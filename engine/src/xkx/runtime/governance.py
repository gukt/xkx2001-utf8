"""世界观治理系统（阶段 2.6，平台级 fail-closed Python System，ADR-0029）。

实现两个代表性治理元素（对照 ADR-0029 §决策 1）：

- **阴间死亡轮回**：die -> 鬼门关（gate.c 物品销毁）-> 黑白无常 5 段剧情
  EffectComp -> 还阳（主路径丢弃物品 / 隐藏路径不丢弃）。
- **法院 PK 通缉**：四区域通缉 condition（killer/xakiller/dlkiller/bjkiller）+
  审判收监（PKS 分级量刑 + 穿琵琶骨）+ 受贿销案 + 监狱释放。

**平台级 fail-closed 边界**（ADR-0029 §决策 2，对齐 CLAUDE.md 不变量"themed 治理
是平台级 fail-closed Python，不落入 UGC 可编辑规则层"）：

- 治理逻辑硬编码 Python 模块级常量（通缉时长 / 量刑 PKS 阈值 / 刑期 /
  death_stage 5 段 + 30 秒首延 + 5 秒间隔），不通过层 1 DSL / UGC CPK 暴露配置
  接口。UGC 只能"触发"治理（PK 行为触发通缉），不能"修改"治理规则。
- 阴间还阳路径有两条（主路径黑白无常剧情 + 隐藏路径 inn1 ask 回家），均调
  ``reincarnate_at``，无第三条"跳过阴间"路径（fail-closed：必须经过阴间状态机）。
- gate.c 物品销毁（destruct 鬼魂所有非 character 物品）是死亡副作用，玩家无法
  保留阳间物品进入阴间。

**与 ConditionSystem 的边界**（ADR-0029 §决策 4 + 开放问题 1 裁决）：

- 通用 condition 衰减（killer/pker/city_jail 等 duration-1）走 ConditionSystem
  （现有 handler 保留不动）。
- death_stage 治理剧情（5 段对话）由 GovernanceSystem 独立遍历
  ``effect_id="death_stage"`` 的 EffectComp（按 effect_id 过滤），**不注册到
  ConditionSystem**，GovernanceSystem.update 自己调 death_stage_handler + apply 结果。

**确定性**（ADR-0029 §关键约束 5）：death_stage 推进无 random（5 段固定时序），
reincarnate_at 无 random。proceed_sentencing 无 random（PKS 分级 if-else）。

**可序列化**（ADR-0029 §决策 8）：death_stage EffectComp 随鬼魂实体序列化
（EffectComp 已可序列化，ADR-0022）。通缉 condition 走现有 apply_condition
（已支持序列化）。无新组件（复用 EffectComp / Marks / TitleComp / Position /
Inventory）。

**主题中立**（ADR-0029 §关键约束 4）：本模块源码无武侠门派 / 武学字面量。通缉 /
阴间 / 监狱 / 黑白无常是通用治理概念（阴间神话非武侠烙印）。

[ADR-0029](../../../docs/adr/ADR-0029-world-governance-system.md) /
[09 灵魂系统盘点](../../../docs/xkx-arch/09-灵魂系统盘点.md) /
[LPC d/death/npc/wgargoyle.c](../../../d/death/npc/wgargoyle.c) /
[LPC d/death/npc/bgargoyle.c](../../../d/death/npc/bgargoyle.c) /
[LPC d/death/gate.c](../../../d/death/gate.c) /
[LPC d/city/npc/kexiu.c](../../../d/city/npc/kexiu.c) /
[LPC kungfu/condition/city_jail.c](../../../kungfu/condition/city_jail.c)
"""

from __future__ import annotations

from xkx.runtime import death
from xkx.runtime.components import (
    EffectComp,
    Inventory,
    Marks,
    Position,
    Progression,
    RoomComp,
    TitleComp,
)
from xkx.runtime.conditions import (
    ConditionTriggerResult,
    apply_condition,
    clear_one_condition,
    query_condition,
)
from xkx.runtime.ecs import World
from xkx.runtime.message import tell_object
from xkx.runtime.query import move_to
from xkx.runtime.systems import System
from xkx.runtime.theme import ThemeConfig


