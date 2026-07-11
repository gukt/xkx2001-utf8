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

from xkx.runtime.components import (
    Attributes,
    Identity,
    Marks,
    NpcBehavior,
    Progression,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.schema import SchemaRegistry

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
    # Vitals（LPC qi/max_qi/eff_qi/jing/max_jing/jingli/max_jingli/neili/max_neili）
    "qi": (Vitals, "qi"),
    "max_qi": (Vitals, "max_qi"),
    "eff_qi": (Vitals, "eff_qi"),
    "jing": (Vitals, "jing"),
    "max_jing": (Vitals, "max_jing"),
    "jingli": (Vitals, "jingli"),
    "max_jingli": (Vitals, "max_jingli"),
    "neili": (Vitals, "neili"),
    "max_neili": (Vitals, "max_neili"),
    # Progression（LPC combat_exp/potential/max_potential，ADR-0017 从 Vitals 拆出）
    "combat_exp": (Progression, "combat_exp"),
    "potential": (Progression, "potential"),
    "max_potential": (Progression, "max_potential"),
    # Skills（LPC apply_attack/dodge/parry/damage/armor + weapon）
    "apply_attack": (Skills, "apply_attack"),
    "apply_dodge": (Skills, "apply_dodge"),
    "apply_parry": (Skills, "apply_parry"),
    "apply_damage": (Skills, "apply_damage"),
    "apply_armor": (Skills, "apply_armor"),
    "weapon": (Skills, "weapon"),
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
}

# 路径访问 key 前缀 -> (组件类型, 字段名)
# LPC "skill/axe" -> Skills.levels["axe"]（set("skill/axe", 30)）
# LPC "marks/酥" (temp) -> Marks.flags（set_temp("marks/酥", 1)，S4 ADR-0006）
PATH_PREFIX_MAP: dict[str, tuple[type, str]] = {
    "skill": (Skills, "levels"),
    "marks": (Marks, "flags"),
}

# 后置 key（无对应组件，阶段 2/M3 实现时补，文档 13 §三 标注后置阶段）
POSTPONED_KEYS: frozenset[str] = frozenset({
    # 战斗/行为状态（T6 combat 扩展 / T6+ NPC AI）
    "actions", "action_flag", "fight", "disable_type", "disabled",
    "yield", "winner", "victim_name", "free_rider", "guarding",
    "looking_for_trouble", "pursuer", "behavior_exp", "thief",
    "last_opponent", "last_damage_from", "last_eff_damage_from",
    "last_fainted_from", "my_killer",
    # 资源扩展（eff_jing/eff_jingli 后置，Vitals 无字段）
    "eff_jing", "eff_jingli",
    # 角色长期状态（阶段 2 TitleSystem/Race/mud_age 时间系统）
    "title", "shen", "race", "mud_age", "mud_age_last", "age_modify",
    "month", "birthday", "combat_exp_last", "death_count", "death_times",
    # PK/法院系统（阶段 1 法院 / 阶段 2，09 盘点）
    "vendetta", "vendetta_mark", "pking", "pktime",
    # 频道/消息系统（阶段 2，ADR-0014 channeld）
    "channels", "chblk_on", "channel_msg_cnt", "block_msg", "language",
    # 登录/重连（T7 WS 服务器）
    "link_ob", "body_ob", "body", "was_userp", "netdead", "quit",
    # 对象/房间扩展
    "startroom", "no_clean_up", "no_death", "cost", "item_desc", "id",
    "equipped", "env", "apply", "balance", "pending",
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

    支持简单 key（``"combat_exp"``）和路径前缀（``"skill/axe"`` ->
    ``Skills.levels``）。调用方按返回的字段类型自行处理 dict/set 访问。
    """
    if key in DBASE_KEY_MAP:
        return DBASE_KEY_MAP[key]
    if "/" in key:
        prefix = key.split("/", 1)[0]
        if prefix in PATH_PREFIX_MAP:
            return PATH_PREFIX_MAP[prefix]
    return None
