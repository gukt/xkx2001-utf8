"""LLM prompt 模板（ADR-0036）：从 LPC 规格源生成层0 DSL 初稿。

grounded in ``07-agent-schema-mapping``（LPC -> schema 字段映射 + map_skill 推断
三规则 + 三类偏差陷阱）。目标：降低 ADR-0004 三类偏差，修订量 <40%（kill criteria 5）。
"""

from __future__ import annotations

_SYSTEM_LINES = [
    "你是侠客行 MUD 新引擎的 LPC -> DSL 转译助手。从给定 LPC 源码生成 YAML DSL 初稿。",
    "",
    "严格遵守 07-agent-schema-mapping 映射规则。",
    "",
    "三类偏差陷阱（必须避免）：",
    '1. neili/max_neili 混淆：schema 只有 max_neili（上限）。LPC set("neili",X) 是当前值，'
    '忽略；只取 set("max_neili",Y)。',
    "2. attack_skill 填武器类别：attack_skill = map_skill(武器类别) 推断的招式，不是武器类别本身。",
    "推断三规则：有 map_skill(W,X) 且持武器类别 W -> X；无 map_skill 但持 W 且 W in skills -> W；"
    "无武器 -> unarmed。",
    "3. weapon 填物品 id：weapon = 武器类别（从武器物品 inherit STAFF/SWORD/BLADE 或 "
    "init_xxx 推断），不是物品 id。",
    "",
    "输出要求：",
    "- 只输出纯 YAML，不要 markdown 代码围栏（```），不要任何解释文字。",
    "- 字段用 schema 定义名（str_/dex_/int_/con_ 带下划线避关键字，非 str/dex/int/con）。",
    "- LPC 未显式 set 的字段省略（用 schema 默认值），不要凭空补值。",
    "- 函数式 inquiry（LPC (:func:)）取函数内 say/write 文本转静态字符串；set_temp 副作用用"
    " `# GAP: ...` 注释标注（DSL 不支持的表达力缺口）。",
]

SYSTEM_PROMPT = "\n".join(_SYSTEM_LINES)


def _wrap(lpc_source: str, task: str) -> list[dict[str, str]]:
    """组装 messages（system + user）。user 包含 task 指令 + LPC 源码。"""
    user = f"{task}\n\n以下是需要转译的 LPC 源码：\n\n----\n{lpc_source}\n----\n"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def build_npc_prompt(lpc_source: str, npc_id: str) -> list[dict[str, str]]:
    """NpcDef 转译 prompt（含可选 apprentice 拜师配置）。"""
    lines = [
        f'将上述 LPC 转译为单个 NpcDef 的 YAML（顶层 dict，id="{npc_id}"）。',
        "",
        "NpcDef schema 字段（仅这些，未列出省略）：",
        "id / name / aliases(list) / gender / age / "
        "attitude(friendly|heroism|aggressive|peaceful)",
        "str_ / dex_ / int_ / con_ / max_qi / max_jing / max_jingli / max_neili / combat_exp",
        "skills(dict {skill: level}) / apply_attack / apply_dodge / apply_parry / "
        "apply_damage / apply_armor",
        "weapon(类别如 staff/blade/sword，无武器省略) / "
        "attack_skill(map_skill 推断招式，无武器=unarmed) / "
        "weapon_label(武器中文名，无武器=\"拳头\")",
        "chat_chance_combat / chat_msg_combat(list) / inquiry(dict {topic: 静态 reply})",
        "apprentice(可选，师傅收徒配置；非师傅 NPC 省略此字段)",
        "",
        "apprentice 结构（仅该 NPC 是师傅，即 LPC 有 create_family + attempt_apprentice 时填）：",
        "  family_name(门派名) / generation(师傅辈分 int，如 gongcang=12) / "
        "title(门派称号如\"弟子\")",
        "  conditions(入门条件 dict):",
        "    min_combat_exp(int，玩家 combat_exp 下限，0=不限)",
        "    reject_gender(str，拒绝此性别，空=不限；对照 gongcang 拒女徒)",
        "    allow_families(list，允许的已有门派；空=不限门派)",
        "    other_family_max_combat_exp(int，已有门派不在 allow_families 时 "
        "combat_exp 上限，0=不限)",
        "    min_skills(dict {skill: level}，任一技能低于阈值拒绝)",
        "    require_flags(list，玩家须持有的标记名)",
        "  kneel(可选，剃度配置；仅 gongcang 类需剃度的师傅填，否则省略):",
        "    set_class(剃度后职业如 lama) / require_flag(需的 pending 标记) / "
        "clear_flag(剃度后清除标记) / message(剃度文本)",
        "  success_message(收徒成功消息文本)",
        "",
        "map_skill 推断：LPC map_skill(base, mapped) + 持 base 类武器 -> attack_skill = mapped。"
        "weapon 类别从 carry_object(...)->wield() 的武器文件 inherit/init 推断。",
    ]
    return _wrap(lpc_source, "\n".join(lines))