def _theme_config(world: World) -> ThemeConfig:
    """读取 world.theme_config（ADR-0030 决策 2）。

    裸 ``World()``（不经 ``build_world``）无 ``theme_config`` 属性时 fallback 到
    ``ThemeConfig.default()``（非武侠测试默认配置）。governance.py 源码不硬编码
    武侠房间路径，统一从 ThemeConfig 读取。
    """
    return getattr(world, "theme_config", None) or ThemeConfig.default()

# ──────────── 平台级 fail-closed 治理常量（硬编码，ADR-0029 §决策 2） ────────────

# 黑白无常 5 段剧情对话（对照 wgargoyle.c / bgargoyle.c death_msg[0..4]）。
# greenfield 用中文对照 09 盘点 §二剧情；HIW/HIB 颜色后置简化台账 13 不内核化。
DEATH_STAGE_MSGS_WGARGOYLE: tuple[str, ...] = (
    "白无常说道：喂！新来的，你叫什么名字？\n\n",
    "白无常用奇异的眼光盯著你，好像要看穿你的一切似的。\n\n",
    "白无常「哼」的一声，从袖中掏出一本像帐册的东西翻看著。\n\n",
    "白无常合上册子，说道：咦？阳寿未尽？怎么可能？\n\n",
    "白无常搔了搔头，叹道：罢了罢了，你走吧。\n一股阴冷的浓雾突然出现，很快地包围了你。\n\n",
)
DEATH_STAGE_MSGS_BGARGOYLE: tuple[str, ...] = (
    "黑无常说道：喂！新来的，你叫什么名字？\n\n",
    "黑无常用奇异的眼光盯著你，好像要看穿你的一切似的。\n\n",
    "黑无常「哼」的一声，从袖中掏出一本像帐册的东西翻看著。\n\n",
    "黑无常合上册子，说道：咦？阳寿未尽？怎么可能？\n\n",
    "黑无常搔了搔头，叹道：罢了罢了，你走吧。\n一股阴冷的浓雾突然出现，很快地包围了你。\n\n",
)

# death_stage 时序常量（对照 wgargoyle.c init call_out("death_stage", 30) +
# death_stage call_out("death_stage", 5)）：首延 30 秒 + 每段 5 秒间隔 + 5 段。
DEATH_STAGE_SEGMENTS = 5
DEATH_STAGE_FIRST_DELAY = 30  # 首段延迟（秒，对照 call_out 30）
DEATH_STAGE_INTERVAL = 5  # 段间间隔（秒，对照 call_out 5）

# death_stage EffectComp 字段约定（ADR-0029 §决策 4）：
# - effect_id="death_stage", kind="governance_dialog"
# - detail="wgargoyle" | "bgargoyle"（区分黑白无常 NPC）
# - duration=剩余段数（5->4->...->1，到 0 触发还阳）
# - tick_interval=DEATH_STAGE_INTERVAL, next_tick=触发 tick
# - source_id=无常 NPC eid（若有，else 0）
DEATH_STAGE_EFFECT_ID = "death_stage"
DEATH_STAGE_KIND = "governance_dialog"

# detail -> 剧情对话表（黑白无常共用 5 段，仅 NPC 名差异）。
_DEATH_STAGE_MSGS: dict[str, tuple[str, ...]] = {
    "wgargoyle": DEATH_STAGE_MSGS_WGARGOYLE,
    "bgargoyle": DEATH_STAGE_MSGS_BGARGOYLE,
}

# ──────────────────────── 法院 PK 通缉常量（ADR-0029 §决策 5） ────────────────────────

# region -> effect_id 映射（对照 ADR-0029 §5 四区域通缉表 + 09 §五通缉 condition 文件表）。
# bjkiller 无 LPC condition 文件，apply_condition 框容错（_default_trigger 衰减）。
WANTED_REGIONS: dict[str, str] = {
    "city": "killer",  # 扬州/通用，kungfu/condition/killer.c
    "xa": "xakiller",  # 西夏，kungfu/condition/xakiller.c
    "dl": "dlkiller",  # 大理，kungfu/condition/dlkiller.c
    "bj": "bjkiller",  # 北京（无 condition 文件，仅 apply_condition 施加）
}

# 通缉时长（tick，对照 killer_reward side_effect order=3 apply_condition("killer",100)）。
WANTED_DURATION = 100

