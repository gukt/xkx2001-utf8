# 世界空间层 -> engine 核心抽象方案与可选方向

> 本文件是「引擎架构师 A」产出。职责：把 LPC 世界空间层通用机制映射到**题材无关** engine 核心，输出抽象方案与**可选方向**（不止一个"正确答案"），止步于设计输入层，不落最终接口契约。
>
> 证据规则：每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。engine 模块仅作批判对照对象，不作反向脑补来源。

---

## 0. 方法论与判定标尺

判定一条机制"必须进 core / 可下沉题材包"用三条标尺：

1. **题材无关性**：换仙侠/科幻/校园题材，该机制是否仍成立且语义不变？成立->偏向 core。
2. **正交复用度**：该机制是否被多个子系统复用（Nature 广播、战斗、任务、UGC）？复用面越广越偏 core。
3. **UGC 安全性**：若交给题材包自由实现，是否会破坏引擎不变量（单进程单 World、存档一致性、房间拓扑可达性）？破坏风险高->core 必须收口。

不满足以上任一条->倾向下沉题材包（通过 hook/组件/数据声明）。

---

## 1. 房间 / 拓扑 / 出口 / 门 的最小核心集

### 1.1 LPC 原始形态（证据）

- `inherit/room/room.c:227` `create_door(dir, data, other_side_dir, status)`：门按**方向**索引，载荷是 mapping（`name`/`id`/`other_side_dir`/`status` 位掩码 `DOOR_CLOSED`）。`room.c:168` `open_door(dir, from_other_side)` 与 `room.c:193` `close_door` 实现**双向同步**：开本侧门时调用对侧房间 `open_door(other_side_dir, 1)`，`from_other_side` 标志避免无限递归。
- `room.c:267` `valid_leave(me, dir)`：门关则 `notify_fail("你必须先把…打开！")`，是 go 命令的通行闸。
- `room.c:52` `make_inventory` + `room.c:76` `reset()`：按 `set("objects", ([file: amount]))` 声明刷 NPC/物品，`reset` 周期补刷、 wander NPC `return_home` 召回。
- 房间定义模式（`d/village/alley1.c`）：`set("exits", ([dir: target]))` + `set("outdoors","xxx")` + `set("objects",…)` + `set("cost",1)` + `setup()` + `replace_program(ROOM)`。出口就是方向->目标房间文件名的 mapping，无独立"出口对象"。
- `d/REGIONS.h`：35 区域纯命名映射（`"village":"华山村"`），**不参与拓扑**，只是显示名与目录组织。

### 1.2 engine 现状对照（批判）

engine 把 LPC 单一 `doors` mapping **正交拆成三件**（`engine/src/openmud/components.py:102-170`）：
- `Exit`（frozen：`target` + `aliases`）= "通向哪里"；
- `Exits`（mutable `by_direction`）= 房间出口集合，运行时可增删；
- `Door`（`state` + `key_item_id` + `consume_key`）+ `Doors`（`by_direction`）= "能不能过"，与 `Exits` 正交。
- 另有 `HiddenExit`/`HiddenExits`（`components.py:173-185`）承载剧情出口揭示。

**偏差/遗漏**：
1. **双向门同步缺失**：LPC `open_door(from_other_side)` 显式同步对侧；engine 的 `Door` 组件按方向各自独立，`commands.py` 的 open/close 是否同步对侧需核实（grep 显示 `commands.py:455` 有 `ON_TRAVERSE_BLOCKED` 但未见对侧同步逻辑）。这是 LPC 的真实机制，engine 若未做则是遗漏。
2. **门状态枚举更细**：engine `DoorState`（OPEN/CLOSED/LOCKED，`components.py:127`）比 LPC 位掩码（仅 `DOOR_CLOSED`）多一档 LOCKED + 钥匙引用，是合理的现代化增强，但属于"超过 LPC"而非偏差。
3. `make_inventory`/`reset` 周期补刷：engine 用 `world.spawners` 蓝图 + `spawn_scan`（`world.py:87-91`）替代，语义对齐 ADR-0010。

### 1.3 抽象判定（必须 core / 可下沉）

