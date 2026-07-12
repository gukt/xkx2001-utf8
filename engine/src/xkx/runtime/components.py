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
    eff_jing: int = 100  # 2.2：jing 有效上限（heal_up 恢复上限，对齐 eff_qi）
    jingli: int = 100
    max_jingli: int = 100
    neili: int = 0
    max_neili: int = 0
    water: int = 200  # 2.2：水度（heal_up 脱水门控，LPC set("water")）
    food: int = 200  # 2.2：食物度（heal_up 饥饿门控，LPC set("food")）


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
    """技能 + 临时修正（阶段 2.3 扩展，对照 LPC feature/skill.c）。

    - ``levels``：技能等级（永久基础值层，对照 LPC ``skills`` mapping）
    - ``apply_*``：临时修正标量（对照 LPC ``query_temp("apply/...")``，装备加成
      在 equip 时注入 + condition 修正由 EffectComp 驱动，三类叠加见 ADR-0026）
    - ``skill_map``/``skill_prepare``/``learned``：2.3 新增（对照 LPC skill_map/
      skill_prepare/learned mapping，query_skill 三层叠加 + skill_death_penalty）
    """

    levels: dict[str, int] = field(default_factory=dict)
    apply_attack: int = 0
    apply_dodge: int = 0
    apply_parry: int = 0
    apply_damage: int = 0
    apply_armor: int = 0
    apply_speed: int = 0  # 2.3：apply/speed（fight/riposte 判定，ADR-0026 §1）
    weapon: str | None = None
    # 2.3 新增（ADR-0026 §2 技能三层）：skill_map 映射 + skill_prepare 准备 +
    # learned 进度（skill_death_penalty 真实公式用，对照 skill.c:121-147）
    skill_map: dict[str, str] = field(default_factory=dict)
    skill_prepare: dict[str, str] = field(default_factory=dict)
    learned: dict[str, int] = field(default_factory=dict)


@dataclass
class Equipment:
    """装备组件（阶段 2.3，对照 LPC feature/equip.c wield/wear/unequip）。

    装备槽 + per-slot prop 副本（unequip 反向扣减 apply_* 用，对照 LPC
    ``applied_prop``）。可序列化（字段全基本类型 + dict 容器，ADR-0022 存档崩溃
    安全）。

    prop 副本按槽位存（weapon_props/secondary_weapon_props/armor_props），unequip
    单个物品时按该槽 prop 副本扣减 Skills.apply_*，不依赖 apply_* 当前值（避免
    LPC "中途 condition 改了同 key 导致扣减出错"的隐性 bug，ADR-0026 §1）。

    [ADR-0026](../../../docs/adr/ADR-0026-modifier-stack-and-skill-layers.md)
    """

    # 装备槽（物品 id，None=空）
    weapon: str | None = None
    secondary_weapon: str | None = None
    armors: dict[str, str] = field(default_factory=dict)  # armor_type -> item_id

    # per-slot prop 副本（key: apply_* 路径名如 "attack"/"dodge"；unequip 扣减用）
    weapon_props: dict[str, int] = field(default_factory=dict)
    secondary_weapon_props: dict[str, int] = field(default_factory=dict)
    armor_props: dict[str, dict[str, int]] = field(default_factory=dict)  # type -> prop

    # 负重（对照 LPC F_MOVE weight/encumbrance，ADR-0025 后置 2.3 衔接）
    encumbrance: int = 0  # 当前负重（物品重量总和）
    max_encumbrance: int = 0  # 最大负重（由 str 决定，LPC set_max_encumbrance）


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
    no_death: bool = False  # 2.2：no_death 房玩家死亡转 unconcious（LPC query("no_death")）


@dataclass
class TitleComp:
    """称谓组件（阶段 2.5，ADR-0028 决策 3，第 14 组件）。

    承载 RANK_D 7 函数求值所需的 dbase key：title/nickname/shen（玩家称号）+
    rank_info 四键（rankd 覆盖优先）+ PKS/MKS（PKS 称号）+ class/dali/rank
    （门派职位/官职）+ is_ghost（鬼魂状态）。

    对照 LPC set("title"/"nickname"/"shen"/"rank_info/*"/"PKS"/"MKS"/"class")
    dbase key（dbase_map.py POSTPONED_KEYS，2.5 激活 title/shen；PKS/MKS/class/
    rank/dali/rank 本未在 POSTPONED，2.5 新增激活，ADR-0028 决策 5）。

    可序列化（ADR-0022）：字段全基本类型（str/int/bool/None），serialization.py
    按 dataclasses.fields 自动提取，无需额外适配。
    [ADR-0028](../../../docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md)
    """

    # 玩家称号（LPC set("title")/set("nickname")/set("shen")）
    title: str = ""  # LPC "title"：头衔（如"普通百姓"/"华山派弟子"）
    nickname: str = ""  # LPC "nickname"：绰号（如「老顽童」）
    shen: int = 0  # LPC "shen"：道德值（正=侠，负=魔，rankd 按阈值分级）

    # rank_info 覆盖（LPC set("rank_info/respect|rude|self|self_rude")）
    # rankd.c 行 327/411/468/520：stringp 时直接返回，跳过 gender/class 求值
    rank_info_respect: str | None = None
    rank_info_rude: str | None = None
    rank_info_self: str | None = None
    rank_info_self_rude: str | None = None

    # PKS 称号（LPC "PKS"/"MKS"，09 §五法院系统）
    pks: int = 0  # 玩家击杀数（PKS>100 且 PKS>MKS -> "土匪"/"土匪婆"）
    mks: int = 0  # 怪物击杀数（对照用）

    # 门派职位/官职（LPC "class"/"dali/rank"/"rank"）
    char_class: str = ""  # LPC "class"：职业（bonze/taoist/beggar/eunach/swordsman/...）
    dali_rank: int = 0  # LPC "dali/rank"：大理官职（1-5，5=王爷/王妃）
    family_rank: int = 0  # LPC "rank"：丐帮袋数（rankd 行 28/130-145/280-295）

    # 鬼魂状态（LPC is_ghost()，rankd 行 19 最先判定）
    is_ghost: bool = False