# ──────────────────────── 审判收监常量（对照 kexiu.c do_proceed） ────────────────────────

# PKS 分级量刑阈值（对照 kexiu.c:212/218/224 if-else）。
SENTENCE_PKS_HIGH = 99  # PKS > 99 => city_jail 500 tick
SENTENCE_PKS_MID = 74  # PKS > 74 => city_jail 300 tick
SENTENCE_PKS_LOW = 49  # PKS > 49 => city_jail 200 tick

# 刑期（tick，对照 kexiu.c:215/221/227 apply_condition("city_jail", N)）。
SENTENCE_DURATION_HIGH = 500
SENTENCE_DURATION_MID = 300
SENTENCE_DURATION_LOW = 200
SENTENCE_DURATION_RECIDIVIST = 600  # 累犯加重（对照 kexiu.c:229-230 city_jail>4 => 600）
SENTENCE_RECIDIVIST_THRESHOLD = 4  # 已有 city_jail > 4 触发累犯加重

# 穿琵琶骨标记（对照 kexiu.c:235 obj->set("embedded", 1) + do_embed）。
EMBEDDED_FLAG = "embedded"

# 经验转移上限（对照 kexiu.c:206 if (bonus > 3000) bonus = 3000）。
SENTENCE_EXP_TRANSFER_CAP = 3000

# 受贿销案阈值（对照 kexiu.c:175 ob->value() < combat_exp/10 不足销案）。
BRIBE_EXP_DIVISOR = 10

# ──────────────────── 监狱释放房间（ADR-0030 决策 2 外提到 ThemeConfig） ────────────────────

# jail_type -> 释放房间映射从 world.theme_config.jail_rooms 读取（ADR-0030 决策 2，
# 对照 ADR-0029 §5 监狱表 + LPC city_jail.c 等 condition 文件）。governance.py 源码
# 不硬编码武侠房间路径，统一从 ThemeConfig 注入。

# 监狱释放后 startroom 标记前缀（对照 city_jail.c:14 me->set("startroom")）。
STARTROOM_FLAG_PREFIX = "startroom"


# ──────────────────────── GovernanceSystem（平台级 fail-closed System） ────────────────────────


class GovernanceSystem(System):
    """世界观治理系统（平台级 fail-closed，ADR-0029 §决策 2）。

    tick 驱动 death_stage 治理剧情 EffectComp（非均匀 tick，next_tick<=tick 触发）。
    通用 condition 衰减（killer/pker/city_jail）由 ConditionSystem 负责，本 System
    不重复造衰减逻辑（ADR-0029 开放问题 2 裁决）。

    update 遍历 ``effect_id="death_stage"`` 的 EffectComp（按 effect_id 过滤，不混入
    ConditionSystem 通用 on_tick），调 death_stage_handler 取纯函数结果，自行 apply：
    - tell 剧情消息（DEATH_STAGE_MSGS[stage]）
    - 推进 stage（duration-1）+ 更新 next_tick
    - stage 4（最后一段，duration 减到 0）触发 reincarnate_at（主路径还阳）
    """

    name = "GovernanceSystem"

    def update(self, world: World, tick: int) -> None:
        """每 tick 遍历到期 death_stage EffectComp，apply 剧情推进 + stage 4 还阳。

        非均匀 tick：只处理 ``next_tick <= tick`` 的 EffectComp（ADR-0018 §3）。
        物化 EffectComp 实体列表，因遍历中可能 remove（swap-remove 不安全于遍历中）。
        """
        # 收集到期 death_stage EffectComp（按 effect_id 过滤，ADR-0029 开放问题 1 裁决）
        pending: list[tuple[int, EffectComp]] = []
        for effect_eid in world.entities_with(EffectComp):
            eff = world.get(effect_eid, EffectComp)
            if eff is None or eff.effect_id != DEATH_STAGE_EFFECT_ID:
                continue
            if eff.next_tick <= tick:
                pending.append((effect_eid, eff))
        # apply 每个到期 death_stage
        for effect_eid, eff in pending:
            trig = death_stage_handler(world, eff, tick)
            target_id = eff.target_id
            # tell 剧情消息（2.6 最小不推送，消息系统后置 M3，对齐 death._tell）
            tell_object(world, target_id, "".join(trig.messages))
            # 推进 stage：duration 衰减（handler 已算 new_duration）
            new_duration = trig.new_duration
            if new_duration is None:
                new_duration = eff.duration - 1
            eff.duration = new_duration
            if new_duration <= 0:
                # stage 4（最后一段）触发还阳（主路径：丢弃物品 + move revive_room）
                # 黑无常 detail 且活人闯入分支不在此（death_stage 只对 ghost 启动，
                # bgargoyle 活人闯入在 enter_underworld 前置检查，见 death_stage_handler）
                reincarnate_at(
                    world, target_id, _theme_config(world).revive_room, drop_items=True
                )
                world.remove(effect_eid, EffectComp)
            else:
                # 更新 next_tick（下一段触发 tick）
                eff.next_tick = tick + eff.tick_interval
            _mark_dirty(world, effect_eid)
            _mark_dirty(world, target_id)


