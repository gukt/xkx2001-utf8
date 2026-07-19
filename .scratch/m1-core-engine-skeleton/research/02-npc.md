> 本文是 2026-07-19 M1 扩展调研的**原始 subagent 输出**（NPC 系统调研员），完整保留，未做二次精简。汇总与 scope 决策见 [../research-m1-extension-items-npc-nature.md](../research-m1-extension-items-npc-nature.md)。
>
> 立场：LPC 是设计灵感与术语参考，不是规格源（ADR-0001）。

---

两个调研都已完成。我现在掌握了：LPC NPC 系统全貌 + 源码验证纠正 + 当前 M1 引擎实际状态。可以产出报告了。

# NPC 系统调研报告：为 M1 scope 决策提供输入

## 1. NPC 系统全景

LPC《侠客行》的 NPC 系统核心设计思想是 **"NPC 与玩家角色共用同一套继承基类 CHARACTER，靠 attitude/inquiry/chat_msg 等声明式属性 + 钩子函数表达个性"**。`char.c` 通过混入 14 个 feature（F_ATTACK/F_DAMAGE/F_SKILL/F_CONDITION/F_MOVE/F_DBASE/F_NAME/F_MESSAGE/F_COMMAND/F_ATTRIBUTE/F_FINANCE/F_TEAM/F_APPRENTICE/F_ACTION 等）构建出完整角色能力，`npc.c` 只是在其上薄薄叠加 `carry_object/random_move/chat/return_home/accept_fight/accept_kill` 等 NPC 专属方法。玩家与 NPC 唯一的硬性区别是 `interactive()`（是否有真实连接）和 `userp()`（是否玩家对象）两个 driver 判定，行为驱动逻辑（心跳循环、战斗、恢复）完全共用。

**对新引擎 ECS 的关键启发**：这正是 ECS 天然能表达的模型--"角色通用能力"做成可挂载的组件集合（`Health`/`Stats`/`Position`/`Container`/`Combat`/`SkillSet`...），玩家与 NPC 挂同一批组件，区别只在是否挂 `PlayerSession`/`AIController` 这种"驱动源"组件。LPC 里 feature = ECS 里的组件，`inherit` 链 = 组件组合预设。这意味着新引擎不需要"NPC 类继承 Player 类"这种 OOP 层级，玩家和 NPC 是同一套实体 + 不同组件组合。

另一个关键启发是 **NPC 行为统一由 `chat()` 调度**：闲话、战斗喊话、随机移动、随机施法都靠把字符串或函数指针塞进 `chat_msg`/`chat_msg_combat` + 一个概率值触发，由 `heart_beat` 每拍轮询。这是一种非常"声明式 + 钩子"的 DSL--和新引擎"YAML 声明式 + 受限 Python 钩子"的 DSL 方向高度一致。

## 2. 核心功能点清单（12 维度）

### 维度 1：NPC 继承链与 feature 共用

- **出处**：`inherit/char/char.c`（CHARACTER，14 个 F_*）、`inherit/char/npc.c`（NPC）、`inherit/char/trainee.c`（TRAINEE 野兽/坐骑）、`inherit/char/master.c`（师父，仅 `prevent_learn`）。源码验证：**`living.c` 不存在**，"living" 是 driver efun 状态（`enable_commands`/`disable_commands`），不是独立类。
- **关键机制**：继承链 `CHARACTER -> NPC -> TRAINEE`；NPC 与玩家共用全部 14 个 feature；NPC 专属方法 `carry_object/add_money/return_home/random_move/chat/cast_spell/exert_function/perform_action/accept_fight/accept_kill/attempt_apprentice/accept_object`（后两个是钩子，基类不提供默认实现）。
- **对新引擎启发**：玩家与 NPC 共用组件池，靠"是否挂 AIController/PlayerSession"区分驱动源；NPC 专属能力做成可选组件（如 `Vendor`/`QuestGiver`/`Tameable`/`Instructor`）按需挂载，而不是建 NPC 子类。

### 维度 2：NPC 属性