| 机制 | 判定 | 理由 |
|---|---|---|
| 房间 = 实体 + Position/Description/Exits 组件 | **必须 core** | 拓扑基底，所有题材共用；UGC 安全性要求拓扑可达性由 core 校验 |
| Exit（target + aliases） | **必须 core** | 通行原语，Nature/交通/任务全复用 |
| Exits mutable（运行时增删方向） | **必须 core** | 渡船/船只/机关秘道全靠它（`ferry.py:123` `_apply_crossing_exits` 直接改 `exits.by_direction`） |
| Door 状态（open/closed/locked） | **必须 core** | 通行闸，战斗追逃/任务门槏复用 |
| **双向门同步**（对侧联动） | **应补进 core** | LPC 真实机制，缺则两个房间门状态会漂移不一致，破坏拓扑不变量 |
| HiddenExit 揭示 | **core 提供机制，触发条件下沉** | 揭示时机（时段/技能/物品）是题材逻辑，用 hook（`room_hooks.py:240` `TimeOfDayPassageHook` 已是此路） |
| Door 钥匙/剧情门（consume_key） | **core 数据，匹配规则可下沉** | 钥匙匹配可由条件 DSL 表达，core 只存引用 |
| make_inventory/reset 补刷 | **core 调度，刷什么下沉** | 引擎控制补刷周期与存活判定，题材包只声明蓝图 |

---

## 2. 移动与移动消耗、负重的抽象方向

### 2.1 LPC 原始形态（证据）

- `feature/move.c:47` `move(dest, silently)`：这是**对象到容器的通用移动**（物品进背包、NPC 进房间都走它），不是方向移动。流程：unequip 检查 -> 负重校验（`move.c:76` `query_encumbrance + weight() > query_max_encumbrance`）-> 容器嵌套绕过（`move.c:74-75` 父链里有 ob 则跳过负重检查）-> 重量转移（`environment()->add_encumbrance(-weight())` 后 `ob->add_encumbrance(weight())`）-> 自动 look。
- `move.c:16` `add_encumbrance(w)`：**级联传播**到 environment 的 encumbrance。`move.c:45` `weight()` = 自身 weight + 携带 encumb（递归）。
- `room.c:17` `query_max_encumbrance()` 返回 `100000000000`（房间实际不限重）。
- 移动消耗：`alley1.c` `set("cost",1)` 是房间级移动消耗声明，但 `move.c` 本身不消费 cost——cost 在 go 命令层扣（见坐骑 `condition_check` 用 jingli）。
- 坐骑消耗：`clone/horse/horse.h:7` `condition_check()`——`jingli<=10` 坠骑受伤（`receive_wound("qi",150)`）+ 马昏厥；`<=30` 喘气；`<=max_jingli/3` 大口喘气。挂在 NPC `chat_msg`（`baima.c:42` `(: condition_check :)`）随随机 tick 触发，**不是移动时扣**。

### 2.2 engine 现状对照（批判）

- engine **拆成两路**：`transfer.py`（物品 take/drop/put，`transfer()` 收口，容量/重量校验在 `transfer.py:169-179`）+ `commands.py:455+` `go`（玩家方向移动，改 `Position.room`）。LPC 的单一 `move` 被拆开。
- 负重：engine **不做级联传播**，改用 `transfer.py:92` `container_total_weight` 按需求和。LPC 的 `add_encumbrance` 级联（嵌套容器重量自动向上累加）在 engine 里靠 `item_weight` + `container_total_weight` 显式算。这是合理的简化（避免级联状态维护），但**嵌套容器总重**计算在深嵌套时是 O(深度)。
- 移动消耗：engine 有 `Terrain`(cost, `components.py:725`) + `Mount`(ability/jingli, `components.py:705`) + `Riding`。`commands.py:471-483` go 命令扣精力：骑乘 `drain = cost * MOUNT_JINGLI_PER_TERRAIN_COST`，步行 `walk_drain = cost * WALK_JINGLI_PER_TERRAIN_COST`（`components.py:733/737`）。
- **偏差**：engine 把坐骑精力消耗从 LPC 的"NPC 随机 chat_tick 衰减"改成"**移动时扣**"（`commands.py:513`），语义不同——LPC 马站着也会累，engine 马不动不累。engine 还加了 LPC 没有的**步行玩家精力消耗**（`WALK_JINGLI_PER_TERRAIN_COST`），是题材增强。
- engine `Mount` 能力判定是**二值**（`cost > ability` 拒走，`commands.py:476`），丢了 LPC 的**分级喘息文案**（`horse.h:32-40` 三档）。engine 坠骑阈值是 `jingli==0`（`commands.py:515`），LPC 是 `jingli<=10`（`horse.h:18`）。
- `RoomResources`（`components.py:573`）注释明说"grass / 坐骑喂食未打通"——LPC `horse.h:48` 草地吃草回精力未实现。