def build_skill_prompt(lpc_source: str, skill_id: str) -> list[dict[str, str]]:
    """SkillData 转译 prompt（练功字段 bool stub，rich 条件记 GAP，ADR-0036 决策 5）。"""
    lines = [
        f'将上述 LPC 武学文件转译为单个 SkillData 的 YAML（顶层 dict，skill_id="{skill_id}"）。',
        "",
        "SkillData schema 字段（M3-1 练功 stub，ADR-0032 决策 2）：",
        "skill_id(武学 id) / skill_type(str，LPC type()：martial/knowledge/dodge 等)",
        "valid_learn(bool，LPC valid_learn(me) 简化：能否向 NPC 学习此武学)",
        "practice_skill(bool，LPC practice_skill(me) 简化：能否自行练习)",
        "valid_enable(list[str]，可 enable 映射的基础技能类别如 [sword, parry]；空=不限)",
        "",
        "判定规则：",
        "- valid_learn：LPC valid_learn 返回 1 或无条件限制 -> true；"
        "返回 0 或有 class/属性硬门槛 -> "
        "true（门槛用 `# GAP:` 注释标注，bool 仍 true，因 greenfield 练功命令另做门控）",
        "- practice_skill：LPC practice_skill 存在且可练 -> true；LPC type()==knowledge"
        "（如 lamaism 密宗佛法，只能 learn 不能 practice）-> false",
        "- valid_enable：LPC valid_enable 函数返回的可行 map 种类"
        "（如 xueshan-jian: [sword, parry]）",
        "- skill_type：LPC inherit FORCE -> 内功相关 martial；"
        "inherit SKILL + type() -> 取 type() 字符串",
        "",
        "LPC 的丰富学习条件（class=lama / lamaism>=120 / 经书 / neili 阈值等）DSL 暂不支持，用"
        " `# GAP: <具体条件>` 注释标注，bool 字段仍按上述规则填。",
    ]
    return _wrap(lpc_source, "\n".join(lines))


def build_quest_prompt(lpc_source: str, quest_id: str) -> list[dict[str, str]]:
    """QuestDef 转译 prompt（多步 objectives + time-gate）。"""
    lines = [
        f'将上述 LPC NPC 的任务交互转译为单个 QuestDef 的 YAML（顶层 dict，id="{quest_id}"）。',
        "",
        "QuestDef schema 字段：",
        "id / name / giver(NPC prototype_id，接任务 NPC) / trigger(ask 话题)",
        "description(接任务时描述) / objectives(list[QuestObjective]，多步 chain 按序完成)",
        "reward(dict: exp / flag / message / time_gate)",
        "",
        "QuestObjective.kind 取值：",
        "- give_item：给指定 NPC 指定物品。字段 npc_id + item_id",
        "- kill_npc：击杀指定 NPC。字段 npc_id",
        "- reach_room：到达指定房间。字段 room_id",
        "- fight_win：切磋击败指定 NPC（不杀死）。字段 npc_id + "
        "win_threshold(默认 50，NPC qi 百分比下限)",
        "",
        "reward.time_gate > 0：可重复任务冷却 tick 数（对照 jiamu lama_wage 工资）；0=一次性。",
        "reward.flag：完成后设的标记名（LPC set_temp marks/X）。",
        "",
        "LPC 多步任务（如 fsgelun kill->give corpse->延迟发奖 / darba fight->设标记->解锁拜师）转为"
        " objectives list。LPC 的 call_out 延迟发奖 / 分档奖励用 `# GAP:` 注释标注。",
    ]
    return _wrap(lpc_source, "\n".join(lines))


def build_room_prompt(lpc_source: str, room_id: str) -> list[dict[str, str]]:
    """RoomDef 转译 prompt。"""
    lines = [
        f'将上述 LPC 房间文件转译为单个 RoomDef 的 YAML（顶层 dict，id="{room_id}"）。',
        "",
        "RoomDef schema 字段：",
        "id / short / long / exits(dict {方向: 目标房间 id}) / objects(dict {npc_id: 数量})",
        "items(list，房间地面物品 id) / outdoors(bool) / no_fight(bool)",
        "",
        'LPC `__DIR__"xxx"` -> 同目录 xxx（去 __DIR__ 前缀，拼相对 id）。',
        'objects 的 `__DIR__"npc/xxx"` -> npc/xxx。',
    ]
    return _wrap(lpc_source, "\n".join(lines))


def build_item_prompt(lpc_source: str, item_id: str) -> list[dict[str, str]]:
    """ItemDef 转译 prompt。"""
    lines = [
        f'将上述 LPC 物品文件转译为单个 ItemDef 的 YAML（顶层 dict，id="{item_id}"）。',
        "",
        "ItemDef schema 字段：id / name(中文名) / aliases(list 别名)",
        "",
        "LPC set_name(中文名, ({别名数组})) -> name + aliases。",
    ]
    return _wrap(lpc_source, "\n".join(lines))