- **出处**：`feature/dbase.c`（F_DBASE 路径式键值存储）、`feature/attribute.c`（F_ATTRIBUTE 四大属性 + 运气 + 容貌）、`feature/damage.c`（气血/精神/精力/内力）。
- **关键机制**：角色通用属性 `str/int/con/dex/kar/per`（先天）+ `max_qi/max_jing/max_neili/max_jingli`（上限）+ `qi/eff_qi/jing/eff_jing/jingli/neili`（当前值与有效上限，分两层）+ `shen`（善恶值）+ `combat_exp/potential/behavior_exp`（经验与潜能）+ `age/gender`。NPC 专属属性 `attitude`（peaceful/friendly/aggressive/killer/heroism）+ `chat_chance/chat_msg`（+ 战斗版 `_combat`）+ `inquiry`（话题映射）+ `vendetta_mark`（世仇标记）+ `family`（门派）+ `startroom`（出生房间）+ `vendor_goods`（商品清单）。
- **对新引擎启发**：属性分"通用角色属性"（玩家 NPC 共用，做成 `Stats`/`Vitals` 组件）与"NPC 专属行为参数"（做成行为组件的字段，如 `AIController.disposition`、`ChatterTable.messages`）。LPC 用一个 dbase mapping 全塞（路径式 `family/family_name`），新引擎应该用强类型 dataclass 组件替代，避免键值地狱。

### 维度 3：NPC AI 驱动（heart_beat 与 chat 调度）

- **出处**：`char.c::heart_beat()`（每秒一拍）+ `npc.c::chat()`（NPC 行为总调度器）。
- **关键机制**：`heart_beat` 是模板方法：清理计数 -> 上限检查 -> 濒死/昏迷判定 -> 战斗（busy 优先推进，否则检查逃跑后 `attack()`）-> **非玩家调 `chat()`** -> `tick` 变量引入 5~15 秒慢速周期跑 `update_condition`/`heal_up` -> 无玩家时 `set_heart_beat(0)` 省电。`chat()` 同时管"自动恢复"（内力 > 100 时按比例调 `force` 的 refresh/recover/regenerate）和"随机行为"（按 `chat_chance` 概率抽 `chat_msg` 一条，字符串则 `say`，函数指针则 `evaluate`）。**关键陷阱**：`chat()` 可能 `destruct(this_object())`，调用后必须检查对象存在。
- **对新引擎启发**：M1 的 `TickLoop` 已就绪且明确预留了"NPC 行为决策挂载到这个循环"的位（见现状核查）。LPC 的"心跳 + chat() 调度 + 概率 + 函数指针"模型可平移为：tick 循环遍历挂了 `AIController` 的实体，按其 `behaviors` 列表逐个 `tick(context)`，每个 behavior 自带概率/冷却/条件判定。LPC 的 `tick` 慢速周期（5~15 秒跑 condition/heal）对应"不同行为不同 tick 频率"的设计，新引擎可用 `period` 字段表达。

### 维度 4：NPC 行为类型全量

- **出处**：`npc.c::random_move`、`npc.c::chat`、`feature/attack.c::init`（自动攻击触发）、`feature/team.c::follow_me`、`feature/attack.c::attack/select_opponent`、`char.c::heart_beat` 逃跑分支。
- **关键机制**：
  - **随机移动**：`random_move()` 取房间 exits（人类还把门并入可选方向），遇关着的门先 `command("open dir")`，`jingli < max_jingli/2` 时停止。
  - **闲聊**：`chat_msg` 字符串或函数指针，按 `chat_chance` 概率触发；战斗中切 `chat_msg_combat`。
  - **攻击/aggro**：`feature/attack.c::init()` 在玩家进入房间时触发，三档条件--`is_killing(id)` 追杀 / `vendetta_mark` 世仇 / `attitude=="aggressive"` 主动挑衅，调 `COMBAT_D->auto_fight(me, ob, type)`。
  - **巡逻**：无独立巡逻机制，靠 `random_move` + 函数指针塞 `chat_msg` 模拟定点游走。
  - **跟随**：`team.c::set_leader` + `follow_me(ob, dir)`，带"轻功甩脱"判定（比 `move` 技能，被甩则延迟 1 拍重试）。
  - **守卫**：靠房间 `valid_leave` + NPC `set_temp("exit_blocked", dir)` 阻挡出口，或 `attitude`/`vendetta_mark` 主动攻击入侵者；少林/武当山门是 `valid_leave` 典范。
  - **逃跑**：`heart_beat` 中 `is_fighting() && wimpy_ratio > 0` 时 `GO_CMD->do_flee`。
  - **睡觉/作息**：无显式作息机制，靠 `day_shop` 房间属性 + `NATURE_D` 昼夜循环间接表达（晚上商店不开门）。
- **对新引擎启发**：行为类型应做成可组合的 `Behavior` 单元（`RandomMove`/`Aggro`/`Chatter`/`Follow`/`Guard`/`Flee`），每个带自己的触发条件与 tick 频率，YAML 里按列表声明。LPC "把函数塞进 chat_msg" 的做法 = 新引擎"行为条目里挂受限 Python 钩子"。

### 维度 5：对话系统