### 2.3 三个可选抽象方向

**方向 A：移动原语统一化（回到 LPC 单 move）**
- 把 `transfer`（物品）与 `go`（实体定位）统一到一个"实体入容器/入房间"原语，对应 LPC `move(dest)`。
- 优点：语义统一，嵌套容器重量自然级联；接近 LPC 心智模型。
- 缺点：engine 已把两者拆开且各自成熟（transfer 有堆叠/合并/拆分，go 有门/钩子/地形校验），强行合并会牺牲类型清晰度；LPC 的 `move` 本身也是大杂烩（unequip+负重+look 全塞一起），现代引擎不应照搬。

**方向 B：分层原语（推荐基线）**——保持 transfer/go 分离，但抽出共享"通行校验链"
- core 提供 `traverse_check(world, entity, from_room, to_room, direction)` 闸口函数，串起：门状态 -> 地形/骑乘能力 -> before_leave 否决 -> before_enter 否决。`commands.py` 现已隐式做这套（`commands.py:464-492`），但散在 go 命令里。
- 负重保持 `container_total_weight` 按需求和（不级联），但为嵌套容器加缓存层（container 脏标记）防 O(深度)。
- 移动消耗：core 提供 `Terrain.cost` 数据 + `drain` 计算钩子，**消耗对象**（玩家 jingli / 坐骑 jingli / 燃料 / 体力）由题材包挂组件决定，core 只定义"cost -> drain -> 某资源池"的契约。坐骑分级喘息文案下沉题材包 hook。
- 优点：core 收口通行不变量（可达性、门一致），资源池题材无关；engine 现状改动小。
- 缺点：traverse_check 与现有 hook 事件点（`ON_BEFORE_LEAVE_ROOM`/`ON_BEFORE_ENTER_ROOM`，`room_hooks.py:33-35`）有职责重叠，需明确"闸口函数 = 同步硬规则，hook = 题材软否决"。

**方向 C：ECS 查询驱动（最激进）**
- 不设专门 traverse 原语，移动 = 改 `Position.room` + 分发 enter/leave 事件；所有校验（门/地形/精力）都做成查询组件的 guard，由事件订阅者各自否决。
- 优点：极致 ECS 风格，零硬编码；UGC 可任意插 guard。
- 缺点：guard 执行顺序不可控（事件总线无序），门"先于"地形校验这类时序依赖难保证；`commands.py:476` 地形校验必须在 before_leave 之前（否则马已扣精力却走不过去），无序事件无法表达。**不推荐**。

> 倾向方向 B：与 engine 现状最贴近、改动最小、且把"消耗资源池"题材化这一点是 LPC 未做但新引擎应做的增强。

---

## 3. Nature 作为 engine 横切层的抽象

### 3.1 LPC 原始形态（证据）

- `adm/daemons/natured.c:22` `create()` 读 `day_phase` 表 + `init_day_phase()`。
- `natured.c:28` `init_day_phase()`：`localtime(TIME_TICK)`（`TIME_TICK = time()*60`，1 真实秒=1 游戏分钟，60:1）对齐当前相位，`call_out("update_day_phase", 剩余长度)` 驱动循环。
- `natured.c:54` `update_day_phase()`：推进 `current_day_phase`，`message("outdoor:vision", time_msg, users())` 广播，调 `event_fun`（`event_dawn`/`sunrise`/`noon`），调 `event_common`。
- `natured.c:71` 广播接收方是 `users()`（全部在线玩家）——**户外过滤不在 natured.c**，靠 `message` efun 的 `"outdoor:vision"` 通道语义隐式过滤。`natured.c:144` `outdoor_room_description()` 是房间 look 时主动拉取的描述。
- `natured.c:83` `event_sunrise()`：**存档副作用**——遍历 `users()` 调 `link_ob->save()` + `ob->save()`。时段事件直接耦合持久化。
- `natured.c:100` `event_common()`：检查所有 livings 有 environment，无 environment 的玩家 move 到 `/d/city/wumiao.c`，跑 `inventory_check`。
- `adm/etc/nature/day_phase`：8 时段（dawn/sunrise/morning/noon/afternoon/evening/night/midnight），字段 `length`/`time_msg`/`desc_msg`/`event_fun`。
- 天气：`natured.c:11` 5 档 `weather_msg` 字符串数组，但 **natured.c 内无天气状态机**（只有字符串，没有切换逻辑）——天气演变可能在别处或未实现。

