"""LPC dbase key -> ECS 组件字段映射表（阶段 1 T3，ADR-0019）。

LPC dbase 是字符串 key 的 mapping（[feature/dbase.c](../../../feature/dbase.c)），
全仓约 68771 个 query/set 调用点（[08](../../../docs/xkx-arch/08-阶段-0-实施计划.md)
§四抽样校准）。``query("cobmat_exp")`` 拼写错误静默返回 0（[spec/layer_b]
(_query_spec postcondition)）。本表把 go/move/combat 路径核心键映射到 ECS 组件
字段，T2 SchemaRegistry.has_field 启动期校验映射目标合法（ADR-0019）。

范围（[12](../../../docs/xkx-arch/12-阶段1-核心循环实施计划.md) T3 验收：核心键集 +
9 层规格涉及的 dbase 键）：

- **已映射**：``components.py`` 13 组件承接的简单 key（``DBASE_KEY_MAP``）
- **路径前缀**：``skill/xxx`` -> ``Skills.levels``，``marks/xxx`` -> ``Marks.flags``
  （``PATH_PREFIX_MAP``，LPC dbase 路径访问语义，[spec/layer_b](_set_spec notes)）
- **后置**：无对应组件的 key（``POSTPONED_KEYS``，文档标注后置阶段）

完整枚举与后置说明见
[13-dbase-key-map.md](../../../docs/xkx-arch/13-dbase-key-map.md)。
动态拼接 key（``"eff_" + type`` / ``"max_" + type``）按完整 key 映射（eff_qi/max_qi
等），type 维度见文档。
"""

from __future__ import annotations

from typing import Literal

from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Marks,
    NpcBehavior,
    Progression,
    RoomComp,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.schema import SchemaError, SchemaRegistry

# LPC dbase 简单 key -> (组件类型, 字段名)
# 启动期由 validate_dbase_map 校验映射目标字段存在（ADR-0019 has_field）
DBASE_KEY_MAP: dict[str, tuple[type, str]] = {
    # Identity（LPC set_name -> name/id/my_id）
    "name": (Identity, "name"),
    # Attributes（LPC str/dex/int/con/age/gender/family）
    "str": (Attributes, "str_"),
    "dex": (Attributes, "dex_"),
    "int": (Attributes, "int_"),
    "con": (Attributes, "con_"),
    "age": (Attributes, "age"),
    "gender": (Attributes, "gender"),
    "family": (Attributes, "family"),
    "family_name": (Attributes, "family"),  # LPC family/family_name 同义
    # Vitals（LPC qi/jing/eff_*/max_*/jingli/neili/water/food，2.2 激活 eff_jing/water/food）
    "qi": (Vitals, "qi"),
    "max_qi": (Vitals, "max_qi"),
    "eff_qi": (Vitals, "eff_qi"),
    "jing": (Vitals, "jing"),
    "max_jing": (Vitals, "max_jing"),
    "eff_jing": (Vitals, "eff_jing"),  # 2.2 激活（heal_up 恢复上限）
    "eff_jingli": (Vitals, "eff_jingli"),  # 2.7 激活（setup_race 用，2.2 遗漏补全）
    "jingli": (Vitals, "jingli"),
    "max_jingli": (Vitals, "max_jingli"),
    "neili": (Vitals, "neili"),
    "max_neili": (Vitals, "max_neili"),
    "water": (Vitals, "water"),  # 2.2 激活（heal_up 脱水门控）
    "food": (Vitals, "food"),  # 2.2 激活（heal_up 饥饿门控）
    # Progression（LPC combat_exp/potential/max_potential，ADR-0017 从 Vitals 拆出）
    "combat_exp": (Progression, "combat_exp"),
    "potential": (Progression, "potential"),
    "max_potential": (Progression, "max_potential"),
    # Skills（LPC apply_attack/dodge/parry/damage/armor/speed + weapon）
    "apply_attack": (Skills, "apply_attack"),
    "apply_dodge": (Skills, "apply_dodge"),
    "apply_parry": (Skills, "apply_parry"),
    "apply_damage": (Skills, "apply_damage"),
    "apply_armor": (Skills, "apply_armor"),
    "apply_speed": (Skills, "apply_speed"),  # 2.3 激活（fight/riposte 判定）
    "weapon": (Skills, "weapon"),
    # Equipment（LPC weight/encumbrance，2.3 激活，ADR-0026 §3 F_MOVE 负重）
    "weight": (Equipment, "encumbrance"),
    "encumbrance": (Equipment, "encumbrance"),
    # NpcBehavior（LPC attitude/chat_chance_combat/chat_msg_combat/inquiry）
    "attitude": (NpcBehavior, "attitude"),
    "chat_chance_combat": (NpcBehavior, "chat_chance_combat"),
    "chat_msg_combat": (NpcBehavior, "chat_msg_combat"),
    "inquiry": (NpcBehavior, "inquiry"),
    # RoomComp（LPC exits/objects/short/long/outdoors/no_fight）
    "exits": (RoomComp, "exits"),
    "objects": (RoomComp, "objects"),
    "short": (RoomComp, "short"),
    "long": (RoomComp, "long"),
    "outdoors": (RoomComp, "outdoors"),
    "no_fight": (RoomComp, "no_fight"),
    "no_death": (RoomComp, "no_death"),  # 2.2 激活（die no_death 房判定）
    # TitleComp（LPC title/nickname/shen/PKS/MKS/class/rank，2.5 激活，ADR-0028 决策 5）
    "title": (TitleComp, "title"),  # LPC "title"：头衔
    "nickname": (TitleComp, "nickname"),  # LPC "nickname"：绰号（不在 POSTPONED，直接激活）
    "shen": (TitleComp, "shen"),  # LPC "shen"：道德值
    "PKS": (TitleComp, "pks"),  # LPC "PKS"：玩家击杀数
    "MKS": (TitleComp, "mks"),  # LPC "MKS"：怪物击杀数
    "class": (TitleComp, "char_class"),  # LPC "class"：职业（字段名避 Python 保留字）
    "rank": (TitleComp, "family_rank"),  # LPC "rank"：丐帮袋数
}