- **出处**：`cmds/std/ask.c`、`cmds/std/say.c`、`feature/attack.c::init` 触发对话。源码验证：**没有 `talk` 命令**，对话全走 `ask <npc> about <topic>`。
- **关键机制**：`ask` 查 NPC `query("inquiry/<topic>")`，命中则 NPC `say` 该消息；未命中按 topic 分支（名字按 attitude 回应、`here` 报房间名、其它随机回"没听说过"）。`inquiry` 值既可是字符串也可是函数指针（动态回答）。`INQUIRY_D->parse_inquiry` 是外部扩展钩子。`say` 广播给房间并触发房间内所有对象的 `relay_say(me, arg)`（NPC 可据此反应）。神龙教 `say` 彩蛋：喊特定口号词 + 独龙大法 30-100 级时提升技能。
- **对新引擎启发**：对话用"关键词 -> 响应"映射表（YAML `inquiry`），响应值支持字符串或受限 Python 钩子（对应 LPC 函数指针）。`ask` 命令格式 `ask <npc> about <topic>` 简洁，值得沿用。`relay_say` 这种"房间内对象监听 say"是事件订阅模式，新引擎可用事件总线表达。

### 维度 6：商店 NPC

- **出处**：`feature/vendor.c`（旧版/简版，仅卖固定清单）+ `feature/dealer.c`（完整版，买卖+估价+分类+库存+现金流）。源码验证关键陷阱：**`do_buy/do_sell/do_list/do_value` 是裸函数，feature 不自动注册命令**，每个 dealer NPC 必须在自己的 `init()` 里 `add_action` 手动绑定 `buy/sell/list/value`（`d/beijing/npc/dpboss.c` 是范例，`cl_huoji.c` 没写 init 故命令无效）。
- **关键机制**：商品两路--固定清单 `vendor_goods`（无库存可 `new`）+ 身上库存 `all_inventory`（带 `quantity` 计数，分 weapon/armor/book/drug/misc 五类）。定价：买入库存品 +20%（`val_factor=12`）/新品原价（`val_factor=10`），卖出/估价 70% 折扣，单笔上限 100 万。现金流走 `MONEY_D->player_dealer_pay`（找不开会失败）。拒收暗器/食物/少林庙产/`no_drop`/`no_sell`。`busy` 临时标记防刷，1 拍冷却。`day_shop` 房间晚上不开门。
- **对新引擎启发**：商店 NPC = `Vendor` 组件（商品清单 + 定价策略 + 库存 + 拒收规则）。命令注册的"手动 init"陷阱在新引擎里不存在--命令是全局注册表，NPC 挂 `Vendor` 组件即自动获得 `buy/sell/list/value` 命令的可用性。定价的"库存品加价 / 新品原价 / 卖出七折"是通用经济规则，可做成可配置策略字段。

### 维度 7：任务 NPC

- **出处**：`cmds/std/give.c::accept_object`（任务道具触发）+ `clone/npc/suicong.c`（随从/刺客 NPC，`F_SAVE` 持久化 + `call_out` 链驱动刺杀任务）+ `feature/apprentice.c`（师徒关系数据结构）+ `cmds/skill/apprentice.c`(=`bai`)/`recruit.c`(=`shou`)（双向 pending 握手收徒）。
- **关键机制**：任务触发四路--(a) `accept_object(me, obj)` 钩子（玩家 give 特定物品，如野狗接骨头后 `set_leader`）；(b) `init()` 条件触发；(c) `call_out` 链定时任务（随从寻敌 `find_player` + `move` 到目标房间 + 战斗）；(d) `ask` 查 `inquiry`。师父 NPC 自定义 `attempt_apprentice(ob)` 钩子决定收不收。`master.c::prevent_learn` 只管"教不教"（非嫡传弟子且师父技能 ≤ 徒弟 3 倍时拒教）。任务状态机靠 temp 属性（`cisha_task/cisha_target_id/cisha_result`）。
- **对新引擎启发**：任务 NPC 的核心是"钩子 + 状态机"。新引擎可预留 `QuestGiver` 组件 + `accept_object`/`on_ask`/`on_give` 等事件钩子点，状态机用受限 Python 表达。LPC 的 `call_out` 链 = 新引擎的 tick 调度 + 状态机推进。一次性 vs 可重复任务靠 NPC reset 后状态恢复（见维度 10）。

### 维度 8：守卫/门派 NPC