# ──────────────────────── 阴间死亡轮回 ────────────────────────


def enter_underworld(world: World, eid: int, tick: int, *, gargoyle_eid: int = 0) -> None:
    """die() 触发阴间入口（ADR-0029 §决策 3，对照 d/death/gate.c init）。

    die() 已做 ghost=1 + move 阴间入口（theme_config.death_room，death.py:208-211）。
    本函数做剩余部分：
    1. gate.c 物品销毁：destruct 鬼魂 Inventory 所有非 character 物品（防御性，
       death.die make_corpse 已转移物品到尸体留在死亡地点，鬼魂本应无物品）。
    2. 启动 death_stage EffectComp（白无常 5 段剧情，首延 30 秒 + 5 秒间隔）。

    Args:
        world: ECS 世界。
        eid: 鬼魂实体 id（die 玩家）。
        tick: 当前 tick（首段触发 tick = tick + 30）。
        gargoyle_eid: 无常 NPC 实体 id（若有，作为 source_id 记录；else 0）。
    """
    # gate.c init() 物品销毁（destruct 鬼魂所有非 character 物品）
    # greenfield：Inventory.items 是物品 id 集合（无 is_character 物品，全销毁）
    inv = world.get(eid, Inventory)
    if inv is not None:
        inv.items.clear()
    # 启动 death_stage EffectComp（duration=5 段，首延 30 秒，间隔 5 秒）
    effect_eid = world.new_entity()
    world.add(
        effect_eid,
        EffectComp(
            effect_id=DEATH_STAGE_EFFECT_ID,
            kind=DEATH_STAGE_KIND,
            target_id=eid,
            source_id=gargoyle_eid,
            detail="wgargoyle",  # 主路径白无常入口（gate.c -> wgargoyle）
            duration=DEATH_STAGE_SEGMENTS,
            tick_interval=DEATH_STAGE_INTERVAL,
            next_tick=tick + DEATH_STAGE_FIRST_DELAY,
        ),
    )
    _mark_dirty(world, eid)
    _mark_dirty(world, effect_eid)


def death_stage_handler(
    world: World, eff: EffectComp, tick: int
) -> ConditionTriggerResult:
    """黑白无常剧情 EffectComp handler（GovernanceSystem 自有，非通用 ConditionSystem）。

    5 段对话，每段 5 秒，stage 4 还阳（ADR-0029 §决策 4，对照 wgargoyle.c
    death_stage）。纯函数：读 EffectComp + world 快照，返回 ConditionTriggerResult
    （messages + new_duration），由 GovernanceSystem.update apply。

    stage 反推：``stage = DEATH_STAGE_SEGMENTS - duration``（duration=5 时 stage=0，
    duration=1 时 stage=4）。

    黑无常（detail="bgargoyle"）额外检查 is_ghost：活人闯入直接传送回还阳房间
    （对照 bgargoyle.c:60-66），不推进剧情。greenfield：death_stage 只对 ghost
    启动（die 触发），活人闯入是隐藏路径，本 handler 检测后传送不推进 stage。

    Args:
        world: ECS 世界。
        eff: death_stage EffectComp（duration=剩余段数，detail=无常类型）。
        tick: 当前 tick。

    Returns:
        ConditionTriggerResult：messages=本段对话，new_duration=衰减后剩余段数。
    """
    msgs = _DEATH_STAGE_MSGS.get(eff.detail, DEATH_STAGE_MSGS_WGARGOYLE)
    target_id = eff.target_id
    # 黑无常活人闯入分支（bgargoyle.c:60-66 !is_ghost -> move 还阳房间）
    if eff.detail == "bgargoyle" and not _is_ghost(world, target_id):
        # 活人闯入阴间：传送回还阳房间（theme_config.revive_room），不推进剧情
        # （隐藏路径，ADR-0029 §3）
        move_to(world, target_id, _theme_config(world).revive_room)
        _mark_dirty(world, target_id)
        # 返回 new_duration=0 让 update 移除 EffectComp（剧情终止）
        return ConditionTriggerResult(
            messages=["黑无常说道：喂！阳人来阴间做什么？\n"],
            new_duration=0,
        )
    # 正常剧情推进：stage 反推
    stage = DEATH_STAGE_SEGMENTS - eff.duration
    if stage < 0:
        stage = 0
    if stage >= len(msgs):
        stage = len(msgs) - 1
    r = ConditionTriggerResult()
    r.messages.append(msgs[stage])
    # duration 衰减（5->4->...->1，到 0 由 update 触发还阳）
    r.new_duration = eff.duration - 1
    return r