# 路径访问 key 前缀 -> (组件类型, 字段名)
# LPC "skill/axe" -> Skills.levels["axe"]（set("skill/axe", 30)）
# LPC "marks/酥" (temp) -> Marks.flags（set_temp("marks/酥", 1)，S4 ADR-0006）
PATH_PREFIX_MAP: dict[str, tuple[type, str]] = {
    "skill": (Skills, "levels"),
    "marks": (Marks, "flags"),
}

# apply/ 子路径 -> Skills.apply_* 标量（ADR-0026 §3 装备 prop 注入）。
# apply/attack -> Skills.apply_attack 等；未知 apply/{x} 子路径读返回 0（LPC
# query_temp 未设语义；通用 apply/{skill} 存储后置 M3）。
APPLY_SUBPATH_MAP: dict[str, str] = {
    "attack": "apply_attack",
    "dodge": "apply_dodge",
    "parry": "apply_parry",
    "damage": "apply_damage",
    "armor": "apply_armor",
    "speed": "apply_speed",
}
APPLY_PREFIX = "apply"

# rank_info/ 子路径 -> TitleComp.rank_info_* 字段（ADR-0028 决策 5）。
# LPC "rank_info/respect" -> TitleComp.rank_info_respect 等；rankd.c 行 327/411/
# 468/520：stringp 时直接返回，跳过 gender/class 求值。未知 rank_info/{x} 子路径
# 读返回 None（未设覆盖），对齐 apply/ 未知子路径语义。
RANK_INFO_PREFIX = "rank_info"
RANK_INFO_SUBPATH_MAP: dict[str, str] = {
    "respect": "rank_info_respect",
    "rude": "rank_info_rude",
    "self": "rank_info_self",
    "self_rude": "rank_info_self_rude",
}