- **出处**：`d/shaolin/shanmen.c`/`d/wudang/shanmen.c`（房间 `valid_leave` + NPC 配合）、`feature/attack.c::init`（`attitude`/`vendetta_mark` 主动攻击）、`cmds/std/block.c`（阻挡出口）。
- **关键机制**：守卫靠两层--房间 `valid_leave(me, dir)` 检查（少林：女性禁入 + 外客放下兵刃；武当：杀气重者 `shen < -99` 禁入除非敬香）+ 守卫 NPC `attitude`/`vendetta_mark` 在 `init()` 主动攻击入侵者。守卫 NPC 还会 `set_temp("exit_blocked", dir)` 阻挡出口。喊话报警靠 `message_vision` + 房间内对象感知。
- **对新引擎启发**：守卫是"房间出口校验 + NPC 主动行为"的组合，不是单一组件。新引擎里门派守卫可由房间 `on_leave` 钩子 + NPC `Aggro` 行为（条件：目标门派不符/善恶值超阈值）共同实现。`vendetta_mark` 这种"阵营敌对"是通用概念，可做成 `Faction` 组件 + 敌对关系表。

### 维度 9：跟随者/宠物

- **出处**：`feature/team.c`（`set_leader`/`set_lord`/`follow_me`/队伍）+ `inherit/char/trainee.c`（野兽/坐骑基类，`train_it` 累积训练点过 100 后 `set_lord`+`set_leader` 认主跟随）。
- **关键机制**：`leader`（跟随目标，禁止自指）+ `lord`（主人/驯服者）+ `team`（队伍数组，共享同一引用）。`follow_me(ob, dir)` 仅当 `ob==leader` 或本对象是 `pursuer` 且追杀 ob 时跟随，带轻功甩脱判定。`trainee.c` 提供 `gen`(跟随)/`yao`(咬人)/`ting`(停下)/`fang`(放生)/`zhi`(停止攻击) 等驯兽命令，全部校验 `query_lord()==ob` 才听指挥。忠诚度靠 `training_pts` 累积。
- **对新引擎启发**：跟随 = `Follower` 组件（`leader`/`lord` 引用）+ `Follow` 行为（监听 leader 移动事件）。忠诚度可做成 `Loyalty` 组件的字段。驯兽命令是"有 `Tameable` 组件才可用的命令"，新引擎命令系统可按组件存在性 gate 命令可用性。

### 维度 10：NPC spawn 与重生

- **出处**：`inherit/room/room.c::reset()` + `make_inventory()` + `feature/clean_up.c` + `feature/unique.c`。源码验证：`unique.c::violate_unique()` 若本对象是 clone 且已有其他 clone 则返回 1，`create()` 里立即 `destruct`--全局唯一。
- **关键机制**：房间 `set("objects", ([ "/path/npc": 数量 ]))` 声明。`reset()` 逻辑：清理非 character/非 `no_refresh` 的克隆物品 -> 遍历 objects 配置，数量=1 是唯一 NPC（不存在则 `make_inventory`，存在但离开了房间则调 `return_home` 召回，召回失败则 `no_clean_up++` 防过早清理）-> 数量>1 是多实例 NPC（按缺失数补）。`make_inventory` 设 `startroom`；`/kungfu/class/` 下唯一 NPC 双重防重复克隆。`clean_up` 对 interactive 对象/在容器内的对象不清理。
- **对新引擎启发**：spawn 与重生是新引擎必须设计的机制。LPC 的"数量=1 唯一召回 / 数量>1 补齐"是通用模式，可做成房间 `npcs` 列表声明 + reset 时校验数量并补齐/召回。`startroom` 概念值得沿用--NPC 记住出生房间，reset 时 `return_home`。新引擎的"reset 周期"可挂到 tick 循环（如每 N tick 跑一次 reset 扫描）。

### 维度 11：NPC 与物品（装备/掉落/给予）

- **出处**：`feature/equip.c`（`wear`/`wield`/`unequip`，按 `armor_type` 分类型，主手/副手/双手武器，`apply` 临时属性加成）+ `char.c::die`（`CHAR_D->make_corpse`）+ `npc.c::carry_object/add_money` + `cmds/std/give.c::accept_object`。
- **关键机制**：NPC 通过 `carry_object(file)` 持有物品（武器护甲），可 `wield`/`wear` 装备获得属性加成。死亡时 `CHAR_D->make_corpse` 生成尸体对象（设名称/描述/重量），死者物品转移到尸体，玩家可从尸体 loot。`give` 给 NPC 物品时调 `accept_object` 钩子，NPC 接收有 `value` 的物品直接 `destruct`（不囤道具，只认钱/任务物）。`add_money` 创建货币对象并设堆叠数。
- **对新引擎启发**：NPC 装备 = `Container` 组件（持有物品）+ `Equipment` 组件（装备槽与属性加成）。死亡掉落 = `Death` 事件钩子生成尸体实体（挂 `Container` 装着死者物品 + `Identity` 尸体描述）。M1 已有 `Container` 给物品用，NPC 可复用同一组件。装备系统较重，建议延后。

### 维度 12：NPC 死亡