def reincarnate_at(
    world: World, eid: int, revive_room: str, drop_items: bool
) -> None:
    """还阳（ADR-0029 §决策 3，对照 wgargoyle.c:62 reincarnate + DROP + move）。

    两条还阳路径统一入口（ADR-0029 §3 两条路径）：
    - 主路径：黑白无常 5 段剧情结束 -> reincarnate + DROP_CMD 丢弃物品 + move
      ``theme_config.revive_room``（GovernanceSystem.update 调用）。
    - 隐藏路径：inn1 ask 回家 -> reincarnate + move ``theme_config.revive_room``
      （不丢弃物品，调用方传 ``drop_items=False``）。

    Args:
        world: ECS 世界。
        eid: 鬼魂实体 id。
        revive_room: 还阳目标房间 id（主路径/隐藏路径均由调用方从
            ``world.theme_config.revive_room`` 读取传入）。
        drop_items: True=丢弃所有 Inventory 物品到房间地面（主路径）；
            False=不丢弃（隐藏路径，鬼魂本应无物品）。
    """
    # 还阳：清 ghost + 完整恢复 qi/jing/eff/jingli/neili 到 max（death.reincarnate）
    death.reincarnate(world, eid)
    # 物品处理：主路径 DROP_CMD 丢弃所有物品到房间地面
    if drop_items:
        _drop_all_inventory(world, eid)
    # 位置移动到还阳房间
    move_to(world, eid, revive_room)
    _mark_dirty(world, eid)


# ──────────────────────── 法院 PK 通缉 ────────────────────────


def apply_wanted(world: World, eid: int, region: str, duration: int = WANTED_DURATION) -> None:
    """施加通缉 condition（ADR-0029 §决策 5，对照 killer_reward side_effect order=3）。

    region -> effect_id 映射（WANTED_REGIONS），调 conditions.apply_condition 施加。
    bjkiller 无 LPC condition 文件也支持（apply_condition 框容错，_default_trigger
    衰减）。叠加由调用方手写 query+delta（对齐 pker +120，death.killer_reward 已做）。

    Args:
        world: ECS 世界。
        eid: 被通缉实体 id。
        region: 区域（"city"|"xa"|"dl"|"bj"）。
        duration: 通缉时长（tick，默认 WANTED_DURATION=100）。
    """
    effect_id = WANTED_REGIONS.get(region)
    if effect_id is None:
        return  # 未知 region 不施加（fail-closed，不静默 fallback 到通用 killer）
    apply_condition(world, eid, effect_id, duration)
    _mark_dirty(world, eid)


def query_wanted(world: World, eid: int) -> str | None:
    """查询通缉状态（ADR-0029 §决策 5，执法 NPC AI 用，2.4/层 G 衔接）。

    查 4 种通缉 condition（killer/xakiller/dlkiller/bjkiller）之一，返回 region
    （反查 WANTED_REGIONS）或 None（无通缉）。多 condition 同时存在时返回首个匹配
    （按 WANTED_REGIONS 迭代顺序，确定性无 random）。

    Args:
        world: ECS 世界。
        eid: 被查询实体 id。

    Returns:
        region（"city"|"xa"|"dl"|"bj"）或 None。
    """
    for region, effect_id in WANTED_REGIONS.items():
        if query_condition(world, eid, effect_id) > 0:
            return region
    return None


