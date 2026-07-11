"""最小 ECS 组件（S1）。

组件映射 LPC dbase 的结构化字段（01 子系统3 旧->新映射）。SparseSet 后置；
S1 用 dict 存储（``ecs.py``）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Identity:
    name: str
    aliases: list[str] = field(default_factory=list)
    is_player: bool = False
    prototype_id: str = ""  # NPC/玩家 def id（如 "city/npc/bing"）


@dataclass
class Position:
    room_id: str


@dataclass
class Attributes:
    str_: int = 20
    dex_: int = 20
    int_: int = 20
    con_: int = 20
    age: int = 20
    gender: str = "男性"
    family: str = ""  # S4 ADR-0005：LPC family/family_name（门派判断）


@dataclass
class Vitals:
    qi: int = 100
    max_qi: int = 100
    eff_qi: int = 100
    jing: int = 100
    max_jing: int = 100
    jingli: int = 100
    max_jingli: int = 100
    neili: int = 0
    max_neili: int = 0


@dataclass
class Progression:
    """角色长期进度（阶段 1 T1，ADR-0017）。

    从 Vitals 拆出 ``combat_exp``/``potential``/``max_potential``：Vitals 专注当前
    资源（qi/jing/jingli 会波动），Progression 承载长期进度（只增不减，除非死亡
    惩罚）。对应 LPC dbase 的 combat_exp/potential 键。
    [ADR-0017](../../../docs/adr/ADR-0017-ecs-sparse-set-effect-component.md)
    """

    combat_exp: int = 0
    potential: int = 0
    max_potential: int = 100


@dataclass
class Skills:
    levels: dict[str, int] = field(default_factory=dict)
    apply_attack: int = 0
    apply_dodge: int = 0
    apply_parry: int = 0
    apply_damage: int = 0
    apply_armor: int = 0
    weapon: str | None = None


@dataclass
class CombatState:
    enemy_ids: list[int] = field(default_factory=list)
    # 招式（S1 简化：固定；未来从 SkillData 取）
    action_message: str = "$N一招「试探」，攻向$n$l"
    action_force: int = 100
    action_dodge: int = 30
    action_parry: int = 30
    action_damage: int = 20
    action_damage_type: str = "击伤"
    # 本回合招式技能 id + 武器显示名（题材数据声明，内核不解释，见 ADR-0003）
    attack_skill: str = "unarmed"
    weapon_label: str = "拳头"
    hit_ob_bonus: int = 0
    hit_by_override: int | None = None
    # T10 整合遗留：CombatantSnapshot 已有字段，CombatState 补齐 + to_snapshot 传递
    # （ADR-0023 决策 4 第 4/5 项；T6 用默认值兼容，不 break 但不启用 T6 新功能）
    # guarding：LPC set_temp("guarding")，riposte 触发条件之一（规格 order=48）
    guarding: int = 0
    # is_fighting：LPC is_fighting()，skill_power DEFENSE 折减判定
    is_fighting: bool = False
    # fight_dodge：LPC set_temp("fight/dodge")，DEFENSE 加成（规格 order=7）
    fight_dodge: int = 0


@dataclass
class NpcBehavior:
    """NPC 行为（LPC chat_msg_combat / attitude / inquiry）。"""

    attitude: str = "friendly"  # friendly | heroism | aggressive
    chat_chance_combat: int = 0
    chat_msg_combat: list[str] = field(default_factory=list)
    inquiry: dict[str, str] = field(default_factory=dict)  # S4 ADR-0006：LPC set("inquiry")


@dataclass
class Inventory:
    """物品栏（S4 ADR-0005：LPC ``present(obj, me)`` -> ``has_item`` 谓词）。

    S4 最小：物品 id 集合（无堆叠/装备/容器，后续切片扩）。
    """

    items: set[str] = field(default_factory=set)


@dataclass
class Marks:
    """临时标记（LPC ``set_temp("marks/X", 1)``）。

    S4 ADR-0006：``set_flag`` 副作用存储，``has_flag`` 谓词读取。
    """

    flags: set[str] = field(default_factory=set)


@dataclass
class QuestLog:
    """玩家任务日志（S4 ADR-0007）。

    ``statuses``: {quest_id -> "not_started" | "in_progress" | "completed"}
    """

    statuses: dict[str, str] = field(default_factory=dict)


@dataclass
class EffectComp:
    """持续 Effect 组件（阶段 1 T1，ADR-0017）。

    承载 condition（毒/醉/失明）/ buff / DoT 等持续效果，区别于 combat 即时
    Effect（``CombatRoundResult.effects``，apply 后不持久化）。ConditionHandler.on_tick
    按 ``next_tick`` 触发（ADR-0018）。

    可序列化（字段全基本类型）/ 可中断（remove 或按 effect_id 取消）/ 可崩溃恢复
    （存档含 duration/next_tick，04 §三硬约束）。
    [ADR-0017](../../../docs/adr/ADR-0017-ecs-sparse-set-effect-component.md) /
    [ADR-0018](../../../docs/adr/ADR-0018-conditionhandler-on-tick-contract.md)
    """

    effect_id: str
    kind: str
    target_id: int
    source_id: int = 0
    amount: int = 0
    detail: str = ""
    duration: int = 0  # 剩余 tick（0=永久，需显式取消）
    tick_interval: int = 1
    next_tick: int = 0
    flags: int = 0  # LPC CND_CONTINUE(1) / CND_NO_HEAL_UP(2)


@dataclass
class RoomComp:
    room_id: str
    short: str
    long: str
    exits: dict[str, str] = field(default_factory=dict)
    objects: dict[str, int] = field(default_factory=dict)
    items: set[str] = field(default_factory=set)  # S5a：房间地面物品（take 命令拾取）
    outdoors: bool = False
    no_fight: bool = False
