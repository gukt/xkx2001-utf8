# 系统 / NPC 自动触发视角 User Stories

> 产出角色：空间/移动机制设计师。本文件覆盖「系统/NPC 自动触发」层 User Stories--即不由玩家主动输入触发、而由引擎定时器、状态机或 NPC 心跳自动驱动的世界空间层行为。每条 Story 标注 LPC 证据来源（自动触发机制 + 触发条件 + 证据文件/函数）。
>
> 格式：`US-SYS-NNN`：作为<系统/NPC 角色>，我希望<自动行为>，以便<价值>。
> 验收：源自 LPC <文件:函数>。

---

## 一、昼夜时段自动触发（Nature daemon）

### US-SYS-001：游戏时段自动循环推进
作为 Nature 守护进程，我希望游戏昼夜 8 时段按预定时长自动循环推进（dawn->sunrise->morning->noon->afternoon->evening->night->midnight->dawn...），以便世界时间感持续运转而无需人工干预。
- 触发：`call_out("update_day_phase", length)` 定时自驱动（`adm/daemons/natured.c` `update_day_phase` line 54-77，每段 length 秒后触发下一段）。
- 验收：8 段总长 1440 分钟（=现实 1440 秒=24 分钟现实）轮转一圈；每轮回到 dawn 时 `init_day_phase()` 重新同步现实时间（line 60-64）。

### US-SYS-002：时段切换时向所有户外玩家广播环境消息
作为 Nature 守护进程，我希望每次时段切换时把 `time_msg`（如「太阳从东方的地平线升起了」）推送给所有当前在户外房间的玩家，以便户外玩家实时感知时间流转。
- 触发：`update_day_phase` line 71 `message("outdoor:vision", time_msg+"\n", users())`。
- 验收：广播发给 `users()` 全服玩家，但 `feature/message.c` `receive_message` line 27-29 过滤掉非户外环境的玩家；室内玩家收不到。
- 风险/标注：推送目标是全服而非空间索引，1000 在线即 1000 次 receive 调用（性能评审关注点）。

### US-SYS-003：日出时自动存盘全服玩家数据
作为 Nature 守护进程，我希望在 sunrise 时段自动保存所有在线玩家的数据，以便减少崩溃/掉线造成的数据丢失，且选择低活跃时段存盘降低感知。
- 触发：`natured.c` `event_sunrise()` line 83-97（day_phase 数据里 sunrise 段的 `event_fun` 字段）。
- 验收：遍历 `users()`，对每个玩家 `link_ob->save()` + `ob->save()` 双存（link_ob 与 body）。

### US-SYS-004：时段切换时清理无环境对象与物品检查
作为 Nature 守护进程，我希望每次时段切换时清理无 environment 的游离 NPC、把游离玩家移到安全房间、并对所有玩家做物品合法性检查，以便维护世界对象一致性。
- 触发：`natured.c` `event_common()` line 100-142（每次 update_day_phase 都调用，line 75）。
- 验收：① 遍历 `livings()`，无 environment 的 NPC `destruct()`、无 environment 的玩家 `move("/d/city/wumiao.c")`（武庙安全点）；② 遍历 `users()` 调 `UPDATE_D->inventory_check()` 做物品检查。
- 标注：这是「世界级 GC + 健康检查」周期任务，挂在时段切换上。

### US-SYS-005：夜间自动关闭日间商店
作为引擎，我希望在 night/midnight 时段阻止玩家进入 day_shop 标记的商店，以便模拟商店夜间打烊。
- 触发：玩家 `go <方向>` 进入 day_shop 房间时，`cmds/std/go.c` line 101-103 检查 `NATURE_D->outdoor_room_event()` 返回 `event_night`/`event_midnight` 则拒绝。
- 验收：夜间进入 day_shop 房间返回「X 晚上不开，请天亮了再来」；白天放行。
- 标注：这是「时段状态被动查询」式自动行为（非 daemon 主动推送），但效果是系统级的营业时间控制。

---

## 二、渡船周期自动触发（ferry / boat）