- **出处**：`char.c::die`/`unconcious` + `feature/damage.c` + `CHAR_D::make_corpse`。
- **关键机制**：`die()` 流程--不死房间处理 -> 清除状态 -> `COMBAT_D->announce("dead")` -> 死亡惩罚（玩家：减经验/潜能/存款、清 vendetta；NPC 无惩罚）-> 记录杀手 + `killer_reward` -> `make_corpse` 生成尸体移入房间 -> 清除敌人 -> **玩家变鬼魂移到 DEATH_ROOM 走死亡流程，NPC 直接 `destruct(this_object())`**。`unconcious`（昏迷）是中间态：清敌人 + 打断动作 + 解散队伍 + 清零属性 + 定时苏醒（`call_out("revive", random(100-con)+30)`）。
- **对新引擎启发**：NPC 死亡 = 销毁实体 + 生成尸体实体 + 触发奖励钩子。LPC "NPC 死直接 destruct，玩家变鬼魂" 的差异 = 新引擎"NPC 与玩家挂不同 DeathHandler 组件"。死亡轮回（CLAUDE.md 标注 MVP 必做、推 M2）依赖战斗系统，M1 不应触碰。

## 3. 与其他系统的关联点

- **物品系统**：NPC 持有装备（`Container`+`Equipment`）、死亡掉落尸体（`Death` 钩子）、give 触发 `accept_object`。M1 已有 `Container`，可复用。
- **战斗系统**：`F_ATTACK`+`F_DAMAGE`+`COMBAT_D`，NPC 的 `attitude`/`vendetta_mark`/`accept_fight`/`accept_kill` 全部挂在战斗上。ADR-0004 已拍板战斗结算框架归引擎、效果生命周期归引擎，但战斗/状态/死亡轮回推 M2。**这是 NPC"有行为"的最大前置依赖**--主动攻击/逃跑/受伤都依赖战斗。
- **状态系统**：`F_CONDITION`（中毒/盲/封招式等），`update_condition` 在心跳慢速周期跑。NPC 也吃状态。推 M2。
- **门系统**：M1 已完成门与动态出口。NPC 守卫与 `valid_leave`/`exit_blocked` 直接联动门，且 `random_move` 会开门。这是 M1 已有能力可立即用的关联点。
- **任务系统**：`accept_object`/`inquiry`/`call_out` 链。任务 NPC 是 MVP 必做子系统（02 号票），但任务框架本身复杂，建议拆出独立里程碑。
- **经济系统**：`F_FINANCE`+`MONEY_D`+`F_DEALER`。商店 NPC 依赖货币与定价。MVP 标注"货币/账本抽象"是商业化支撑点但不强制 M1 实现。
- **心跳/Nature**：`NATURE_D` 昼夜循环驱动 `day_shop`（晚上不开门）、户外房间天气描述、日出自动存档。NPC 作息靠 Nature 间接表达。M1 的 `TickLoop` 是单心跳，尚未接 Nature 概念。

## 4. M1 scope 建议

### 当前基线（已确认）

M1 当前 NPC 是**纯静态展示型**：`Identity`+`Description`+`Position` 三个组件，只能被 `look` 看到名字，无任何交互命令（ask/say/kill/give/buy/sell 全缺），无 `Behavior`/`Timer`/`Stats`/`Combat` 等行为组件，`TickLoop` 已落地但只承载存档（`tick.py` 注释口头预留"NPC 行为挂载点"，无代码）。

### M1 必做（地基 + 轻量可见行为）

1. **行为机制地基组件**：新增 `Behavior`（行为列表 + 调度元数据）与 `AIController`（驱动源标记 + tick 频率）组件骨架，挂到 `TickLoop`。**不实现战斗相关行为**，但把"tick 遍历挂 AIController 的实体、逐个 behavior.tick(context)"的骨架搭起来。这是 LPC `heart_beat`+`chat()` 模型的 ECS 平移，也是后续所有 NPC 行为的承载点，M1 不做会债留 M2。

2. **NPC 生成/重生地基**：在场景 YAML 的 `npcs` 段基础上，加 `count`（数量）+ `respawn`（是否重生）+ `startroom` 记忆，挂一个轻量 `Spawn`/`Reset` 扫描到 tick 循环（低频，如每 50 tick）。LPC 的"唯一召回 / 多实例补齐"模式。M1 NPC 不死所以不触发重生，但**机制地基**先埋好，M2 接战斗时直接用。

3. **`ask` 对话命令 + `inquiry` 映射**：这是 NPC 交互的"最低门槛可见价值"--玩家能 `ask <npc> about <topic>` 触发预设对话。不依赖战斗/状态/物品，纯文本 + 关键词匹配，工作量小但让 NPC 从"摆设"变"可交互"。响应值支持字符串与受限 Python 钩子（对应 LPC 函数指针）。

