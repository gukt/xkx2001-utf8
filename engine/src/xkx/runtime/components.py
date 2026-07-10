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
    combat_exp: int = 0
    potential: int = 0


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
class RoomComp:
    room_id: str
    short: str
    long: str
    exits: dict[str, str] = field(default_factory=dict)
    objects: dict[str, int] = field(default_factory=dict)
    outdoors: bool = False
    no_fight: bool = False
