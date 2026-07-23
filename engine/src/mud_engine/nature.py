"""Nature 系统：昼夜时辰循环 + 晴雨天气骨架（M1 扩展块 B，13~17 号票）。

机制归引擎、文案/相位序列归题材包（ADR-0004 手法推广到非战斗系统）：

- ``NatureState`` 是 world 级纯内存态，**不进存档**；重启 / 构建时按可注入
  时钟对齐当前相位（对应 LPC ``natured.c`` 的重启对齐，非行为等价）。
- 相位配置数据驱动（``DayPhase``：name / length 游戏分钟 / time_msg / desc_msg，
  可选 ``rain_desc_msg`` 构成时辰 × 天气二维文案）。
- 挂 ``on_tick`` 推进（``game_minutes_per_tick`` 可配，默认 1，即 1 tick ≈ 1
  游戏分钟，对应"60:1"游玩节奏：CLI 每命令 1 tick）。
- 实现 ``ConditionContext`` 协议，供条件求值器查询（14 号票）。
- 相位 / 天气切换时分发 ``on_nature_change``，并向户外玩家推送广播文案到
  ``world.pending_messages``（16/17 号票）。
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from mud_engine.components import Description, LocalNature, PlayerSession, Position
from mud_engine.events import ON_TICK, TickContext
from mud_engine.world import EntityId, World

# 相位 / 天气切换事件名（16/17 号票）。形状由 ``NatureChangeContext`` 契约锁定。
ON_NATURE_CHANGE = "on_nature_change"

# 默认真墙钟 -> 游戏分钟比例：1 真实秒 = 1 游戏分钟（LPC TIME_TICK = time()*60
# 的"游戏分钟"语义）。可注入 clock 时测试不依赖墙钟。
Clock = Callable[[], float]
Rng = random.Random


class Weather(Enum):
    """天气两态：晴 / 雨（17 号票骨架）。不做对玩家机制影响（视野/移动等）。"""

    CLEAR = "clear"
    RAIN = "rain"


@dataclass(frozen=True)
class DayPhase:
    """一个时辰相位的声明式配置（题材包数据，引擎只管推进）。

    ``rain_desc_msg`` 非空时，下雨天户外 look 用它替代 ``desc_msg``，形成
    「时辰 × 天气」二维文案；为空则在 ``desc_msg`` 后追加默认雨片段。
    """

    name: str
    length: int  # 游戏分钟
    time_msg: str  # 切换到本相位时推给户外玩家的文案
    desc_msg: str  # 晴天户外 look 追加的描述片段
    rain_desc_msg: str = ""  # 雨天户外 look 描述；空则回退拼接


@dataclass(frozen=True)
class NatureChangeContext:
    """``on_nature_change`` 分发给订阅者的上下文。形状被契约测试锁定。

    frozen dataclass：字段全为值 / 枚举 / 实体 id，无 mutable 引用（与
    ``TickContext`` / 09 号票领域事件上下文同风格）。

    ``phase_msgs`` 携带本次 tick 跨越的**全部**相位切换文案（含中间相位，
    一个 tick 跨多相位时不丢），``weather_msg`` 是天气切换文案。户外广播
    订阅者用这俩组装推送内容；``time_msg`` 是向后兼容的"代表文案"（最后一
    相文案，或仅天气变时的天气文案），供只需一条文案的订阅者。
    """

    world: World
    old_phase: str
    new_phase: str
    old_weather: Weather
    new_weather: Weather
    time_msg: str  # 代表文案：phase_msgs[-1] 或 weather_msg
    phase_msgs: tuple[str, ...] = ()  # 本次跨越的全部相位切换文案（含中间相位）
    weather_msg: str = ""  # 天气切换文案；未切换为空


# 题材无关默认四相，总长 1440 游戏分钟 = 1 游戏日。
DEFAULT_PHASES: tuple[DayPhase, ...] = (
    DayPhase(
        name="dawn",
        length=240,
        time_msg="东方的天空中开始出现一丝微曦。",
        desc_msg="东方的天空已逐渐发白。",
        rain_desc_msg="东方微曦，细雨蒙蒙。",
    ),
    DayPhase(
        name="day",
        length=720,
        time_msg="天光大亮。",
        desc_msg="日正当空，天色晴朗。",
        rain_desc_msg="白天，下着小雨。",
    ),
    DayPhase(
        name="dusk",
        length=240,
        time_msg="天色渐渐暗了下来。",
        desc_msg="夕阳西下，暮色四合。",
        rain_desc_msg="黄昏时分，细雨连绵。",
    ),
    DayPhase(
        name="night",
        length=240,
        time_msg="夜幕降临了。",
        desc_msg="夜深了，四下一片寂静。",
        rain_desc_msg="夜雨潇潇，四野寂然。",
    ),
)

_PHASE_LABELS = {
    "dawn": "黎明",
    "day": "白天",
    "dusk": "黄昏",
    "night": "夜晚",
    "midnight": "午夜",
}

# 高阶谓词相位集合（14 号票）。对齐 research「夜里」条件：
# night / midnight / dawn 算夜里（户外夜事件、NPC 闲聊等）；day / dusk 算白天。
# 精确时辰仍用 ``phase == X``（Equals），不依赖这两集合是否互斥完备。
NIGHT_PHASES: frozenset[str] = frozenset({"night", "midnight", "dawn"})
DAY_PHASES: frozenset[str] = frozenset({"day", "dusk"})

_DEFAULT_RAIN_SUFFIX = "下着小雨。"
_WEATHER_CLEAR_MSG = "雨停了，天空放晴。"
_WEATHER_RAIN_MSG = "天阴了下来，下起了雨。"

# 每个 tick 天气翻转概率（可注入 RNG 做确定性测试）。
DEFAULT_WEATHER_CHANGE_CHANCE = 0.1


class NatureState:
    """世界级 Nature 运行时态：当前相位、推进进度、天气。

    实现 ``ConditionContext`` 协议（``phase`` / ``is_night`` / ``is_day`` /
    ``is_raining``），另暴露 ``game_time_str`` 供展示。不进存档。
    """

    def __init__(
        self,
        phases: Sequence[DayPhase],
        *,
        game_minutes_per_tick: int = 1,
        weather: Weather = Weather.CLEAR,
        weather_change_chance: float = DEFAULT_WEATHER_CHANGE_CHANCE,
        rng: Rng | None = None,
        phase_index: int = 0,
        elapsed: int = 0,
    ) -> None:
        if not phases:
            raise ValueError("NatureState 至少需要一个 day phase")
        if game_minutes_per_tick < 1:
            raise ValueError("game_minutes_per_tick 必须 >= 1")
        self.phases: tuple[DayPhase, ...] = tuple(phases)
        self.phase_index = phase_index % len(self.phases)
        self.elapsed = max(0, elapsed)  # 当前相位内已流逝的游戏分钟
        self.weather = weather
        self.game_minutes_per_tick = game_minutes_per_tick
        self.weather_change_chance = weather_change_chance
        self.rng: Rng = rng if rng is not None else random.Random()

    # ---- ConditionContext 协议 ----

    @property
    def phase(self) -> str:
        """当前时辰名（如 ``"night"``），供 ``phase == X`` 比较。"""
        return self.phases[self.phase_index].name

    @property
    def is_night(self) -> bool:
        """是否夜里：``phase`` ∈ ``NIGHT_PHASES``（night / midnight / dawn）。

        高阶概念，不止 ``phase == "night"``。黎明算夜里（对齐 research
        「只在夜里闲聊」类条件）；精确时辰用 ``Equals("phase", ...)``。
        """
        return self.phase in NIGHT_PHASES

    @property
    def is_day(self) -> bool:
        """是否白天：``phase`` ∈ ``DAY_PHASES``（day / dusk）。

        黄昏算白天侧（与 ``is_night`` 互补覆盖默认四相）；未知相位两者皆 False。
        """
        return self.phase in DAY_PHASES

    @property
    def is_raining(self) -> bool:
        """是否在下雨。"""
        return self.weather is Weather.RAIN

    @property
    def faction_id(self) -> str | None:
        """世界环境无门派概念；门槏查询面缺省 None。"""
        return None

    @property
    def gender(self) -> str | None:
        """世界环境无性别；门槏查询面缺省 None。"""
        return None

    @property
    def is_wielding_edged_weapon(self) -> bool:
        """世界环境无持械状态；门槏查询面缺省 False。"""
        return False

    @property
    def game_time_str(self) -> str:
        """可读游戏时间字符串（时辰中文名，雨天加后缀）。"""
        label = _PHASE_LABELS.get(self.phase, self.phase)
        if self.is_raining:
            return f"{label}，雨"
        return label

    @property
    def current_phase(self) -> DayPhase:
        """当前相位配置。"""
        return self.phases[self.phase_index]

    def seek_phase(self, name: str) -> None:
        """跳到名为 ``name`` 的相位并清零相位内进度；测试 / 剧本常用。"""
        for index, phase in enumerate(self.phases):
            if phase.name == name:
                self.phase_index = index
                self.elapsed = 0
                return
        raise ValueError(f"NatureState 无相位 {name!r}")

    @property
    def day_length_minutes(self) -> int:
        """一游戏日总长（全部相位 length 之和）。"""
        return sum(p.length for p in self.phases)

    def outdoor_desc(self) -> str:
        """户外 look 追加的「时辰 × 天气」描述片段。"""
        return self.outdoor_desc_for(phase=self.phase, weather=self.weather)

    def outdoor_desc_for(self, *, phase: str, weather: Weather) -> str:
        """按给定 phase×weather 取户外文案（仍用本单例相位表，ADR-0013）。"""
        phase_cfg = self._phase_by_name(phase)
        if weather is Weather.RAIN:
            if phase_cfg.rain_desc_msg:
                return phase_cfg.rain_desc_msg
            return f"{phase_cfg.desc_msg}{_DEFAULT_RAIN_SUFFIX}"
        return phase_cfg.desc_msg

    def _phase_by_name(self, name: str) -> DayPhase:
        for phase in self.phases:
            if phase.name == name:
                return phase
        # 贴纸 phase 应在加载期已校验；运行期若漂移则回退当前相，避免 look 崩。
        return self.current_phase

    def align_from_clock(self, clock: Clock) -> None:
        """按时钟对齐当前相位与相位内进度（重启 / attach 时调用）。

        ``clock()`` 返回 Unix 秒；默认 1 真实秒 = 1 游戏分钟，对一天总长取模
        后落入对应相位。测试注入固定 clock 避免依赖墙钟。
        """
        total = self.day_length_minutes
        if total <= 0:
            self.phase_index = 0
            self.elapsed = 0
            return
        minutes = int(clock()) % total
        remaining = minutes
        for index, phase in enumerate(self.phases):
            if remaining < phase.length:
                self.phase_index = index
                self.elapsed = remaining
                return
            remaining -= phase.length
        # minutes ∈ [0, total)，各相位 length>0，循环内必 return，此处不可达。
        raise AssertionError("unreachable: clock modulo must fall into a phase")

    def advance_tick(self, world: World) -> None:
        """推进一个 tick：累加游戏分钟，可能切换相位 / 天气。

        相位或天气变化时分发 ``on_nature_change``（携带本次跨越的全部相位
        文案 ``phase_msgs`` + 天气文案 ``weather_msg``，多相位不丢中间）；
        户外广播由 ``on_nature_change`` 订阅者 ``_broadcast_nature_change``
        推送，不在此内联（spec US 21：广播挂事件点以便复用于未来天气变化）。
        """
        old_phase = self.phase
        old_weather = self.weather
        self.elapsed += self.game_minutes_per_tick

        phase_msgs: list[str] = []
        while self.elapsed >= self.current_phase.length:
            self.elapsed -= self.current_phase.length
            self.phase_index = (self.phase_index + 1) % len(self.phases)
            phase_msgs.append(self.current_phase.time_msg)

        weather_msg = self._maybe_change_weather() or ""

        new_phase = self.phase
        new_weather = self.weather
        if new_phase == old_phase and new_weather is old_weather:
            return

        # 代表文案：相位变取最后一相，否则取天气文案（进此分支必有一者非空）。
        time_msg = phase_msgs[-1] if phase_msgs else weather_msg
        world.events.dispatch(
            ON_NATURE_CHANGE,
            NatureChangeContext(
                world=world,
                old_phase=old_phase,
                new_phase=new_phase,
                old_weather=old_weather,
                new_weather=new_weather,
                time_msg=time_msg,
                phase_msgs=tuple(phase_msgs),
                weather_msg=weather_msg,
            ),
        )

    def _maybe_change_weather(self) -> str | None:
        """按概率翻转天气；未翻转返回 None，翻转返回广播文案。"""
        if self.weather_change_chance <= 0:
            return None
        if self.rng.random() >= self.weather_change_chance:
            return None
        if self.weather is Weather.CLEAR:
            self.weather = Weather.RAIN
            return _WEATHER_RAIN_MSG
        self.weather = Weather.CLEAR
        return _WEATHER_CLEAR_MSG


@dataclass(frozen=True)
class EffectiveNature:
    """房间贴纸与 World.nature 合成后的只读读数（ADR-0013）。"""

    phase: str
    weather: Weather
    is_night: bool
    is_day: bool
    is_raining: bool


def resolve_effective_nature(
    world: World, room_id: EntityId | None
) -> EffectiveNature | None:
    """按房间合成 Nature 读数；无 ``World.nature`` 时返回 None（与今日一致）。

    回退：``LocalNature`` 已声明的面 → ``World.nature`` 单例。
    """
    nature = world.nature
    if nature is None:
        return None
    local = (
        world.get_component(room_id, LocalNature) if room_id is not None else None
    )
    phase = local.phase if local is not None and local.phase is not None else nature.phase
    if local is not None and local.weather is not None:
        weather = Weather.RAIN if local.weather == Weather.RAIN.value else Weather.CLEAR
    else:
        weather = nature.weather
    return EffectiveNature(
        phase=phase,
        weather=weather,
        is_night=phase in NIGHT_PHASES,
        is_day=phase in DAY_PHASES,
        is_raining=weather is Weather.RAIN,
    )


def outdoor_desc_for_room(world: World, room_id: EntityId | None) -> str | None:
    """户外 look 追加行：合成 phase×weather，文案仍取 World 相位表。"""
    nature = world.nature
    if nature is None:
        return None
    eff = resolve_effective_nature(world, room_id)
    if eff is None:
        return None
    return nature.outdoor_desc_for(phase=eff.phase, weather=eff.weather)


def attach_nature(
    world: World,
    *,
    phases: Sequence[DayPhase] | None = None,
    clock: Clock | None = None,
    rng: Rng | None = None,
    game_minutes_per_tick: int | None = None,
    weather: Weather = Weather.CLEAR,
    weather_change_chance: float = DEFAULT_WEATHER_CHANGE_CHANCE,
    config_from_yaml: object | None = None,
) -> NatureState:
    """把 Nature 挂到 world：设 ``world.nature``、注册 ``on_tick``、按时钟对齐。

    配置优先级：显式 ``phases`` 参数 > ``config_from_yaml`` >
    ``world.extension_data["nature"]`` > ``DEFAULT_PHASES``。同一 world 重复
    调用会替换 ``NatureState``，但 ``on_tick`` handler 只注册一次。
    """
    config = config_from_yaml
    if config is None:
        config = world.extension_data.get("nature")

    resolved_phases = phases
    resolved_gmt = game_minutes_per_tick
    if resolved_phases is None:
        parsed = _parse_nature_config(config)
        if parsed is not None:
            resolved_phases, cfg_gmt = parsed
            if resolved_gmt is None:
                resolved_gmt = cfg_gmt
    if resolved_phases is None:
        resolved_phases = DEFAULT_PHASES
    if resolved_gmt is None:
        resolved_gmt = 1

    state = NatureState(
        resolved_phases,
        game_minutes_per_tick=resolved_gmt,
        weather=weather,
        weather_change_chance=weather_change_chance,
        rng=rng,
    )
    state.align_from_clock(clock if clock is not None else time.time)

    # 重复 attach 不重复注册：EventBus.register 不去重（见 events.py），用
    # handlers_for 查重避免同一 handler 注册多次（替代 world 上的哨兵猴补丁）。
    if _on_tick_nature not in world.events.handlers_for(ON_TICK):
        world.events.register(ON_TICK, _on_tick_nature)
    if _broadcast_nature_change not in world.events.handlers_for(ON_NATURE_CHANGE):
        world.events.register(ON_NATURE_CHANGE, _broadcast_nature_change)

    world.nature = state
    return state


def _on_tick_nature(context: TickContext) -> None:
    """on_tick 订阅者：推进挂在 world 上的 NatureState。"""
    nature = context.world.nature
    if nature is None:
        return
    nature.advance_tick(context.world)


def _parse_nature_config(
    config: object,
) -> tuple[tuple[DayPhase, ...], int | None] | None:
    """从 YAML 透传的 nature 段解析相位序列；无法解析时返回 None（回退默认）。"""
    if not isinstance(config, dict):
        return None
    raw_phases = config.get("day_phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        return None
    phases: list[DayPhase] = []
    for entry in raw_phases:
        if not isinstance(entry, dict):
            return None
        name = entry.get("name")
        length = entry.get("length")
        if not name or length is None:
            return None
        try:
            length_int = int(length)
        except (TypeError, ValueError):
            return None
        if length_int < 1:
            return None
        phases.append(
            DayPhase(
                name=str(name),
                length=length_int,
                time_msg=str(entry.get("time_msg", "")),
                desc_msg=str(entry.get("desc_msg", "")),
                rain_desc_msg=str(entry.get("rain_desc_msg", "")),
            )
        )
    gmt_raw = config.get("game_minutes_per_tick")
    gmt: int | None = None
    if gmt_raw is not None:
        try:
            gmt = int(gmt_raw)
        except (TypeError, ValueError):
            gmt = None
    return tuple(phases), gmt


def _outdoor_player_ids(world: World) -> list[EntityId]:
    """在户外房间的玩家实体（PlayerSession + Position + 房间 outdoors）。

    28 号票起玩家判定走 ``PlayerSession``，不再用 Container 启发式（NPC 将来
    也可挂 Container）。
    """
    result: list[EntityId] = []
    for entity in world.entities_with(PlayerSession, Position):
        room = world.require_component(entity, Position).room
        desc = world.get_component(room, Description)
        if desc is not None and desc.outdoors:
            result.append(entity)
    return result


def _broadcast_nature_change(ctx: NatureChangeContext) -> None:
    """``on_nature_change`` 订阅者：把切换文案推给每个户外玩家。

    广播挂在事件点上（spec US 21），题材包可注册自己的 ``on_nature_change``
    订阅者替换/扩展广播。每位户外玩家各收 ``phase_msgs`` + ``weather_msg``
    一份；室内玩家不收。CLI 在 tick 后 drain 打印。
    """
    messages = [*ctx.phase_msgs]
    if ctx.weather_msg:
        messages.append(ctx.weather_msg)
    if not messages:
        return
    outdoor_players = _outdoor_player_ids(ctx.world)
    if not outdoor_players:
        return
    for player_id in outdoor_players:
        for msg in messages:
            if msg:
                ctx.world.push_message(player_id, msg)


__all__ = [
    "DAY_PHASES",
    "DEFAULT_PHASES",
    "DEFAULT_WEATHER_CHANGE_CHANCE",
    "NIGHT_PHASES",
    "ON_NATURE_CHANGE",
    "Clock",
    "DayPhase",
    "EffectiveNature",
    "NatureChangeContext",
    "NatureState",
    "Weather",
    "attach_nature",
    "outdoor_desc_for_room",
    "resolve_effective_nature",
]
