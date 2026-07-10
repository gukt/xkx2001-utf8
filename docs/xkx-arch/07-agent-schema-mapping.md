# Agent Schema 映射文档（LPC -> DSL）

> 给 Agent（LLM）的操作手册：从 LPC 规格源生成层0/层1 DSL 初稿时，按本表映射字段 + 推断 map_skill，避免 ADR-0004 三类典型偏差，目标修订量 < 20%。
>
> 关联：[ADR-0004](../adr/ADR-0004-agent-dsl-generation-s3.md) Agent 偏差度量 / [03](03-DSL-UGC与Agent协作.md) DSL 架构 / [layer0.py](../../engine/src/xkx/dsl/layer0.py) schema 定义 / [validator.py](../../engine/src/xkx/dsl/validator.py) 四道校验。

## 一、目的

[ADR-0004](../adr/ADR-0004-agent-dsl-generation-s3.md) 度量 copilot Agent 生成 DSL 初稿的语义修订量 24.5%，瓶颈是三类反复出现的偏差（字段名混淆 / map_skill 推断 / 武器 id vs 类别）。本文档固化 LPC -> schema 字段映射表 + map_skill 推断规则，供 M2 独立 LLM + Langfuse 验证，预期降修订量至 < 20%（kill criteria 5 降级线 30%）。

阶段 -1 的四道校验（[ADR-0008](../adr/ADR-0008-schema-validator-four-checks.md)，pydantic strict + 未知字段警告）可自动捕获偏差 1（neili/max_neili 类静默丢失），但偏差 2/3（map_skill / weapon 类别）需 Agent 按本文档规则推断，校验无法自动修正。

## 二、NpcDef 字段映射（LPC set() -> schema）

| NpcDef 字段 | LPC 来源 | 说明 |
|---|---|---|
| id | 文件路径（d/xueshan/npc/gelun1.c -> xueshan/npc/gelun1） | 去 d/ 前缀 + .c 后缀 |
| name | set_name(中文名, ...) 第 1 参数 | |
| aliases | set_name(中文名, {别名数组}) 第 2 参数 | |
| gender | set("gender", ...) | |
| age | set("age", ...) | |
| attitude | set("attitude", ...) | friendly / heroism / aggressive / peaceful |
| str_ | set("str", ...) | LPC str -> schema str_（避关键字） |
| dex_ | set("dex", ...) | |
| int_ | set("int", ...) | |
| con_ | set("con", ...) | |
| max_qi | set("max_qi", ...) | |
| max_jing | set("max_jing", ...) | |
| max_jingli | set("max_jingli", ...) | LPC 未设则默认 100 |
| max_neili | set("max_neili", ...) | ⚠ 偏差 1：LPC set("neili",...) 是当前值非上限，不填 |
| combat_exp | set("combat_exp", ...) | |
| skills | set_skill(skill, level) 全部 | dict: {skill: level} |
| apply_attack | set_temp("apply/attack", ...) | |
| apply_dodge | set_temp("apply/dodge", ...) | |
| apply_parry | set_temp("apply/parry", ...) | |
| apply_damage | set_temp("apply/damage", ...) | |
| apply_armor | set_temp("apply/armor", ...) | |
| weapon | carry_object(武器)->wield() 的武器类别 | ⚠ 偏差 3：填类别不填物品 id |
| attack_skill | map_skill 推断（见 §四） | ⚠ 偏差 2：不填武器类别，填推断的招式 |
| weapon_label | 武器物品中文名（set_name） | 无武器默认"拳头" |
| chat_chance_combat | set("chat_chance_combat", ...) | |
| chat_msg_combat | set("chat_msg_combat", ({...})) | list[str] |
| inquiry | set("inquiry", [...]) 静态字符串部分 | ⚠ 函数式见 §五 |

LPC 未显式 set 的字段用 schema 默认值（见 [layer0.py](../../engine/src/xkx/dsl/layer0.py)）。LPC `set("shen_type"/"class"/"score"/"jiali"/...)` 等阶段 -1 schema 未覆盖，忽略（后置阶段 0）。

## 三、RoomDef 字段映射

| RoomDef 字段 | LPC 来源 | 说明 |
|---|---|---|
| id | 文件路径 | |
| short | set("short", ...) | |
| long | set("long", ...) | |
| exits | set("exits", ([方向:目标])) | dict: {方向: room_id}；`__DIR__"xxx"` -> 同目录 xxx |
| objects | set("objects", ([npc路径:数量])) | dict: {npc_id: count}；`__DIR__"npc/xxx"` -> npc/xxx |
| outdoors | set("outdoors", 1) | bool |
| no_fight | set("no_fight", 1) | bool |