### US-SYS-006：渡船靠岸后自动开船离岸
作为渡口房间，我希望玩家喊船靠岸后 15 秒自动开船（撤掉登船出口），以便渡船周期不依赖玩家手动触发后续状态。
- 触发：`inherit/room/ferry.c` `check_trigger()` 里 `call_out("on_board", 15)`（line 90）-> `on_board()` 撤 `exits/enter`/`exits/out`（line 93-112）。
- 验收：玩家 `yell 船家` 后 15s，船自动「竹篙一点，扁舟向心驶去」，无法再登船。

### US-SYS-007：渡船行驶中自动抵达对岸
作为渡船，我希望开船后 20 秒自动抵达对岸并接通下船出口，以便乘客无需手动操作即可到岸。
- 触发：`ferry.c` `on_board()` 里 `call_out("arrive", 20)`（line 111）-> `arrive()` 设 `boat->set("exits/out", opposite)`（line 114-139）。
- 验收：开船后 20s 船出口接到对岸，乘客可 `go out` 下船。

### US-SYS-008：渡船到岸后自动收板离岸
作为渡船，我希望到岸 20 秒后自动收起踏脚板（撤掉下船出口）并重置 yell_trigger，以便渡船周期完整收尾、可被再次喊叫。
- 触发：`ferry.c` `arrive()` 里 `call_out("close_passage", 20)`（line 137-138）-> `close_passage()` 撤 `exits/out` + `delete("yell_trigger")`（line 141-157）。
- 验收：到岸后 20s 出口撤除，船回到可被喊叫的初始状态。

### US-SYS-009：太湖渡船自动清理与销毁
作为太湖渡船对象（动态克隆），我希望靠岸后超时无乘客时自动把残留乘客赶下船并销毁自身，以便回收动态克隆的船对象、不堆积内存。
- 触发：`d/taihu/duchuan2.c` `arriving()` 设 `call_out("auto_clean_up", 40)`（line 121）+ `call_out("arrive", 20)`；`auto_clean_up()`（line 74-114）把乘客 move 到出口后 `destruct(room)`，若仍有玩家则续 `call_out("auto_clean_up", 20)`。
- 验收：靠岸后 40s 起开始清理；无人时 destruct 船，有人则延时再清。

---

## 三、马匹 / 驯兽自动触发

### US-SYS-010：马匹体力随心跳自动检查并触发昏厥坠骑
作为马匹 NPC，我希望我的体力（jingli）被自动周期性检查，当体力耗尽时自动把骑手摔下并昏迷，以便体现坐骑疲劳的物理后果而无需骑手操作。
- 触发：`clone/horse/horse.h` `condition_check()` 注册为 `chat_msg` 函数指针（`baima.c` line 34-37 `set("chat_chance",50)` + `set("chat_msg",({ (: condition_check :) }))`）；`inherit/char/npc.c` `chat()` line 99-130 按 `chat_chance` 概率每心跳随机执行一条 chat_msg。
- 验收：jingli<=10 时骑手 `receive_wound("qi",150)` + 马匹 `unconcious()` + `set_leader(0)`（horse.h line 18-30）；jingli<=30>20 警告喘气；jingli<=max/3 早期警告。
- 标注：这是「概率触发」而非「定时触发」，挂在 NPC 心跳的 chat 调度器上。

### US-SYS-011：马匹在草地自动吃草回血
作为马匹 NPC，我希望进入有草资源的房间时自动吃草恢复体力与饱食度，以便马匹有自然回血途径。
- 触发：`horse.h` `init()`（line 42-65）--马匹进入 `query("resource/grass")` 为真的房间且未吃饱时，`add("food", max_food/4)` + `add("jingli", (max_jingli-jingli)/2)`。
- 验收：马匹在草地房间（如 `d/city/beijiao4.c`、`d/xixia/hytan.c`）自动「低下头在草地上吃起草来」并回复一半精力缺口。
- 标注：init 在马匹进入房间时触发（被动），非持续心跳。