4. **`say` 命令 + 房间事件广播**：`say` 广播给同房间实体，触发 `on_hear_say` 钩子（对应 LPC `relay_say`）。这是"NPC 监听环境"的地基，后续 NPC 反应/任务触发都靠它。

5. **`Behavior` 组件的第一个实现：`Chatter`（闲聊）**：LPC `chat_msg`+`chat_chance` 的直接平移。NPC 按概率在 tick 时 `say` 预设消息。这是**唯一一个不依赖战斗/状态/物品、纯靠 tick+文本就能让 NPC"活起来"的行为**，是 M1 引入"有行为 NPC"的最小可信切片，也是 DSL 动态规则的天然试金石。

### M1 可选（看 token 余量，做了提升体感但不阻塞 M2）

- **`random_move` 行为**：NPC 随机走房间出口，遇门尝试开门。M1 已有门与移动机制，接起来不难，能让世界更生动。但会让 NPC 离开出生房间，需要 `return_home`/reset 召回配合。
- **`give` 命令 + `accept_object` 钩子**：玩家给 NPC 物品触发钩子。为任务 NPC 预留入口，但任务框架本身不在 M1。
- **`Disposition`/`Faction` 组件骨架**：把 LPC `attitude`/`vendetta_mark`/`family` 抽象成可挂载组件，字段先定下来，行为（主动攻击）留 M2 接战斗时实现。

### 延后 M2+（依赖战斗/状态/死亡轮回，M1 碰了就是越界）

- **战斗相关全部行为**：`Aggro`/`attack`/`accept_fight`/`accept_kill`/`flee`/`perform_action`/`cast_spell`。ADR-0004 战斗边界已拍板但战斗结算推 M2，M1 实现这些就是抢占 M2 工作且无战斗系统可挂。
- **商店 NPC（`Vendor`/`buy`/`sell`/`list`/`value`）**：依赖货币/定价/库存，MVP 标注货币是商业化支撑点不强制 M1。
- **任务 NPC 框架**：`QuestGiver`/`call_out` 链/状态机。任务子系统复杂，独立里程碑更合适。
- **师父 NPC（收徒/教技能）**：依赖技能系统（M2+）。
- **跟随者/宠物（`Tameable`/`Follow`/`train_it`）**：依赖战斗指令（`yao`/`attack`）与忠诚度，M2+。
- **守卫主动攻击**：依赖战斗。但守卫的"房间出口校验"部分（`valid_leave` + 阻挡出口）M1 已有门机制可部分支撑，可做"静态守卫挡路"轻量版。
- **NPC 死亡/尸体/掉落**：依赖死亡轮回（M2+）。
- **装备系统**：依赖物品装备槽与属性加成，M2+。

### 关于"M1 是否值得引入有行为的 NPC"的明确倾向

**倾向：M1 引入"轻量行为 NPC"，但严格限定在"不依赖战斗/状态/死亡"的行为子集。** 理由：

1. **心跳循环已就绪是最大机会**：LPC NPC 行为的根是 `heart_beat`+`chat()`，M1 的 `TickLoop` 正好是它的 ECS 对应物且明确预留了挂载位。现在不接，M2 接战斗时还要回头改 tick 架构，不如现在就把"tick 遍历 AIController 实体 + behavior.tick"骨架搭好，让战斗行为 M2 直接挂上。
2. **"有行为"的最小可信切片存在且不越界**：`Chatter`（闲聊）+ `ask` 对话 + `say` 广播，这三个组合能让 NPC 从"摆设"变"可交互且会说话"，工作量小、不碰战斗、不碰状态、不碰死亡，完全在 M1 边界内。这是验证"行为机制地基 + DSL 动态规则"的最小闭环。
3. **DSL 动态规则的试金石**：NPC 闲聊与对话触发是"YAML 声明式 + 受限 Python 钩子"DSL 的第一批真实用例（见第 5 节草稿）。M1 不做，DSL 设计就是纸上谈兵；M1 做了，能拿真实用例验证 DSL 形状，为 M3 UGC 创作层铺路。
4. **不做的代价**：若 M1 保持纯静态展示型，M2 开工时 NPC 系统要从零搭行为地基，与战斗/状态/死亡并行推进，风险叠加。现在埋地基，M2 只需"挂战斗行为"而非"先搭地基再挂战斗行为"。

**不建议 M1 做的边界**：任何需要 `Health`/`Stats`/`Combat` 组件的行为（攻击/逃跑/受伤/死亡），因为战斗/状态/死亡轮回明确推 M2，M1 实现这些就是抢占 M2 且无系统可挂。