# dali/ 子路径 -> TitleComp.dali_* 字段（ADR-0028 决策 5）。
# LPC "dali/rank" -> TitleComp.dali_rank（大理官职，rankd 行 40/115-120/263-270）。
# rankd.c 行 40 先查 dali/employee（布尔）决定是否取 dali/rank，greenfield 简化只
# 处理 dali/rank（dali/employee 后置）。未知 dali/{x} 子路径读返回 None。
DALI_PREFIX = "dali"
DALI_SUBPATH_MAP: dict[str, str] = {
    "rank": "dali_rank",
}

# 语义 key（非简单字段映射，走语义函数，ADR-0026 §3 equipped）。
# query 返回派生值（equipped -> 装备物品集合），set 不支持（装备走 wield/wear）。
# 不进 DBASE_KEY_MAP（无简单字段，validate_dbase_map 不校验）。
SEMANTIC_KEY_MAP: dict[str, type] = {
    "equipped": Equipment,  # is_equipped 语义函数，query 返回装备物品集合
}

# 后置 key（无对应组件，阶段 2/M3 实现时补，文档 13 §三 标注后置阶段）
POSTPONED_KEYS: frozenset[str] = frozenset({
    # 战斗/行为状态（T6 combat 扩展 / T6+ NPC AI）
    "actions", "action_flag", "fight", "disable_type", "disabled",
    "yield", "winner", "victim_name", "free_rider", "guarding",
    "looking_for_trouble", "pursuer", "behavior_exp", "thief",
    "last_opponent", "last_damage_from", "last_eff_damage_from",
    "last_fainted_from", "my_killer",
    # 资源扩展（eff_jing 2.2 激活；eff_jingli 2.7 激活见 DBASE_KEY_MAP）
    # 角色长期状态（阶段 2 TitleSystem/Race/mud_age 时间系统）
    # 2.5 激活 title/shen 到 TitleComp（ADR-0028 决策 5），race/mud_age 等仍后置
    "race", "mud_age", "mud_age_last", "age_modify",
    "month", "birthday", "combat_exp_last", "death_count", "death_times",
    # PK/法院系统（阶段 1 法院 / 阶段 2，09 盘点）
    "vendetta", "vendetta_mark", "pking", "pktime",
    # 频道/消息系统（阶段 2，ADR-0014 channeld）
    "channels", "chblk_on", "channel_msg_cnt", "block_msg", "language",
    # 登录/重连（T7 WS 服务器）
    "link_ob", "body_ob", "body", "was_userp", "netdead", "quit",
    # 对象/房间扩展（equipped/apply 2.3 激活，见 SEMANTIC_KEY_MAP / apply 前缀）
    "startroom", "no_clean_up", "cost", "item_desc", "id",
    "env", "balance", "pending",
})


def validate_dbase_map(schema: SchemaRegistry) -> list[str]:
    """启动期校验 DBASE_KEY_MAP + PATH_PREFIX_MAP 映射目标字段存在（ADR-0019）。

    返回问题列表（空 = 全部合法）。``build_world`` 启动期调用，问题非空 raise
    ``SchemaError``，防映射目标拼写错误静默传播。
    """
    issues: list[str] = []
    for key, (comp_type, field_name) in DBASE_KEY_MAP.items():
        if not schema.has_field(comp_type, field_name):
            issues.append(
                f"DBASE_KEY_MAP[{key!r}] -> "
                f"{comp_type.__name__}.{field_name} 字段不存在"
            )
    for prefix, (comp_type, field_name) in PATH_PREFIX_MAP.items():
        if not schema.has_field(comp_type, field_name):
            issues.append(
                f"PATH_PREFIX_MAP[{prefix!r}] -> "
                f"{comp_type.__name__}.{field_name} 字段不存在"
            )
    return issues