### US-SYS-012：驯服的动物自动跟随主人移动
作为驯服的动物（马/兽），我希望主人移动时自动跟随到同一方向，以便组队行进不需主人逐个指令带领。
- 触发：`cmds/std/go.c` line 243 `all_inventory(env)->follow_me(me, arg)` 遍历同房间对象；`feature/team.c` `follow_me(ob, dir)` line 37-49 检查 `ob==leader` 或 pursuer 追杀关系，再 `follow_path(dir)` 或 `call_out("follow_path",1,dir)`。
- 验收：主人 go <dir> 后，leader==主人的动物执行 `GO_CMD->main(this_object(), dir)` 跟进；move 技能低于主人时有概率跟丢（延迟跟随）。
- 标注：跟随复用 go 命令，因此跟随者同样受 valid_leave/cost/门/负重约束。

---

## 四、船只导航自动触发（ship.c）

### US-SYS-013：海船开船后自动导航循环
作为海船，我希望玩家 `start` 开船后每 2 秒自动推进一次导航（移动、触礁检查、随机事件、靠岸判定），以便航海过程持续运转而无需玩家每步操作。
- 触发：`inherit/room/ship.c` `do_start()` 启动 `call_out("navigate", 2)`（line 106）；`navigate()`（line 112-282）末尾 `call_out("navigate", 2)` 自续（line 279）。
- 验收：每 2s 推进一格 locx/locy（按 navigate/dir）；无方向时累计 wait，>5 次沉船；靠岸或沉船时终止循环。

### US-SYS-014：海船自动触发局部天气变化
作为海船，我希望航行中自动随机生成局部天气（平静/阴/暴），以便航海环境有动态变化且暴风天气影响沉船概率。
- 触发：`ship.c` `do_start()` 启动 `call_out("shipweather", 1)`（line 104）；`shipweather()`（line 484-505）每 1s 检查 `!random(6)`->weather=1、`!random(24)`->weather=2；置非 0 后 `call_out("niceweather", 5+random(10))` 复位（line 494-499）。
- 验收：航行中 `navigate/weather` 在 0/1/2 间随机切换；`long_desc` 随天气变色（line 30-34）；暴风+远离岸时 1% 概率沉船（navigate line 135-141）。
- 标注：与全局 Nature 天气无关，是 ship.c 独立局部状态机。

### US-SYS-015：海船航行中自动触发随机海事件
作为海船，我希望航行中按低概率自动触发海怪/财宝/海盗/极光/幽灵船等海事件，以便航海有惊喜与风险。
- 触发：`ship.c` `navigate()` line 143-183 `!random(40)`（1/40）触发 `random(10)` 十种事件。
- 验收：约每 80 秒（40 次 navigate×2s）概率触发一次海事件文案；当前多数事件仅文案无实际逻辑（case 0/1/2 海怪/财宝/海盗为空注释）。

### US-SYS-016：海船超时无人操作自动沉船
作为海船，我希望玩家上船后超过 15-23 分钟无操作时自动沉船，以便回收长期占用的船对象、避免资源泄漏。
- 触发：`ship.c` `init()` line 46 `call_out("time_out", 900+random(500))`；`time_out()`（line 49-53）「狂风大作船翻了」-> `do_drop()`。
- 验收：约 900-1400 秒无操作后船自动翻沉，玩家落水昏迷被冲上岸。

### US-SYS-017：海船靠岸后自动开船离岸
作为海船，我希望靠岸 20 秒后自动把残留乘客踢下船并离岸，以便船不长期停靠、可被其他玩家从港口喊叫。
- 触发：`ship.c` 靠岸时 `call_out("do_ready", 20)`（navigate line 245/262）；`do_ready()`（line 539-590）把玩家 move 到港口、清 exits/out、港口清 exits/enterN。
- 验收：靠岸后 20s 自动踢玩家下船；荒岛（wildharbors）额外等 100s（line 549-555）。
- 变体：最后一名玩家 `go out` 下船时也触发 `call_out("do_ready", 5)`（valid_leave line 55-68）。

---

## 五、港口自动触发（harbor.c）