### 3.2 engine 现状对照（批判）

- `engine/src/openmud/nature.py:136` `NatureState`：相位序列 + `advance_tick`（`nature.py:279`）推进，`align_from_clock`（`nature.py:257`）对齐。**比 LPC 更忠实于"相位推进"本身**。
- `nature.py:306` `advance_tick` 分发 `ON_NATURE_CHANGE`（`nature.py:29`），携带 `phase_msgs`（跨多相位不丢中间，`nature.py:60-79`）+ `weather_msg`。
- `nature.py:517` `_broadcast_nature_change`：**显式过滤户外玩家**（`nature.py:502` `_outdoor_player_ids` 按 `Description.outdoors`），比 LPC 的"广播给 users() 靠通道过滤"更明确。
- `nature.py:320` 天气是 2 态（CLEAR/RAIN），有概率翻转（`nature.py:320` `_maybe_change_weather`）——**比 LPC 多了状态机**，但档位少于 LPC 的 5 档字符串。
- `nature.py:584`(components) `LocalNature` 房间贴纸（ADR-0013）：LPC **没有**的机制，engine 允许单房覆盖相位/天气（洞天福地）。是合理增强。
- **遗漏**：engine **无 `event_fun` 等价物**——LPC 的"sunrise 自动存档""noon 环境清理"这类时段副作用在 engine 里没有内建耦合。这**反而是优点**（解耦），但意味着"时段触发存档"需题材包用 `on_nature_change` 订阅实现。engine 也无 `event_common` 的"无 environment 实体归位"逻辑（那更像是 LPC 的脏数据兜底，新引擎 ECS 不该产生无 environment 实体）。

### 3.3 三个可选抽象方向

**方向 A：Nature = 纯相位推进器 + 广播事件点（engine 现状，推荐基线）**
- core 只管：相位序列数据驱动（`DayPhase` 题材包提供）、`advance_tick` 推进、`ON_NATURE_CHANGE` 分发、户外广播订阅者。
- 时段副作用（存档/刷怪/NP C 闲聊）全部下沉 `on_nature_change` 订阅，core 不内建任何 `event_fun`。
- 户外判定：core 提供 `Description.outdoors` 标记 + `LocalNature` 贴纸合成（`resolve_effective_nature`，`nature.py:344`），广播通道由 core 的 `_broadcast_nature_change` 默认实现，题材包可替换。
- 优点：与 engine 现状一致，机制/文案彻底分离（ADR-0004 手法推广），UGC 可换相位表不碰引擎。
- 缺点：LPC 的"sunrise 存档"这类运维便利丢失，需题材包显式订阅（可由官方题材包兜底）。

**方向 B：Nature = 时段事件总线（显式 event_fun 注册）**
- core 提供时段回调注册表（`register_phase_event(name, handler)`），题材包声明"sunrise -> save_hook"，引擎在相位切换时按名调用。
- 优点：接近 LPC `event_fun` 心智，时段副作用有显式挂载点。
- 缺点：与 `ON_NATURE_CHANGE` 事件点重复（同一能力两套入口），增加 core 表面；且 `event_fun` 是按相位**名**硬绑，不如事件点灵活。

**方向 C：Nature = 多通道环境广播系统（抽象到天气/季节/月相通用）**
- 把 `outdoor:vision` 抽象成通用"环境通道"（phase/weather/season/custom），core 提供通道注册 + 户外订阅过滤，题材包往各通道发消息。
- 优点：为未来季节/月相/魔潮等扩展留位（题材无关的横切层）。
- 缺点：MVP 过度设计——LPC 只有昼夜+天气两维，engine 现状已够；通用通道框架收益要等 N 个题材包才显现。