## 四、map_skill 推断规则（核心，解决偏差 2）

LPC `map_skill(base, mapped)`：把基础技能类别 base 映射到招式技能 mapped。NPC 攻击时 do_attack 用 map_skill(武器类别) 的招式作为 attack_skill。

**attack_skill 推断三规则**（按优先级）：

1. **有 map_skill(W, X) 且持武器类别 W** -> `attack_skill = X`
   - gelun1: map_skill("staff","jingang-chu") + 持法杵(staff) -> attack_skill = jingang-chu
2. **无 map_skill(W, X) 但持武器类别 W 且 W 在 skills 中** -> `attack_skill = W`
   - bing: 无 map_skill + 持钢刀(blade) + blade in skills -> attack_skill = blade
3. **无武器** -> `attack_skill = unarmed`
   - xlama2: 无 carry_object wield -> attack_skill = unarmed

**weapon 类别推断**（从武器物品文件）：
- `inherit STAFF / SWORD / BLADE / ...` 或 `init_staff / sword / blade / ...` -> 对应类别
- d/qilian/obj/fachu.c `inherit STAFF` -> weapon = staff
- d/city/npc/obj/gangdao.c `inherit BLADE` -> weapon = blade

**weapon_label 推断**：武器物品 `set_name(中文名, ...)` 的中文名。fachu -> 法杵；gangdao -> 刀。无武器默认"拳头"。

## 五、inquiry 对话映射

LPC `set("inquiry", ([topic: reply]))`：

- **静态字符串 reply**：直接转 `NpcDef.inquiry: {topic: reply}`
- **函数式 reply**（`(: func :)`）：LPC 调用函数，可能含 set_temp 副作用。阶段 -1 DSL inquiry 是纯静态字符串：
  - 取函数内 `say(...)` / `write(...)` 的文本部分转静态 reply
  - `set_temp("marks/X")` 副作用标 GAP（需 ask->action 机制，后置 S4+/阶段 0）
  - xlama2 inquiry 酥油茶 -> `(: ask_tea :)`：取 ask_tea 的 say 文本"小喇嘛一脸不耐烦：酥油那麽贵，想喝茶那能说有就有，等着！"转静态，set_temp("marks/茶") 标 GAP

## 六、三类偏差陷阱（ADR-0004）

### 偏差 1：neili / max_neili 混淆
- **错**：把 LPC `set("neili", 500)` 填进 schema `max_neili`，或误填 `neili` 字段（schema 无此字段，pydantic extra=ignore 静默丢失，四道校验 SchemaValidator 现可警告）
- **对**：schema 只有 `max_neili`（上限）。LPC `set("neili", X)` 是当前内力（初始 = max_neili），`set("max_neili", Y)` 是上限。只取 `max_neili`，忽略 `neili`
- gelun1: set("neili",500) + set("max_neili",500) -> max_neili=500（neili 忽略）

### 偏差 2：attack_skill 填武器类别
- **错**：attack_skill = staff / blade / sword（武器类别）
- **对**：attack_skill = map_skill(weapon) 推断的招式（jingang-chu / quanzhen-jian），见 §四
- gelun1: ❌ attack_skill=staff -> ✅ attack_skill=jingang-chu

### 偏差 3：weapon 填物品 id
- **错**：weapon = fachu / gangdao / changjian（LPC 物品 id）
- **对**：weapon = staff / blade / sword（武器类别，从物品 inherit/init 推断）
- gelun1: ❌ weapon=fachu -> ✅ weapon=staff；weapon_label=法杵（物品中文名）

## 七、完整示例：gelun1 LPC -> DSL

LPC d/xueshan/npc/gelun1.c 关键行：
```c
set_name("葛伦布", ({"ge lunbu","ge","lunbu"}));
set("gender","男性"); set("age",20); set("attitude","heroism");
set("max_qi",500); set("max_jing",450); set("neili",500); set("max_neili",500);
set("combat_exp",80000);
set_skill("force",50); set_skill("dodge",55); set_skill("parry",60);
set_skill("staff",60); set_skill("jingang-chu",70); set_skill("longxiang-banruo",60);
map_skill("parry","jingang-chu"); map_skill("staff","jingang-chu");
set("inquiry",(["还愿":(:do_huanyuan:),"烧香":(:do_huanyuan:),...]));
carry_object("/d/qilian/obj/fachu")->wield();
```

