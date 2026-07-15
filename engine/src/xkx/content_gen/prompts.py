"""LLM prompt 模板（ADR-0036）：从 LPC 规格源生成层0 DSL 初稿。

grounded in ``07-agent-schema-mapping``（LPC -> schema 字段映射 + map_skill 推断
三规则 + 三类偏差陷阱）。目标：降低 ADR-0004 三类偏差，修订量 <40%（kill criteria 5）。

第 3 轮强化（kill criteria 5 第 3 轮）：针对第 2 轮 v0 四类高频错误强化--
id 引用规范 / quest 结构（trigger 单值 + objectives 完整）/ 文本字段单行 /
gender 中文 + ANSI 清洗。
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
    "- 函数式 inquiry（LPC (:func:)）取函数内 say/write 文本转静态字符串；若函数内有"
    " give/take 物品或 set/clear flag 等副作用，用结构化 ``{reply: ..., sets_flag: ..., "
    "gives_item: ..., takes_item: ...}`` 表达（M2-2 InquiryNode），不要用 `# GAP:` 标注。"
    "set_temp 其他副作用仍用 `# GAP: ...` 注释标注。",
    "",
    "id 引用规范（关键，第 3 轮强化）：所有跨实体引用必须用完整 id，"
    "禁止用 name/别名/拼音/LPC 路径前缀：",
    "  - NPC id = xueshan/npc/<name>（如 xueshan/npc/gelun1）；"
    "不是 gelun1 / ge_lunbu / 葛伦布 / /kungfu/class/xueshan/xxx / /d/xueshan/npc/xxx。",
    "  - 房间 id = xueshan/<room>（如 xueshan/dshanlu）；不是 dshanlu 或 d/xueshan/dshanlu。",
    "  - 物品 id 用英文 id（如 suyou_guan），不用中文名（酥油罐）。",
    "  - id 来源：LPC 文件名（去 .c）或 set(\"id\",...)；"
    "d/xueshan/npc/jiamu.c -> NPC id xueshan/npc/jiamu。",
    "",
    "文本字段单行（关键，第 3 轮强化）：long / message / inquiry reply / chat_msg / "
    "success_message 等 YAML 字符串字段一律单行，不用 YAML 多行（| / > / '...\\n...'）。",
    "  LPC set(\"long\",\"...\\n...\") 的换行合并为单行（直接拼或空格连），去尾部 \\n。"
    "inquiry reply 去外层引号和尾部 \\n。",
    "",
    "gender 用中文（第 3 轮强化）：男性 / 女性，不用 male / female。",
    "",
    "清洗 LPC ANSI 颜色码（第 3 轮强化）：short / long 中的 HIY / NOR / HIG / RED 等"
    "颜色标记去掉，只留纯文本（如 HIY大殿NOR -> 大殿）。",
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
        "id / name / aliases(list) / gender(中文 男性/女性，不用 male/female) / age / "
        "attitude(friendly|heroism|aggressive|peaceful)",
        "str_ / dex_ / int_ / con_ / max_qi / max_jing / max_jingli / max_neili / combat_exp",
        "skills(dict {skill: level}) / apply_attack / apply_dodge / apply_parry / "
        "apply_damage / apply_armor",
        "weapon(类别如 staff/blade/sword，无武器省略) / "
        "attack_skill(map_skill 推断招式，无武器=unarmed) / "
        "weapon_label(武器中文名，无武器=\"拳头\")",
        "chat_chance_combat / chat_msg_combat(list，每条单行) / "
        "inquiry(dict {topic: 单行 reply 字符串 或结构化 InquiryNode: {reply, sets_flag, "
        "clears_flag, gives_item, takes_item, once, next_topic}})",
        "apprentice(可选，师傅收徒配置；非师傅 NPC 省略此字段)",
        "",
        "文本字段单行（关键）：inquiry reply / chat_msg_combat / message 等字符串一律单行，"
        "去尾部 \\n 和外层引号。如 LPC say(\"葛伦布说道：...？\\n\") -> "
        "inquiry reply \"葛伦布说道：...？\"（无 \\n 无引号）。"
        "InquiryNode 的 reply 字段同样单行。",
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
        "clear_flag(剃度后清除标记) / message(单行剃度文本)",
        "  success_message(收徒成功消息，单行)",
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
        "skill_id(武学 id) / skill_type(str，LPC type() 返回值：martial/knowledge/dodge 等)",
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
        "- skill_type：取 LPC type() 返回字符串。inherit FORCE 的武学 type() 通常返回 "
        "martial（武学类型），不是 force。force 是基础技能类别（出现在 valid_enable 里），"
        "不是 skill_type。如 longxiang-banruo / xiaowuxiang inherit FORCE -> "
        "skill_type=martial（非 force）。",
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
        "id / name / giver(完整 NPC id xueshan/npc/<name>，接任务 NPC) / "
        "trigger(单值字符串，玩家 ask 的一个话题关键词)",
        "description(接任务时描述，单行) / "
        "objectives(list[QuestObjective]，多步 chain 按序完成)",
        "reward(dict: exp / flag / message / time_gate)",
        "",
        "giver id 规范（关键）：giver 是本 LPC 源文件对应的 NPC，"
        "id = xueshan/npc/<文件名去 .c>。quest_id=xueshan/quest/<name> 时 "
        "giver=xueshan/npc/<name>。禁止用 name/别名/拼音（如 葛伦布 / ge lunbu / "
        "jiamu huofo），必须用完整 NPC id（如 xueshan/npc/jiamu）。",
        "",
        "trigger 是单值字符串（关键）：玩家 ask 的一个话题关键词，不是 inquiry 话题列表。"
        "不要把 NPC 的所有 inquiry 话题都列为 trigger。如 LPC ask 话题\"供奉\" -> "
        "trigger: 供奉（单值）。",
        "",
        "QuestObjective.kind 取值：",
        "- give_item：给指定 NPC 指定物品。字段 npc_id + item_id",
        "- kill_npc：击杀指定 NPC。字段 npc_id",
        "- reach_room：到达指定房间。字段 room_id",
        "- fight_win：切磋击败指定 NPC（不杀死）。字段 npc_id + "
        "win_threshold(默认 50，NPC qi 百分比下限)",
        "",
        "objectives 完整性（关键）：多步任务必须还原完整步骤序列。"
        "分析 LPC 的 set_temp marks + accept_object + valid_leave/go 调用链，"
        "提取全部步骤（如 reach_room 到某房 -> give_item 给某 NPC 物品 -> "
        "fight_win 切磋）。不要只提取最后一步或留空 objectives。",
        "objectives 内 id 规范：npc_id=完整 NPC id（xueshan/npc/<name>），"
        "item_id=物品英文 id（如 suyou_guan，不用中文酥油罐），"
        "room_id=完整房间 id（xueshan/<room>）。",
        "",
        "reward.time_gate > 0：可重复任务冷却 tick 数（对照 jiamu lama_wage 工资 86400）；"
        "0=一次性。reward.flag：完成后设的标记名（LPC set_temp marks/X）。"
        "reward.message：单行完成消息。",
        "",
        "LPC 多步任务（如 fsgelun kill->give corpse->延迟发奖 / darba fight->设标记->解锁拜师）转为"
        " objectives list。LPC 的 call_out 延迟发奖 / 分档奖励用 `# GAP:` 注释标注。",
    ]
    return _wrap(lpc_source, "\n".join(lines))


def build_room_prompt(
    lpc_source: str,
    room_id: str,
    known_room_ids: list[str] | None = None,
    known_npc_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    """RoomDef 转译 prompt。

    known_room_ids / known_npc_ids：若提供，注入范围裁剪指令，只保留指向已知 id
    的 exits/objects，消除幻觉引用（第 4 轮强化，方向 A）。
    """
    lines = [
        f'将上述 LPC 房间文件转译为单个 RoomDef 的 YAML（顶层 dict，id="{room_id}"）。',
        "",
        "RoomDef schema 字段：",
        "id / short(去 ANSI 颜色码) / long(单行字符串) / "
        "exits(dict {方向: 完整房间 id xueshan/<room>}) / "
        "objects(dict {完整 NPC id xueshan/npc/<name>: 数量}) / "
        "items(list 物品英文 id) / outdoors(bool) / no_fight(bool)",
        "",
        "id 引用规范（关键）：所有 exit 值和 objects key 必须带 xueshan/ 前缀。",
        'LPC `__DIR__"xxx"` -> xueshan/xxx（保留 xueshan/ 前缀，不要省略）。',
        'objects 的 `__DIR__"npc/xxx"` -> xueshan/npc/xxx。',
        "禁止用 npc/xxx（缺前缀）/ /kungfu/class/xueshan/xxx / /d/xueshan/npc/xxx "
        "路径前缀，统一归一为 xueshan/npc/<name>。",
    ]
    if known_room_ids is not None and known_npc_ids is not None:
        lines.extend([
            "",
            "范围裁剪（关键，第 4 轮强化）：只保留指向以下已知 id 的 exits/objects。"
            "LPC 源码里指向范围外房间的 exit 或范围外 NPC 的 object 一律省略"
            "（不要输出不在已知列表的引用）。",
            f"已知房间 id（exits 目标只从中选，不在列表的 exit 省略）："
            f"{', '.join(known_room_ids)}",
            f"已知 NPC id（objects key 只从中选，不在列表的 object 省略）："
            f"{', '.join(known_npc_ids)}",
        ])
    lines.extend([
        "",
        "文本字段单行（关键）：long 合并 LPC 多行为单行（直接拼或空格连），去尾部 \\n，"
        "不用 YAML 多行（|/>）。short 去掉 HIY/NOR/HIG/RED 等 ANSI 颜色码，只留纯文本"
        "（如 HIY大殿NOR -> 大殿）。",
    ])
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


def build_rule_prompt(
    lpc_source: str,
    rule_id: str,
    event_type: str = "valid_leave",
) -> list[dict[str, str]]:
    """EventRule 转译 prompt（层1 事件规则 condition -> action）。"""
    lines = [
        f'将上述 LPC 事件钩子转译为单个 EventRule 的 YAML（顶层 dict，id="{rule_id}"，'
        f'event="{event_type}"）。',
        "",
        "EventRule schema 字段：",
        "id / event(valid_leave|accept_object|ask|command) / "
        "condition(Predicate) / action(deny|allow|set_flag|clear_flag)",
        "priority(int) / message(单行触发消息) / dir(方向，仅 valid_leave) / "
        "verb(命令动词，仅 command)",
        "npc_id(完整 NPC id) / item_id(物品 id) / flag(标记名) / "
        "topic(ask 话题) / spawn_items(list，仅 ask/accept_object)",
        "",
        "Predicate 结构：",
        "- kind: always | attr_lt | age_lt | present_npc | has_flag | family_eq | "
        "has_item | attr_eq | attr_in | status_eq | same_object | mud_age_lt",
        "- kind=always 时其他字段可省略；kind=attr_lt/age_lt/mud_age_lt 时用 value(int)；"
        "kind=attr_eq/status_eq 时用 value_str(str)",
        "- kind=present_npc 用 npc_id；kind=has_flag 用 flag + flag_source(query|temp，默认 query)",
        "- kind=family_eq 用 family；kind=has_item 用 item_id / item_category / item_name 三选一",
        "- kind=attr_in 用 values(list[str])",
        "- 组合谓词：all(list[Predicate]) / any(list[Predicate]) / not(Predicate)，"
        "组合节点优先于 kind",
        "",
        "spawn_items 结构：item_id / room_id / count",
        "",
        "输出要求：只输出纯 YAML（顶层 dict），不要 ``` 围栏，不要解释文字。",
    ]
    return _wrap(lpc_source, "\n".join(lines))


def build_revision_prompt(
    asset_type: str,
    asset_id: str,
    current_yaml: str,
    findings: list[str],
    rag_context: str = "",
) -> list[dict[str, str]]:
    """根据校验 finding 修订 asset YAML 的 prompt。"""
    user_lines = [
        f"请修订以下 {asset_type} `{asset_id}` 的 YAML，使其通过校验。",
        "",
        "当前 YAML：",
        "----",
        current_yaml,
        "----",
        "",
        "需要修复的问题：",
    ]
    user_lines.extend(f"- {f}" for f in findings)
    user_lines.extend([
        "",
        "约束：",
        "- 保持原有 id、类型和语义，只修问题。",
        "- id 引用必须用完整 id（房间 xueshan/<room>，NPC xueshan/npc/<name>，物品英文 id）。",
        "- 文本字段单行，不要 YAML 多行（| />）。",
        "- 只输出纯 YAML，不要 ``` 围栏，不要解释文字。",
    ])
    if rag_context:
        user_lines.extend(["", "世界圣经约束：", rag_context])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_lines)},
    ]