> 倾向方向 A：engine 现状已是此路，且把时段副作用下沉事件点是正确的解耦；方向 C 留作 post-MVP（见 `post-mvp-backlog.md`）。

---

## 4. 交通三态（坐骑 / 渡船 / 船只）的统一抽象

### 4.1 LPC 三态实证对比

| 维度 | 坐骑（horse） | 渡船（ferry） | 船只（ship） |
|---|---|---|---|
| 源码 | `clone/horse/horse.h` + `baima.c` | `inherit/room/ferry.c` | `inherit/room/ship.c` |
| 驱动 | NPC `chat_msg` 随机 tick（`baima.c:42` `(: condition_check :)`） | `call_out` 链（`ferry.c:90/111/138`） | `call_out` 循环（`ship.c:106/279`） |
| 触发 | 被动（骑上后随时间累减） | **玩家 yell 触发**（`ferry.c:28` `do_yell`） | **玩家 start/go 驱动**（`ship.c:73` `do_start`/`ship.c:284` `do_go`） |
| 状态机 | jingli 三档衰减（`horse.h:18/32/37`） | `yell_trigger` + 4 阶段（check_trigger->on_board->arrive->close_passage） | locx/locy 坐标 + navigate/dir + weather + trigger |
| 出口动态开关 | 无（骑乘改移动语义，不改拓扑） | **是**：两岸 `exits/enter` + 船 `exits/out` 翻转（`ferry.c:81/103/108/121/146`） | **是**：船 `exits/out` 到港时设、离港删（`ship.c:96/241/249`），港口 `exits/enterN` 联动 |
| 空间模型 | 共享房间拓扑 | 船是独立 room，两岸是 room | 船是独立 room + **抽象坐标网格**（locx/locy，`ship.c:100-101/204-214`） |
| 失败/终结 | jingli<=10 坠骑+马昏厥（`horse.h:18-29`） | 无（周期自动关闭） | 触礁/翻船 `do_drop`（`ship.c:129/138/513`）：玩家昏迷+丢物+随机港口上岸 |
| 周期性 | 是（chat_tick 衰减） | 是（call_out 定时翻转） | 是（navigate 每 2 秒推进，`ship.c:279`） |

**关键共性**：三者都是"**周期性载具 + 动态 exit 开关 + 状态机**"。差异在触发源（自动 vs 玩家驱动）与空间模型（拓扑内 vs 抽象坐标）。

### 4.2 engine 现状对照（批判）

- **坐骑**：engine 已建（`components.py:705` `Mount` + `Riding` + `commands.py:500-525` go 处理骑乘移动）。精力消耗改在移动时（非 chat_tick），二值能力判定，缺分级文案与吃草回精力。
- **渡船**：engine 已建（`ferry.py` + `components.py:773` `Ferry`）。但**语义偏差大**：LPC 是玩家 `yell` 触发、call_out 链分阶段；engine 是**自动周期翻转** `FerryCrossing.at_bank_a` + `ticks_until_flip`（`ferry.py:108-113`），`_apply_crossing_exits`（`ferry.py:123`）直接改两岸 `Exits`。engine 丢了 LPC 的"船作为可进入的中间 room"（LPC 玩家先进船 room 再到对岸，engine 直接两岸互通）。engine 也无 `yell` 触发入口。
- **船只**：engine **完全未建**。无坐标网格、无 navigate 循环、无 shipweather、无 do_drop 沉船、无 harbor/island 注册表。这是最大的缺口。

### 4.3 三个统一抽象方向

**方向 A：统一"动态 exit 开关器"（最小公分母）**
- 把渡船/船只/时段秘道/机关门都抽象成"**周期性或事件触发的 exit 增删器**"：core 提供 `ExitToggle` 机制（已有 `_apply_crossing_exits` 雏形，`ferry.py:123`），题材包声明触发条件 + 周期 + 涉及的 (room, direction) 对。
- 坐骑不纳入（它不改拓扑，改移动语义）。
- 优点：覆盖 ferry + time_of_day_passage（`room_hooks.py:240`）+ dig_collapse（`room_hooks.py:74`）这类已有机关；最小新增 core 表面。
- 缺点：船只的**抽象坐标空间**与**载具内 room**无法表达——ship 不是简单 toggle，是在坐标网格里移动后动态生成到港 exit。强行套 toggle 会丢航海玩法。