推断：
- weapon: fachu.c `inherit STAFF` -> staff
- attack_skill: map_skill("staff","jingang-chu") + 持 staff -> jingang-chu
- weapon_label: 法杵（fachu set_name 中文名）
- max_neili: 500（set("max_neili")，忽略 set("neili")）
- inquiry 还原/烧香/供佛: 函数式 do_huanyuan -> 取 say 文本"你拿什麽孝敬佛爷呀?"转静态

DSL（对照 [scenes/xueshan_micro/npcs.yaml](../../engine/scenes/xueshan_micro/npcs.yaml)）：
```yaml
- id: xueshan/npc/gelun1
  name: 葛伦布
  aliases: ["ge lunbu", "ge", "lunbu"]
  gender: 男性
  age: 20
  attitude: heroism
  str_: 24
  dex_: 16
  int_: 14
  con_: 22
  max_qi: 500
  max_jing: 450
  max_jingli: 300
  max_neili: 500
  combat_exp: 80000
  skills:
    force: 50
    dodge: 55
    parry: 60
    staff: 60
    jingang-chu: 70
    longxiang-banruo: 60
  weapon: staff
  attack_skill: jingang-chu
  weapon_label: 法杵
  inquiry:
    还愿: 葛伦布说道：你拿什麽孝敬佛爷呀？
    烧香: 葛伦布说道：你拿什麽孝敬佛爷呀？
    供佛: 葛伦布说道：你拿什麽孝敬佛爷呀？
```

## 八、EventRule 映射（layer1）

### valid_leave（LPC room 的 valid_leave(me,dir) 函数）
- event: valid_leave
- dir: LPC `if(dir=="north")` 的方向（空 = 全方向，向后兼容）
- condition: LPC valid_leave 的判断逻辑（用 present_npc / family_eq / has_item / has_flag 谓词 + all / any / not 组合）
- action: deny（deny-wins 语义，对齐 LPC notify_fail）
- message: deny 时的提示文本

### accept_object（LPC NPC 的 accept_object(who,ob) 函数）
- event: accept_object
- npc_id: NPC prototype_id
- item_id: LPC `ob->name()=="物品名"` 的物品
- action: set_flag（LPC set_temp("marks/X")）或 deny
- flag: set_temp 的标记名
- message: 接受/拒绝时的文本

## 九、QuestDef 映射（S4 任务系统）

对照 LPC NPC 的 ask trigger + accept_object item + set_temp marks：
- giver: 接任务 NPC 的 prototype_id
- trigger: ask 话题（LPC inquiry 触发任务的 topic，优先于普通 inquiry）
- objective.kind: give_item（S4 最小；kill_npc / reach_room 后置）
- objective.npc_id / item_id: 交付目标 NPC + 物品
- reward.exp / flag / message: 奖励经验 + 标记 + 消息

gelun1 供奉任务：ask 还愿 -> give gelun1 suyou_guan -> reward exp+flag=酥+message -> go north 放行（has_flag 替代 has_item）。

## 十、范围边界（阶段 -1）

阶段 -1 schema 子集（[layer0.py](../../engine/src/xkx/dsl/layer0.py)）：
- NpcDef 不含：jiali / score / shen_type / class / vendetta_mark / pursue 等 LPC 字段（后置阶段 0）
- 不支持：动态 inquiry 函数副作用 / accept_object 给物品 / clear_flag / call_out 定时 / 门状态机（标 GAP 后置 S4+/阶段 0）
- 完整 schema（技能 action / 物品系统 / 门状态机）后置阶段 0 / M2

## 关联

- [ADR-0004](../adr/ADR-0004-agent-dsl-generation-s3.md) Agent 偏差度量（本文档解决其 §后续 4）
- [ADR-0008](../adr/ADR-0008-schema-validator-four-checks.md) 四道校验（自动捕获偏差 1）
- [03](03-DSL-UGC与Agent协作.md) DSL 四层架构
- [06](06-阶段-1-实施计划.md) S4 实施计划
- [layer0.py](../../engine/src/xkx/dsl/layer0.py) + [layer1.py](../../engine/src/xkx/dsl/layer1.py) schema 定义

---

*创建：2026年7月10日*