## 5. DSL 动态规则表达（YAML 声明式 + 受限 Python 钩子）

LPC NPC 的"动态规则"需求集中在四类：**时间相关**（夜里睡觉/晚上不开门）、**阵营相关**（守卫见敌对就攻击）、**对话触发**（问特定词触发剧情）、**关系相关**（商人按好感度调价）。LPC 用函数指针塞进 `chat_msg`/`inquiry`/`init` 表达。新引擎用"YAML 声明结构 + 受限 Python 钩子点"。

### 草稿示意 1：NPC 闲聊 + 时间作息（`Chatter` 行为 + 钩子）

```yaml
npcs:
  innkeeper:
    name: 客栈掌柜
    in_room: inn_lobby
    behaviors:
      - kind: chatter
        period: 30  # 每 30 tick 评估一次
        chance: 40  # 40% 概率开口
        messages:
          - "掌柜正在柜台后算账。"
          - "掌柜抬头看了你一眼，又低下头去。"
        # 受限 Python 钩子：按时间过滤消息（声明式表达不了的动态逻辑）
        when: |
          ctx.nature.is_daytime()
        # 夜里换一套消息
        messages_night:
          - "掌柜打了个哈欠，眼皮直打架。"
          - "掌柜嘟囔着：天黑了，该打烊了。"
        when_night: |
          not ctx.nature.is_daytime()
```

**设计点**：YAML 声明 `messages`/`chance`/`period` 是声明式可静态校验的部分；`when` 钩子是受限 Python（访问 `ctx.nature`/`ctx.world`/`ctx.self` 等受控上下文），表达"夜里换消息"这种声明式写不干净的逻辑。对应 LPC 把函数指针塞进 `chat_msg`。

### 草稿示意 2：对话触发剧情（`ask` + `inquiry` + 钩子）

```yaml
npcs:
  old_beggar:
    name: 老乞丐
    in_room: city_square
    inquiry:
      武功:
        response: "老乞丐摇头：我哪会什么武功。"
      酒:
        response: |
          ctx.say("老乞丐眼睛一亮：你若有酒，我便教你三招。")
          if ctx.player.has_item("酒葫芦"):
              ctx.say("老乞丐接过酒葫芦，灌了一大口。")
              ctx.set_flag("taught_beggar", True)
              ctx.say("老乞丐：好！这三招你看好了……")
              ctx.player.grant_skill("beggar-fist", 1)
          else:
              ctx.say("老乞丐叹气：没酒不教。")
      # 默认 fallback
      _default:
        response: |
          ctx.say(f"老乞丐嘟囔：{ctx.topic}？我没听说过。")
```

**设计点**：`response` 既可是字符串（声明式），也可是多行受限 Python（钩子，访问 `ctx.say`/`ctx.player`/`ctx.set_flag`/`ctx.player.grant_skill` 等受控 API）。对应 LPC `inquiry` 的函数指针。`_default` 对应 LPC `msg_dunno`。这是"NPC 被问特定词触发剧情"的 DSL 表达--任务 NPC 的核心模式。

### 草稿示意 3：守卫见敌对阵营攻击（阵营 + 条件行为，M2 实现但 DSL 形状先定）

```yaml
npcs:
  shaolin_guard:
    name: 少林武僧
    in_room: shaolin_shanmen
    faction: shaolin
    stats:  # M2 才挂
      max_qi: 2000
      attack: 80
    behaviors:
      - kind: aggro
        # 受限 Python 钩子：判断是否敌对
        target_filter: |
          ctx.other.faction in ctx.self.hostile_factions
          or ctx.other.shen < -100  # 邪恶值过低
        on_trigger: |
          ctx.say(f"少林武僧对{ctx.other.name}喝道：邪魔外道，休想闯山！")
          ctx.combat.start_combination(ctx.self, ctx.other)
        # 房间出口阻挡（M1 已有门机制，可现在做静态版）
      - kind: guard_exit
        direction: eastup
        block_message: "少林武僧挡住去路：放下兵刃方可上山。"
        # 放行条件钩子
        allow_when: |
          ctx.player.faction == "shaolin"
          or (ctx.player.gender != "female" and not ctx.player.has_weapon())
```

**设计点**：`target_filter`/`on_trigger`/`allow_when` 都是受限 Python 钩子，访问受控上下文（`ctx.other.faction`/`ctx.self.hostile_factions`/`ctx.player`/`ctx.combat`/`ctx.nature`）。声明式部分（`kind`/`direction`/`block_message`/`faction`）可静态校验与编辑器高亮，钩子部分是逃生舱。对应 LPC `init()` 里的三档条件判定（`is_killing`/`vendetta_mark`/`attitude`）+ 房间 `valid_leave`。这个例子明确标注 M2 实现，但 DSL 形状先定下来，让 M1 的 `ask`/`say`/`chatter` 与 M2 的 `aggro`/`guard_exit` 用同一套钩子模型，避免 M2 推翻 DSL。