# ──────────────────────── 审判收监 ────────────────────────


def proceed_sentencing(world: World, eid: int, arrester_eid: int) -> int:
    """审判收监（ADR-0029 §决策 5，对照 kexiu.c do_proceed 量刑分级）。

    PKS 分级量刑（硬编码 if-else，确定性无 random）：
    - PKS > 99 => city_jail 500 tick
    - PKS > 74 => city_jail 300 tick
    - PKS > 49 => city_jail 200 tick
    - 已有 city_jail > 4 => city_jail 600 tick（累犯加重）

    附带副作用（对照 kexiu.c:192-238）：
    - clear_condition（清所有 condition）
    - 穿琵琶骨（Marks.flags 加 EMBEDDED_FLAG，对照 set("embedded", 1)）
    - 清空 Inventory（destruct 所有物品，对照 kexiu.c:195-200 destruct inv）
    - 经验转移给 arrester（Progression.combat_exp += bonus，上限 3000）
    - 施加 city_jail condition（apply_condition，刑期 = 分级量刑）

    Args:
        world: ECS 世界。
        eid: 被审判实体 id。
        arrester_eid: 逮捕者实体 id（接收经验转移 + 赏金）。

    Returns:
        刑期（tick 数，对照 apply_condition("city_jail", N) 的 N）。
    """
    # 累犯检测须在 clear_condition 之前查 city_jail（对照 kexiu.c:229 顺序：
    # LPC 先检查已有 city_jail 再 clear_condition，greenfield 对齐避免死代码）
    existing_jail = query_condition(world, eid, "city_jail")
    # clear_condition（对照 kexiu.c:192 ob->clear_condition()）
    death.clear_condition(world, eid)
    # 穿琵琶骨（对照 kexiu.c:235 set("embedded", 1)）
    _set_flag(world, eid, EMBEDDED_FLAG)
    # 清空 Inventory（对照 kexiu.c:195-200 destruct 所有非装备非 no_get 物品）
    inv = world.get(eid, Inventory)
    if inv is not None:
        inv.items.clear()
    # PKS 分级量刑（对照 kexiu.c:212-228 if-else）
    title = world.get(eid, TitleComp)
    pks = title.pks if title is not None else 0
    # 经验转移量（对照 kexiu.c:205-206 bonus = combat_exp/10, 上限 3000）
    prog = world.get(eid, Progression)
    combat_exp = prog.combat_exp if prog is not None else 0
    bonus = min(combat_exp // 10, SENTENCE_EXP_TRANSFER_CAP)
    # 分级量刑
    if pks > SENTENCE_PKS_HIGH:
        sentence = SENTENCE_DURATION_HIGH
        _transfer_exp(world, eid, arrester_eid, bonus)
    elif pks > SENTENCE_PKS_MID:
        sentence = SENTENCE_DURATION_MID
        _transfer_exp(world, eid, arrester_eid, bonus * 2 // 3)
    elif pks > SENTENCE_PKS_LOW:
        sentence = SENTENCE_DURATION_LOW
        _transfer_exp(world, eid, arrester_eid, bonus // 2)
    else:
        # PKS <= 49 不量刑（对照 kexiu.c：do_proceed 只对 userp && PKS>=50 触发，
        # 但本函数是通用审判入口，低 PKS 给最小刑期 0 不收监）
        sentence = 0
    # 累犯加重（对照 kexiu.c:229-230 if city_jail > 4 => 600；用 clear 前查的值）
    if existing_jail > SENTENCE_RECIDIVIST_THRESHOLD:
        sentence = SENTENCE_DURATION_RECIDIVIST
    # 施加 city_jail condition（刑期 > 0 才施加）
    if sentence > 0:
        apply_condition(world, eid, "city_jail", sentence)
    _mark_dirty(world, eid)
    _mark_dirty(world, arrester_eid)
    return sentence


def bribe_clear_wanted(world: World, eid: int, amount: int) -> bool:
    """受贿销案（ADR-0029 §决策 5，对照 kexiu.c:175 accept_object）。

    amount >= combat_exp//10 时 clear_one_condition(world, eid, "killer") 返回 True，
    else False（金额不足，不销案）。

    Args:
        world: ECS 世界。
        eid: 行贿实体 id。
        amount: 行贿金额（对照 ob->value()）。

    Returns:
        True=销案成功，False=金额不足。
    """
    prog = world.get(eid, Progression)
    combat_exp = prog.combat_exp if prog is not None else 0
    threshold = combat_exp // BRIBE_EXP_DIVISOR
    if amount < threshold:
        return False
    return clear_one_condition(world, eid, "killer")


# ──────────────────────── 监狱 ────────────────────────


def release_from_jail(world: World, eid: int, jail_type: str) -> None:
    """监狱 condition 到期释放（ADR-0029 §决策 5，对照 city_jail.c:9-14 update_condition）。

    监狱 condition 到期时 move 出监狱房间（move_to ``theme_config.jail_rooms[jail_type]``）
    + 设 startroom 标记（Marks.flags 加 "startroom:{room}"，对照 city_jail.c:14
    me->set("startroom", "/d/city/yamen")）。

    Args:
        world: ECS 世界。
        eid: 服刑实体 id。
        jail_type: 监狱类型（"city_jail"|"dali_jail"|"bonze_jail"）。
    """
    release_room = _theme_config(world).jail_rooms.get(jail_type)
    if release_room is None:
        return  # 未知 jail_type 不释放（fail-closed）
    move_to(world, eid, release_room)
    # 设 startroom 标记（对照 city_jail.c:14 set("startroom")）
    _set_flag(world, eid, f"{STARTROOM_FLAG_PREFIX}:{release_room}")
    _mark_dirty(world, eid)


# ──────────────────────── 内部辅助 ────────────────────────


def _is_ghost(world: World, eid: int) -> bool:
    """是否鬼魂（LPC is_ghost()，对照 bgargoyle.c:60 ob->is_ghost()）。

    greenfield：TitleComp.is_ghost（2.5 实现）或 Marks.flags 含 GHOST_FLAG（death.py）。
    """
    title = world.get(eid, TitleComp)
    if title is not None and title.is_ghost:
        return True
    marks = world.get(eid, Marks)
    return marks is not None and death.GHOST_FLAG in marks.flags


def _set_flag(world: World, eid: int, flag: str) -> None:
    """设 Marks.flags 标记（对照 LPC set_temp("marks/X", 1)）。"""
    marks = world.get(eid, Marks)
    if marks is None:
        marks = Marks()
        world.add(eid, marks)
    marks.flags.add(flag)


def _drop_all_inventory(world: World, eid: int) -> None:
    """丢弃所有 Inventory 物品到房间地面（对照 wgargoyle.c:64-66 DROP_CMD->do_drop）。

    greenfield：Inventory.items 物品 id 转移到当前房间 RoomComp.items（房间地面）。
    无 Position 或房间无 RoomComp 则物品直接丢弃（清空 Inventory，对照 destruct）。
    """
    inv = world.get(eid, Inventory)
    if inv is None or not inv.items:
        return
    pos = world.get(eid, Position)
    room_id = pos.room_id if pos else None
    room = _get_room(world, room_id)
    if room is not None:
        room.items |= inv.items
    # 无论房间是否存在都清空 Inventory（物品已"丢弃"，无房间则 destruct）
    inv.items.clear()


def _get_room(world: World, room_id: str | None) -> RoomComp | None:
    """按 room_id 找 RoomComp（线性扫描，对齐 death._get_room）。"""
    if room_id is None:
        return None
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    return None


def _transfer_exp(
    world: World, from_eid: int, to_eid: int, amount: int
) -> None:
    """经验转移（对照 kexiu.c:213-214 who->add + ob->add(-)）。

    从 from_eid 扣 amount combat_exp，加给 to_eid。amount<=0 不操作。
    """
    if amount <= 0:
        return
    from_prog = world.get(from_eid, Progression)
    to_prog = world.get(to_eid, Progression)
    if from_prog is not None:
        from_prog.combat_exp = max(0, from_prog.combat_exp - amount)
    if to_prog is not None:
        to_prog.combat_exp += amount


def _mark_dirty(world: World, eid: int) -> None:
    """ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist。"""
    storage = getattr(world, "storage_system", None)
    if storage is not None:
        storage.mark_dirty(eid)
