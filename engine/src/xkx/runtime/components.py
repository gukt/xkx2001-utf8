"""最小 ECS 组件（S1）。

组件映射 LPC dbase 的结构化字段（01 子系统3 旧->新映射）。SparseSet 后置；
S1 用 dict 存储（``ecs.py``）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xkx.dsl.layer2 import InquiryNode


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
    eff_jingli: int = 0  # 2.7：jingli 有效上限（对照 LPC eff_jingli，2.2 遗漏补全）
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
    # to_death：kill 模式致死 / fight 模式点到为止（LPC kill_ob vs fight_ob 区分，ADR-0039）
    to_death: bool = True
    # win_threshold：fight 模式 qi% 判赢阈值（LPC darba.c checking，0 = kill 模式不判）
    win_threshold: int = 0
    # killer_ids：要杀到死的目标 entity_id 列表（LPC attack.c killer 数组，B-2 ADR-0045）。
    # kill_ob（to_death=True）双向写入；fight 模式不写。init() 查 is_killing 重入房间重触 hatred。
    killer_ids: list[int] = field(default_factory=list)


@dataclass
class NpcBehavior:
    """NPC 行为（LPC chat_msg_combat / attitude / inquiry）。"""

    attitude: str = "friendly"  # friendly | heroism | aggressive
    chat_chance_combat: int = 0
    chat_msg_combat: list[str] = field(default_factory=list)
    # S4 ADR-0006 + M2-2：LPC set("inquiry")，支持纯文本 reply 或 InquiryNode 原子。
    inquiry: dict[str, str | InquiryNode] = field(default_factory=dict)
    # M3-1 ADR-0032 决策 1：拜师配置（师傅 NPC 声明式入门条件 + kneel 剃度）。
    # None=该 NPC 不收徒。结构对照 ApprenticeDef（layer0.py）model_dump：
    # {family_name/generation/title/conditions/kneel/success_message}。
    apprentice_config: dict | None = None
    # B-2 ADR-0045：vendetta 标记（LPC vendetta_mark，标记式追杀非门派世仇）。
    # NPC 被杀 -> 击杀者获 "vendetta:<mark>" flag -> 遇同类 vendetta_mark NPC 触发追杀。
    vendetta_mark: str = ""


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
    """玩家任务日志（S4 ADR-0007 + M3-1 ADR-0032 决策 3 多步 chain）。

    ``statuses``: {quest_id -> "not_started" | "in_progress" | "completed"}
    ``current_step``: {quest_id -> 当前步骤索引}（多步 chain，M3-1）
    ``claimed_at``: {quest_id -> 上次领奖 tick}（time-gate 可重复任务，M3-1；
        对照 jiamu lama_wage 记录 mud_age，冷却判定 current_tick - claimed_at < time_gate）
    """

    statuses: dict[str, str] = field(default_factory=dict)
    current_step: dict[str, int] = field(default_factory=dict)
    claimed_at: dict[str, int] = field(default_factory=dict)


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
class DoorEntry:
    """门状态（C5 ADR-0042 + ADR-0044，对照 LPC room.c doors mapping + status 位掩码）。

    标准 doors 状态模式：exits 静态声明不变，doors 字段存门定义+开闭状态。
    ``closed`` 可变（open/knock 开 / close/DoorSystem call_out 定时关）。``locked``
    锁状态（ADR-0044 落地，独立 bool 非 LPC 位掩码；open 查 locked 走钥匙分支）。
    ``key_id`` 开锁钥匙物品 id（C5 钥匙系统，对照 LPC ``present(key)``；unlock 命令
    检查 inventory 含 key_id -> 解锁）。SMASHED 位跳过（LPC 全仓库死代码，凭空发明规格）。
    """

    name: str  # 门名（LPC doors[dir]["name"]）
    other_room: str  # 对面房间 id（LPC doors[dir]["other_side"] room）
    other_dir: str  # 对面方向（LPC doors[dir]["other_side_dir"]）
    closed: bool = True  # 开闭状态（LPC status & DOOR_CLOSED）
    locked: bool = False  # 锁状态（ADR-0044，LPC DOOR_LOCKED 位，独立 bool）
    key_id: str = ""  # 开锁钥匙物品 id（C5 钥匙系统，对照 LPC present(key) 匹配）


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
    doors: dict[str, DoorEntry] = field(default_factory=dict)  # C5：方向 -> 门


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


@dataclass
class FamilyComp:
    """门派归属组件（M3-1 ADR-0032 决策 1，第 15 组件）。

    承载 LPC ``family`` mapping 7 字段 + ``betrayer`` 叛师计数。拜师时
    ``recruit`` 写入（master_id/master_name/family_name/generation+1/
    enter_time），``assign_apprentice`` 设 title/privs。

    ``Attributes.family``（str）保留兼容 ``family_eq`` 谓词（ADR-0005）+
    ``FamilyBonus`` 分发（ADR-0030），拜师后同步
    ``Attributes.family = family_name``。本组件是 richer 结构（7 字段），
    ``Attributes.family`` 是其 family_name 的 str 投影。

    对照 LPC feature/apprentice.c family mapping + cmds/skill/apprentice.c
    betrayer。可序列化（ADR-0022，字段全基本类型）。
    [ADR-0032](../../../docs/adr/ADR-0032-family-core-loop-design.md)
    """

    family_name: str = ""  # LPC family["family_name"]（如"雪山派"）
    generation: int = 0  # LPC family["generation"]（辈分，拜师=师傅 generation+1）
    master_id: str = ""  # LPC family["master_id"]（师傅 prototype_id）
    master_name: str = ""  # LPC family["master_name"]
    title: str = ""  # LPC family["title"]（门派称号，如"弟子"/"喇嘛"/"法王"）
    privs: int = 0  # LPC family["privs"]（权限：-1=全部，0=无，对照 assign_apprentice）
    enter_time: int = 0  # LPC family["enter_time"]（入门 mud_age，时间系统后置 M3-1 用 0）
    betrayer: int = 0  # LPC add("betrayer",1)（叛师计数）