### US-SYS-018：港口喊船后自动调度船靠岸
作为港口房间，我希望玩家 `yell chuan` 后自动找一艘空闲海船并接通登船出口，20 秒后自动收回，以便船只调度无需人工管理。
- 触发：`inherit/room/harbor.c` `do_yell("chuan")`（line 35-94）找 `!query_temp("trigger")` 的 seaboat，设双向出口，`call_out("do_ready", 20, ship)`（line 80）；`do_ready()`（line 114-152）踢玩家下船、清出口。
- 验收：喊船后船靠岸 20s，期间可登船；超时自动离岸。
- 标注：荒岛（wildharbors）`do_yell` 直接拒绝（line 55-56），玩家无法在荒岛喊船。

---

## 六、房间/NPC 通用自动行为

### US-SYS-019：房间 reset 自动补充/召回 NPC 与物品
作为房间，我希望定期 reset 时按 `objects` 声明自动补充缺失的 NPC 与物品、召回游荡 NPC 回巢，以便世界状态自我维持。
- 触发：`inherit/room/room.c` `reset()`（line 76-155）+ `make_inventory()`（line 52-74）。reset 由 `setup()`（line 277-281）触发及定期调度。
- 验收：按 `query("objects")` mapping（`<文件>:<数量>`）补充；已存在但不在房间的 character 调 `return_home()` 召回，失败则 `add("no_clean_up",1)`；`no_refresh` 标志的对象跳过；`/kungfu/class/` 下 NPC 防多重复制（line 58-64）。
- 标注：这是「世界级 spawn/respawn」周期，与 Nature 时段无直接耦合（由 driver 的 reset 调度驱动）。

### US-SYS-020：NPC chat 心跳自动行为
作为 NPC，我希望按 `chat_chance` 概率每心跳随机执行一条 `chat_msg`（可为文案或函数指针），以便 NPC 有自主行为如马匹体力检查、随机移动、施展武功等。
- 触发：`inherit/char/npc.c` `chat()`（line 99-130）按 `chat_chance`（非战斗）/`chat_chance_combat`（战斗中）百分比概率，从 `chat_msg`/`chat_msg_combat` 数组随机执行一条。
- 验收：`chat_msg` 条目可以是字符串（文案）或函数指针（如 `(: condition_check :)`）；战斗中用 combat 变体。
- 标注：这是 NPC 自动行为的通用底座，马匹 condition_check（US-SYS-010）即基于此；也是 NPC 随机移动/施法的基础。

---

## 自动触发机制分类小结

| 自动驱动源 | 机制 | 代表 Story |
|-----------|------|-----------|
| **call_out 定时器**（一次性/自续） | 渡船周期、船只导航、时段循环、港口调度 | US-SYS-001/006-009/013/016/017/018 |
| **NPC 心跳 chat 调度**（概率触发） | 马匹体力、NPC 随机行为 | US-SYS-010/020 |
| **事件回调 event_fun**（时段切换钩子） | 存盘、清理、物品检查 | US-SYS-003/004 |
| **进入触发 init**（被动钩子） | 马匹吃草、房间进入逻辑 | US-SYS-011 |
| **移动后处理**（go.c 后置调用） | 跟随、关系清理 | US-SYS-012 |
| **被动状态查询**（非主动推送） | day_shop 夜间关门、渡船夜间门禁 | US-SYS-005/009（ferry.h 夜间） |
| **driver reset 调度** | 房间 NPC/物品补充召回 | US-SYS-019 |

> 共性风险（供后续评审）：
> 1. **call_out 串是主要自驱方式**，但无统一调度框架，每个状态机各自管 `remove_call_out`/`call_out`，易漏清导致重复调度或泄漏（ferry.c/ship.c 都有 `remove_call_out` 防重复的模式）。
> 2. **NPC 心跳 chat 是概率触发**，非确定性周期，体力检查的实际频率取决于 `chat_chance` 与心跳频率，玩家感知不可控。
> 3. **event_fun 多数是空调用**（§8.3），时段切换的实际游戏效果很少，主要为存盘+清理+户外文案。
> 4. **天气自动变化完全缺失**（§9.1），无任何全局天气自动触发机制。