**方向 B：分层抽象 = 载具实体 + 周期调度 + 动态 exit（推荐）**
- 三层：
  1. **载具实体**（core 原语）：一个可被玩家进入的"移动 room"（船/马车/轿子）。挂 `Exits`（自身内部出口）+ `VehicleState`（位置/航向/载客）。LPC 的 ship room、ferry 的 boat room 都是此物。engine 现状的 ferry **缺这层**（直接两岸互通，无船 room）。
  2. **周期调度**（core 服务）：`on_tick` 驱动的状态机推进器，题材包声明状态转移图（ferry: 4 阶段 call_out；ship: navigate 循环；mount: jingli 衰减）。engine 的 `FerryCrossing.ticks_until_flip`（`ferry.py:32`）是此物的退化版。
  3. **动态 exit 绑定**（core 机制）：载具到"站"时，在载具与站房间之间双向建 exit；离站时删除。复用 `Exits` mutable + `_apply_crossing_exits` 思路。
- 坐骑单列：它是"骑乘关系"而非"载具 room"（玩家与马共处一房，马是 NPC 不是 room），用 `Mount`/`Riding` 组件，不进载具抽象。
- 优点：覆盖三态（ferry=2 站周期载具，ship=N 站坐标载具，mount=骑乘关系单列）；为未来马车/飞行器留位；修复 engine ferry 缺船 room 的偏差。
- 缺点：core 表面增大（需 `Vehicle` 组件 + 状态机调度框架）；状态机声明格式需设计（YAML DSL 或可信 hook）。

**方向 C：全部下沉可信 hook（零 core 新增）**
- 船只/渡船全用 `RoomHook`（`room_hooks.py`）+ `on_tick` 实现，core 只保证 `Exits` mutable 与 `relocate_entity`（`room_hooks.py:601`）可用。
- 优点：core 零新增；与 ADR-0012"机关用可信 hook"一致。
- 缺点：LPC ship 是**跨房间坐标系统**，用单房 hook 难表达（hook 绑定单房，ship 状态跨多个 harbor/island room）；且 hook 不进 UGC（ADR-0012），官方题材包得自己写 Python，违背"题材包只提供数据"的 M3 目标。**不推荐用于 ship**。

> 倾向方向 B：三态中 ferry/ship 共享"载具 room + 周期 + 动态 exit"骨架，mount 走骑乘关系单列；方向 A 不够（盖不住 ship 坐标），方向 C 违 M3 数据/代码分离。

---

## 5. 跨区连接（官道）与区域/世界边界

### 5.1 LPC 原始形态（证据）

- `d/REGIONS.h`：35 区域纯命名映射，**无拓扑语义**，不声明区域边界或连通关系。
- 跨区连接 = 出口指向另一目录的房间：`d/village/sexit.c:17` `set("exits", (["south": __DIR__"hsroad3"]))`（`__DIR__` 是当前文件目录，故 sexit 在 village/ 指向同目录 hsroad3，而 hsroad 系列通向 huashan）。官道 `d/*/road*.c` 遍布各区，靠 exit 链跨区。
- **无"区域边界"机制**：区域是目录组织 + 显示名，拓扑上是全连通图，无 zone gate/region transition callback。
- `d/death/road1-3.c`：地狱道路，是特殊"区域"但仍是普通房间 + exit。

### 5.2 engine 现状对照（批判）

- engine **无 region/area/zone 抽象**（grep `region|area|zone` 在 `engine/src/openmud/*.py` 无拓扑相关命中，只有 `NoDeathZone`/`in_no_death_zone` 这类房间标记）。
- 房间是**扁平** `world.room_ids: dict[str, EntityId]`（`world.py:97`），区域隐含在 room key 命名（如 `village_alley1`）。
- `scene_loader.py` 按 room key 加载，无区域分组、无跨区连接校验。

### 5.3 三个可选方向