### DSL 设计原则提炼（贯穿三例）

1. **声明式优先**：`kind`/`messages`/`chance`/`period`/`faction`/`direction` 等结构化字段用 YAML，可静态校验、可编辑器高亮、可版本管理。
2. **钩子逃生舱**：`when`/`response`（多行）/`target_filter`/`on_trigger`/`allow_when` 是受限 Python，访问受控 `ctx` 上下文（`ctx.world`/`ctx.self`/`ctx.player`/`ctx.other`/`ctx.nature`/`ctx.combat`/`ctx.say`/`ctx.set_flag` 等白名单 API），沙箱执行。对应 LPC 函数指针。
3. **统一钩子模型**：所有行为（M1 的 chatter / M2 的 aggro / M3 的 quest）共用同一套"YAML 声明 + Python 钩子"形状，避免每类行为重新设计 DSL。这是从 LPC `chat_msg` 既装字符串又装函数指针得到的最大启发。
4. **能力按组件 gate**：NPC 挂 `Chatter` 才有闲聊，挂 `Inquiry` 才能被 ask，挂 `Vendor` 才能 buy/sell。命令可用性按组件存在性判定（LPC 的命令手动 init 陷阱在新引擎里不存在）。

---

## 关键文件路径速查

**LPC 源码（只读参考）**：
- `/Users/gukt/github/xkx2001-utf8/inherit/char/char.c`（CHARACTER 基类，14 个 feature，`heart_beat`）
- `/Users/gukt/github/xkx2001-utf8/inherit/char/npc.c`（NPC 专属方法，`chat`/`random_move`/`accept_fight`）
- `/Users/gukt/github/xkx2001-utf8/inherit/char/master.c`（师父，仅 `prevent_learn`）
- `/Users/gukt/github/xkx2001-utf8/inherit/char/trainee.c`（野兽/坐骑）
- `/Users/gukt/github/xkx2001-utf8/feature/attack.c`（战斗 + `init` 自动攻击）
- `/Users/gukt/github/xkx2001-utf8/feature/damage.c`（伤害/死亡/恢复）
- `/Users/gukt/github/xkx2001-utf8/feature/vendor.c` + `/Users/gukt/github/xkx2001-utf8/feature/dealer.c`（商店）
- `/Users/gukt/github/xkx2001-utf8/feature/team.c`（跟随/队伍）
- `/Users/gukt/github/xkx2001-utf8/feature/unique.c`（唯一 NPC）
- `/Users/gukt/github/xkx2001-utf8/feature/apprentice.c`（师徒数据结构）
- `/Users/gukt/github/xkx2001-utf8/cmds/std/ask.c`、`say.c`、`kill.c`、`give.c`
- `/Users/gukt/github/xkx2001-utf8/adm/daemons/chard.c`（`make_corpse`）

**拆解文档（已整理提炼）**：
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/04-对象与继承体系.md`
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/13-NPC-AI与行为系统.md`
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/05-世界构建系统.md`（reset/objects 放置）
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/03-命令系统.md`
- `/Users/gukt/github/xkx2001-utf8/docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/02-守护进程系统.md`（CHAR_D/COMBAT_D/MONEY_D）

**当前 M1 引擎（待 M1 决策落地后改动）**：
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/components.py`（当前仅 Identity/Description/Position/Exits/Doors/Container）
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/tick.py`（`TickLoop`，已落地存档，预留 NPC 行为挂载位）
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/commands.py`（11 命令，无 ask/say/kill/give/buy/sell）
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/scene_loader.py`（`_build_npcs` 纯静态展示型）
- `/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/save.py`（全量 JSON 存档，NPC 已可存）
- `/Users/gukt/github/xkx2001-utf8/engine/data/m1_default_scene.yaml`（`npcs` 段，当前仅 `stone_guard` 一个 NPC）

## 核心结论一句话

**M1 应引入"轻量行为 NPC"**：搭 `Behavior`/`AIController` 组件骨架接到已就绪的 `TickLoop`，落地 `ask`/`say`/`Chatter` 三个不依赖战斗/状态/死亡的最小行为切片（NPC 会说话、可对话、按概率闲聊），同时把 `Spawn`/`Reset`/`startroom` 重生地基埋好。战斗/商店/任务/守卫主动攻击/死亡等依赖战斗或状态系统的行为严格推 M2+。这样既利用了已就绪的心跳循环、又为 DSL 动态规则提供了第一批真实用例、还把 M2 的行为地基提前埋好避免债留。