def resolve_dbase_key(key: str) -> tuple[type, str] | None:
    """解析 LPC dbase key -> (组件类型, 字段名)。未映射返回 None（后置/未知）。

    支持简单 key（``"combat_exp"``）+ 路径前缀（``"skill/axe"`` ->
    ``Skills.levels``）+ ``apply/`` 子路径分发（``"apply/attack"`` ->
    ``Skills.apply_attack``，ADR-0026 §3）。调用方按返回的字段类型自行处理
    dict/set/标量访问。``equipped`` 等语义 key 不在此解析（走 SEMANTIC_KEY_MAP）。
    """
    if key in DBASE_KEY_MAP:
        return DBASE_KEY_MAP[key]
    if "/" in key:
        prefix, sub = key.split("/", 1)
        # apply/ 子路径分发到 Skills.apply_* 标量（已知 6 个；未知返回 None）
        if prefix == APPLY_PREFIX:
            field = APPLY_SUBPATH_MAP.get(sub)
            return (Skills, field) if field is not None else None
        # rank_info/ 子路径分发到 TitleComp.rank_info_* 覆盖字段（ADR-0028 决策 5）
        # 已知 4 子路径（respect/rude/self/self_rude）；未知返回 None
        if prefix == RANK_INFO_PREFIX:
            field = RANK_INFO_SUBPATH_MAP.get(sub)
            return (TitleComp, field) if field is not None else None
        # dali/ 子路径分发到 TitleComp.dali_*（ADR-0028 决策 5）
        # 已知 dali/rank；未知返回 None（dali/employee 后置）
        if prefix == DALI_PREFIX:
            field = DALI_SUBPATH_MAP.get(sub)
            return (TitleComp, field) if field is not None else None
        if prefix in PATH_PREFIX_MAP:
            return PATH_PREFIX_MAP[prefix]
    return None


# ──────────────────────── ADR-0025：key 分类 + 异常 ────────────────────────


class DbaseKeyError(SchemaError):
    """未映射/后置 key 读写异常（ADR-0025）。

    ``SchemaError`` 子类，复用 ADR-0019 错误体系。未映射 key 的拼写错误
    （如 ``"cobmat_exp"``）raise 本异常，非静默返回 0/None（dissent 2）。
    """


# key 三类分类（ADR-0025 决策 1：区分后置与未知）
KeyClass = Literal["mapped", "postponed", "unknown"]


def is_postponed(key: str) -> bool:
    """判断 key 是否为后置 key（POSTPONED_KEYS，ADR-0025）。

    后置 key = 已知但对应子系统未实现（如 ``"race"`` 后置 2.6 Race/mud_age 后置
    M3 时间系统）。区别于"未知 key"（拼写错误，不在任何集合中）。2.5 已激活
    title/shen 到 TitleComp（ADR-0028 决策 5），不再后置。
    """
    return key in POSTPONED_KEYS


def classify_key(key: str) -> KeyClass:
    """分类 key 为三类（ADR-0025 决策 1，dissent 2 拼写错误不静默）。

    - ``"mapped"``：已映射（DBASE_KEY_MAP / PATH_PREFIX_MAP / ``apply/``/
      ``rank_info/``/``dali/`` 子路径 / SEMANTIC_KEY_MAP），可正常读写（语义 key
      读返回派生值，写见 query.py）
    - ``"postponed"``：后置 key（POSTPONED_KEYS），对应子系统未实现
    - ``"unknown"``：未知 key（拼写错误或未枚举），raise 而非静默

    路径前缀 key（``"skill/axe"``）按前缀判断：已知前缀 -> mapped，未知前缀 ->
    unknown（不归 postponed，因未知前缀是拼写错误非后置）。``apply/``/
    ``rank_info/``/``dali/`` 是已知前缀（任意子路径 mapped；未知子路径读返回
    0/None 不 raise，对齐 LPC query/query_temp 未设语义）。语义 key（``equipped``）
    非简单字段，走 is_equipped 语义函数。
    """
    if key in SEMANTIC_KEY_MAP:
        return "mapped"
    if "/" in key:
        prefix = key.split("/", 1)[0]
        # apply/ rank_info/ dali/ 已知前缀（任意子路径 mapped；未知子路径读返回 0/None
        # 不 raise，对齐 LPC query/query_temp 未设语义）
        if prefix in (APPLY_PREFIX, RANK_INFO_PREFIX, DALI_PREFIX):
            return "mapped"
    if resolve_dbase_key(key) is not None:
        return "mapped"
    if key in POSTPONED_KEYS:
        return "postponed"
    return "unknown"