**方向 A：区域 = 纯显示分组（推荐，贴合 LPC 与 engine 现状）**
- core 不引入 region 拓扑概念。区域 = 题材包数据里的 `region` 标签（room key 前缀或显式 `area` 字段），仅用于：look 显示区域名、地图 UI 分组、stat 统计。
- 跨区连接 = 普通 exit（指向另一区域的 room key），core 不特殊处理。
- 优点：与 LPC `REGIONS.h`（纯命名）和 engine 现状（扁平 room_ids）一致；最小 core 表面；UGC 摆房间连区域无需学新概念。
- 缺点：无"区域切换"事件点（进新区域播报/触发事件需题材包用 `on_enter_room` hook 自己按 room key 前缀判断）。

**方向 B：区域 = 显式拓扑分组 + 切换事件点**
- core 提供 `Region` 组件（room 挂 `region_id`）+ `ON_REGION_CHANGE` 事件点（玩家跨区域时分发）。
- 优点：区域切换有原生事件点（进山/进城播报、区域任务激活）；fast travel 可按区域粒度。
- 缺点：LPC 无此物，engine 现状无此物，纯新增；增加 UGC 创作面（创作者须标 region）；MVP 无明确需求驱动。

**方向 C：世界边界 = 显式边界房间 + 越界处理**
- core 提供"世界边界"概念：声明哪些房间是世界边缘，越界时触发兜底（传送回重生点/提示"前方是未开发区域"）。对应 LPC `natured.c:119` 无 environment 实体 move 到 `/d/city/wumiao.c` 的兜底精神。
- 优点：防 UGC 拓扑断裂（出口指向不存在 room）；世界扩展时有明确边界。
- 缺点：engine `scene_loader` 加载期已校验 exit target 存在（fail-closed），拓扑断裂在加载期就拦住，运行期边界概念冗余；与 ADR-0009（单进程单 World）下"世界即全部加载房间"的模型冲突。

> 倾向方向 A：LPC 与 engine 现状都无区域拓扑概念，区域纯分组足够 MVP；方向 B 的区域切换事件可由 `on_enter_room` + room key 前缀在题材包内实现，无需 core 新增；方向 C 的边界保护已由加载期校验覆盖。

---

## 6. 汇总：核心抽象清单与可选方向一览

| 机制层 | 推荐方向 | core 必收 | 下沉题材包 |
|---|---|---|---|
| 房间/出口/门 | §1 | Exit/Exits/Door + **双向门同步（应补）** + HiddenExit 机制 | 门钥匙匹配规则、揭示触发条件 |
| 移动/消耗/负重 | §2 方向 B | traverse_check 闸口 + Terrain.cost 数据 + drain 契约 | 资源池类型（jingli/燃料）、分级喘息文案、吃草回精力 |
| Nature 横切层 | §3 方向 A | 相位推进 + ON_NATURE_CHANGE + 户外广播默认实现 + LocalNature 合成 | 相位表文案、时段副作用（存档/刷怪）、天气档位扩展 |
| 交通三态 | §4 方向 B | 载具实体 + 周期调度 + 动态 exit 绑定；Mount/Riding 单列 | 状态转移图、坐标网格定义、沉船事件文案 |
| 跨区/边界 | §5 方向 A | 无新增（扁平 room_ids + 加载期 exit 校验） | region 显示分组、区域切换播报（用 on_enter_room） |

### 未决问题（留后续决策）

1. **双向门同步**是 core 必须补的遗漏，还是允许题材包用 hook 实现？（倾向 core：拓扑一致性是不变量）
2. **载具 room**（ferry 的船、ship）是否进 MVP？现状 ferry 无船 room，直接两岸互通——若 MVP 要还原"上船过渡"体验则需补；若只求过河功能则现状够。
3. **船只（ship）整体**是否进 MVP？LPC ship 591 行最复杂，坐标+导航+天气+沉船；MVP 场景清单（CLAUDE.md 架构不变量 7）列"水陆交通（渡口/渡船）"未单列船只航海。倾向 MVP 只做 ferry，ship 留 post-MVP。
4. **移动消耗资源池**题材化后，官方武侠题材包用 jingli，科幻题材用 fuel——core 的 drain 契约形状（资源池接口）需后续接口任务定。
