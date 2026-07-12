"""condition 系统（阶段 1 T1 ADR-0018 + 阶段 2.2 扩展具体类型）。

ConditionHandler.on_tick 对齐 LPC ``feature/condition.c`` 的 ``update_condition()``，
返回组合结构 ``ConditionTickResult``（纯函数，不 mutate 现场状态），由
ConditionSystem 统一 apply。派生变更审计轨迹（dissent 7）。

Effect 作为独立实体（EffectComp attach 到 effect 实体，``target_id`` 指向被作用
实体），支持一个实体同时承载多个 condition。

**阶段 2.2 扩展**（ADR-0018 契约演进）：
- ``condition_deltas`` / ``completed`` 改用 **EffectComp 实体 eid**（int）作 key，
  非 effect_id（str）--支持多 target 同名 condition（玩家 A/B 各自中毒，两个
  "poison" EffectComp 独立衰减，不互相覆盖）。ADR-0018 原用 effect_id 假设全局
  唯一，2.2 apply_condition 打破该假设，故演进 key 类型。
- 新增 ``apply_condition`` / ``query_condition`` / ``clear_condition`` /
  ``clear_one_condition`` 运行时函数（对齐 LPC ``feature/condition.c``）。
- 新增 condition handler 注册机制 + 6 个具体类型（poisoned/snake_poison/drunk/
  blind/killer/pker），对照 [kungfu/condition/](../../../kungfu/condition/) LPC 规格。
- ``apply_condition`` 直接覆盖语义（LPC apply_condition 不自动叠加，叠加由调用方
  手写 query+delta，如 pker ``+120``）。

[ADR-0018](../../../docs/adr/ADR-0018-conditionhandler-on-tick-contract.md) /
[ADR-0025](../../../docs/adr/ADR-0025-query-index-layer.md) /
[kungfu/condition/](../../../kungfu/condition/) /
[spec/layer_f_death.py](../spec/layer_f_death.py)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from xkx.combat.result import (
    KIND_CLEAR_MARK,
    KIND_DAMAGE,
    KIND_DAMAGE_JING,
    KIND_HEAL,
    KIND_HEAL_JING,
    KIND_WOUND_JING,
    LEDGER_EFFECT,
    LEDGER_MESSAGE,
    Effect,
    LedgerEntry,
)
from xkx.runtime.components import Attributes, EffectComp, Vitals
from xkx.runtime.ecs import World
from xkx.runtime.systems import System

# LPC include/condition.h
CND_CONTINUE = 1
CND_NO_HEAL_UP = 2


@dataclass
class ConditionTickResult:
    """ConditionHandler.on_tick 的返回值（ADR-0018 组合结构，不 mutate 现场状态）。

    - ``effects``: 即时副作用（DoT 扣血/heal 等），按触发顺序
    - ``messages``: 文本（毒发/醉倒等），按触发顺序
    - ``condition_deltas``: ``{effect_eid: 新剩余 duration}``（2.2 改用 EffectComp
      实体 eid 作 key 支持多 target 同名 condition）
    - ``completed``: 到期移除的 effect_eid 列表（2.2 改 int）
    - ``flags``: LPC CND_NO_HEAL_UP 等（跨 System 通信）
    - ``ledger``: messages 与 effects 的交织顺序（对齐 combat ledger，dissent 7）
    """

    effects: list[Effect] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    condition_deltas: dict[int, int] = field(default_factory=dict)
    completed: list[int] = field(default_factory=list)
    flags: int = 0
    ledger: list[LedgerEntry] = field(default_factory=list)


@dataclass
class ConditionTriggerResult:
    """单个 condition 的 tick 触发结果（handler 返回，2.2）。

    handler 纯函数：读 EffectComp + world 快照，返回本 condition 的副作用 + 衰减
    决策，由 ConditionHandler 合并到 ConditionTickResult。
    - ``effects``: 即时副作用（DoT 扣血/微醺加血等）
    - ``messages``: 文本（毒发/醉意等）
    - ``new_duration``: None=不衰减（永久）；int=衰减后剩余（<=0 触发移除）
    - ``flags``: CND_NO_HEAL_UP 等（2.2 的 6 个 condition 均不设，保留语义）
    """

    effects: list[Effect] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    new_duration: int | None = None
    flags: int = 0


# condition handler 签名：(world, eff, tick) -> ConditionTriggerResult
ConditionHandlerFn = Callable[[World, EffectComp, int], ConditionTriggerResult]

# effect_id -> handler 注册表（2.2）。未注册的 effect_id 用 _default_trigger。
CONDITION_HANDLERS: dict[str, ConditionHandlerFn] = {}


def register_condition(name: str, handler: ConditionHandlerFn) -> None:
    """注册 condition handler（2.2）。模块加载时注册具体 condition 类型。"""
    CONDITION_HANDLERS[name] = handler


# ──────────────────────── 默认 handler（未注册 effect_id） ────────────────────────


def _default_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """默认 handler：amount!=0 生成 Effect + duration 衰减（ADR-0018 原逻辑）。

    用于未注册的 effect_id（如测试中的通用 EffectComp）。
    """
    r = ConditionTriggerResult()
    if eff.amount != 0:
        r.effects.append(
            Effect(
                kind=eff.kind,
                target_id=eff.target_id,
                amount=eff.amount,
                detail=eff.detail,
            )
        )
    if eff.duration > 0:
        r.new_duration = eff.duration - 1
    r.flags = eff.flags
    return r


# ──────────────────────── 具体 condition handler（对照 kungfu/condition/） ────────────────────────


def _poisoned_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """poisoned（普通毒，壳 condition，对照 kungfu/condition/poisoned.c）。

    纯衰减壳：不扣血无消息，duration 每 tick -1，到 0 移除。
    真正的蛇毒 DoT 见 ``snake_poison``。
    """
    return ConditionTriggerResult(
        new_duration=eff.duration - 1 if eff.duration > 0 else None
    )


def _snake_poison_trigger(
    world: World, eff: EffectComp, tick: int
) -> ConditionTriggerResult:
    """snake_poison（蛇毒 DoT，对照 kungfu/condition/snake_poison.c）。

    每 tick 扣 qi = duration//2 + wound eff_jing = duration//3，按 eff_jing 分档
    消息。衰减步长 1（greenfield 简化；LPC 是 5+poison/10，后置 2.3 接真实抗毒公式）。
    """
    r = ConditionTriggerResult()
    vitals = world.get(eff.target_id, Vitals)
    if vitals is None:
        return r
    dmg = eff.duration // 2
    wound = eff.duration // 3
    # 消息分档（对照 snake_poison.c，按 eff_jing vs max_jing 伤情程度）
    if vitals.eff_jing > vitals.max_jing // 2:
        r.messages.append("你感到四肢发麻，蛇毒发作。")
    elif vitals.eff_jing > vitals.max_jing // 4:
        r.messages.append("你感到呼吸困难。")
    else:
        r.messages.append("你感到天旋地转。")
    if dmg > 0:
        r.effects.append(Effect(kind=KIND_DAMAGE, target_id=eff.target_id, amount=dmg))
    if wound > 0:
        r.effects.append(
            Effect(kind=KIND_WOUND_JING, target_id=eff.target_id, amount=wound)
        )
    r.new_duration = eff.duration - 1 if eff.duration > 0 else None
    return r


def _drunk_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """drunk（醉酒 debuff，对照 kungfu/condition/drunk.c）。

    limit = 3 + (con + max_neili//40)（体质+内力决定酒量上限）：
    - duration > limit/2：扣 jing 10（脑中昏沉）
    - limit/4 < duration <= limit/2：微醺活血（加 jing 10 + qi 15）
    - duration <= limit/4：无副作用（即将醒酒）
    晕倒（duration > limit 调 unconcious）后置 death.py 衔接（2.2 不在 handler 内
    mutate，避免 conditions->death 循环依赖）。
    """
    r = ConditionTriggerResult()
    attrs = world.get(eff.target_id, Attributes)
    vitals = world.get(eff.target_id, Vitals)
    if attrs is None or vitals is None:
        return r
    limit = 3 + (attrs.con_ + vitals.max_neili // 40)
    half = limit // 2
    quarter = limit // 4
    if eff.duration > half:
        r.messages.append("你脑中昏昏沉沉，摇头晃脑站不稳。")
        r.effects.append(
            Effect(kind=KIND_DAMAGE_JING, target_id=eff.target_id, amount=10)
        )
    elif eff.duration > quarter:
        r.messages.append("你一阵酒意上冲，略有微醺。")
        r.effects.append(
            Effect(kind=KIND_HEAL_JING, target_id=eff.target_id, amount=10)
        )
        r.effects.append(Effect(kind=KIND_HEAL, target_id=eff.target_id, amount=15))
    r.new_duration = eff.duration - 1 if eff.duration > 0 else None
    return r


def _blind_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """blind（失明，对照 kungfu/condition/blind.c）。

    静默 condition：持续期间无副作用，到期（duration<=1）输出"视力恢复"消息。
    apply/attack 恢复（LPC add_temp apply/attack cimu_power）后置 2.3
    Attribute/Skill/Equipment（apply_* 体系完整后接恢复钩子）。
    """
    r = ConditionTriggerResult()
    if eff.duration <= 1:
        r.messages.append("你的视力恢复过来了。")
        r.new_duration = 0
    else:
        r.new_duration = eff.duration - 1
    return r


def _killer_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """killer（官府通缉，对照 kungfu/condition/killer.c）。

    纯计时器，到期 tell "官府不再通缉你了"。2.6 GovernanceSystem 接管执法 NPC
    检测 query_condition("killer") 触发追杀（WantedCondition 统一）。
    """
    r = ConditionTriggerResult()
    if eff.duration <= 1:
        r.messages.append("官府不再通缉你了！")
        r.new_duration = 0
    else:
        r.new_duration = eff.duration - 1
    return r


def _pker_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """pker（红名 PK 冷却，对照 kungfu/condition/pker.c）。

    纯计时器，到期静默移除（无消息，与 killer 区别）。叠加由调用方手写
    query+delta（如 killer_reward 中 +120）。
    """
    return ConditionTriggerResult(
        new_duration=eff.duration - 1 if eff.duration > 0 else None
    )


def _revive_trigger(world: World, eff: EffectComp, tick: int) -> ConditionTriggerResult:
    """revive（昏迷自动苏醒定时器，对照 feature/damage.c unconcious call_out revive）。

    duration<=1 到期时清 unconscious 标记 + 苏醒消息（自然苏醒）。
    die 中 revive(1) 强制安静苏醒由 ``death.revive()`` 直接处理（不经 handler，
    避免 conditions->death 循环依赖）。
    """
    r = ConditionTriggerResult()
    if eff.duration <= 1:
        r.messages.append("慢慢地你终于又有了知觉。")
        r.effects.append(
            Effect(kind=KIND_CLEAR_MARK, target_id=eff.target_id, detail="unconscious")
        )
        r.new_duration = 0
    else:
        r.new_duration = eff.duration - 1
    return r


# 模块加载时注册具体 condition 类型
register_condition("poisoned", _poisoned_trigger)
register_condition("snake_poison", _snake_poison_trigger)
register_condition("drunk", _drunk_trigger)
register_condition("blind", _blind_trigger)
register_condition("killer", _killer_trigger)
register_condition("pker", _pker_trigger)
register_condition("revive", _revive_trigger)


# ──────────────────────── ConditionHandler（纯函数 on_tick） ────────────────────────


class ConditionHandler:
    """condition 系统核心（ADR-0018 + 2.2 handler 分派），对应 LPC
    ``feature/condition.c`` 的 ``update_condition()``。

    on_tick 是纯函数：只读 EffectComp 快照 + tick，返回 ConditionTickResult，不
    mutate 现场状态。ConditionSystem.update 调本方法后统一 apply。

    非均匀 tick：只处理 ``next_tick <= tick`` 的 EffectComp（ADR-0018 §3）。

    2.2：按 effect_id 分派到注册 handler（poisoned/snake_poison/drunk/blind/
    killer/pker），未注册用 _default_trigger。
    """

    def on_tick(self, world: World, tick: int) -> ConditionTickResult:
        """遍历到期 EffectComp，分派 handler，返回组合结构（不 mutate world）。"""
        result = ConditionTickResult()
        for effect_eid in world.entities_with(EffectComp):
            eff = world.get(effect_eid, EffectComp)
            if eff is None or eff.next_tick > tick:
                continue
            handler = CONDITION_HANDLERS.get(eff.effect_id, _default_trigger)
            trig = handler(world, eff, tick)
            self._merge(result, trig, effect_eid)
        return result

    @staticmethod
    def _merge(
        result: ConditionTickResult, trig: ConditionTriggerResult, effect_eid: int
    ) -> None:
        """合并单 condition 触发结果到聚合 result（按账本交织顺序）。"""
        for e in trig.effects:
            result.effects.append(e)
            result.ledger.append(LedgerEntry(entry_type=LEDGER_EFFECT, effect=e))
        for m in trig.messages:
            result.messages.append(m)
            result.ledger.append(LedgerEntry(entry_type=LEDGER_MESSAGE, text=m))
        if trig.new_duration is not None:
            result.condition_deltas[effect_eid] = trig.new_duration
            if trig.new_duration <= 0:
                result.completed.append(effect_eid)
        result.flags |= trig.flags


class ConditionSystem(System):
    """condition 系统 ECS System（ADR-0014，tick 驱动）。

    update 调 ConditionHandler.on_tick 得到 ConditionTickResult，统一 apply 到 world
    （apply effects + 衰减 duration + 移除 completed + 更新 next_tick）。
    """

    name = "ConditionSystem"

    def __init__(self) -> None:
        self._handler = ConditionHandler()

    def update(self, world: World, tick: int) -> None:
        result = self._handler.on_tick(world, tick)
        # apply 即时副作用（按账本顺序）
        from xkx.runtime.world import apply_effects

        apply_effects(world, result.effects)
        # 衰减 duration / 移除 completed / 更新 next_tick
        # 物化实体列表，因遍历中可能 remove（swap-remove 不安全于遍历中）
        for effect_eid in list(world.entities_with(EffectComp)):
            eff = world.get(effect_eid, EffectComp)
            if eff is None:
                continue
            if effect_eid in result.completed:
                world.remove(effect_eid, EffectComp)
                continue
            if effect_eid in result.condition_deltas:
                eff.duration = result.condition_deltas[effect_eid]
            if eff.next_tick <= tick:
                eff.next_tick = tick + eff.tick_interval

        # ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist
        # （整合遗留：EffectComp duration/next_tick 变更 + apply_effects 改 Vitals）
        storage = getattr(world, "storage_system", None)
        if storage is not None:
            for e in result.effects:
                storage.mark_dirty(e.target_id)
            for effect_eid in world.entities_with(EffectComp):
                storage.mark_dirty(effect_eid)


# ──────────────────────── LPC F_CONDITION 运行时函数（2.2） ────────────────────────


def apply_condition(
    world: World,
    eid: int,
    name: str,
    duration: int,
    *,
    amount: int = 0,
    source_id: int = 0,
    detail: str = "",
) -> None:
    """施加 condition（LPC ``apply_condition(cnd, info)``，2.2）。

    直接覆盖语义（LPC apply_condition 不自动叠加）：target 已有同名 EffectComp
    则更新 duration（覆盖），否则新建 EffectComp 实体 attach。叠加由调用方手写
    ``query_condition + delta``（对齐 pker ``+120``）。
    """
    # 查 target 已有同名 condition（per-target 唯一，覆盖）
    for effect_eid in world.entities_with(EffectComp):
        eff = world.get(effect_eid, EffectComp)
        if eff is not None and eff.target_id == eid and eff.effect_id == name:
            eff.duration = duration
            if amount:
                eff.amount = amount
            if source_id:
                eff.source_id = source_id
            if detail:
                eff.detail = detail
            return
    # 新建 EffectComp 实体（kind 留空，注册 handler 的 condition 由 handler 决定 effects）
    effect_eid = world.new_entity()
    world.add(
        effect_eid,
        EffectComp(
            effect_id=name,
            kind="",
            target_id=eid,
            amount=amount,
            source_id=source_id,
            detail=detail,
            duration=duration,
            tick_interval=1,  # greenfield 每 tick 触发（LPC 5-14s 非均匀后置）
            next_tick=0,
        ),
    )


def query_condition(world: World, eid: int, name: str) -> int:
    """查 condition 剩余 duration（LPC ``query_condition(cnd)``，2.2）。

    返回剩余 duration（0=无此 condition，对齐 LPC 不存在返回 0）。
    """
    for effect_eid in world.entities_with(EffectComp):
        eff = world.get(effect_eid, EffectComp)
        if eff is not None and eff.target_id == eid and eff.effect_id == name:
            return eff.duration
    return 0


def clear_condition(world: World, eid: int) -> None:
    """清除 target 所有 condition（LPC ``clear_condition()``，2.2）。

    die / death_penalty 中调用（清除毒/特殊状态等）。
    """
    for effect_eid in list(world.entities_with(EffectComp)):
        eff = world.get(effect_eid, EffectComp)
        if eff is not None and eff.target_id == eid:
            world.remove(effect_eid, EffectComp)


def clear_one_condition(world: World, eid: int, name: str) -> bool:
    """清除 target 指定 condition（LPC ``clear_one_condition(cnd)``，2.2）。

    返回是否清除成功（True=有此 condition 已清，False=无）。
    """
    for effect_eid in list(world.entities_with(EffectComp)):
        eff = world.get(effect_eid, EffectComp)
        if eff is not None and eff.target_id == eid and eff.effect_id == name:
            world.remove(effect_eid, EffectComp)
            return True
    return False
