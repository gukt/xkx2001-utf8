# engine-comparison：现有 engine 实现 vs LPC 原始设计 逐项对照

> 层级：06-engine-critique（engine 批判对照员）。
> 方法：以 LPC 一手源码为唯一真相源，逐模块标注 engine 的偏差与遗漏。每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。
> 范围：nature.py / world.py / room_hooks.py / room_details.py / ferry.py / directions.py / transfer.py / scene_loader.py / scenes.py，外加坐骑与玩家船的跨模块覆盖度。
> 约束：engine 模块仅作批判对照对象，不作反向脑补来源。

---

## 0. 总览：正面偏差 vs 负面遗漏

### 正面偏差（engine 做得更好的地方）

| # | 偏差项 | engine 证据 | LPC 对照 |
|---|--------|-------------|----------|
| P1 | 房间数据驱动（YAML），非代码对象 | `scene_loader.py:461` `_build_rooms` 从 YAML 建实体 | LPC 每房 = `.c` 文件 + `inherit ROOM` + `replace_program(ROOM)`（`d/village/alley1.c:4,23`），UGC 不安全 |
| P2 | 声明式门（YAML `door` 字段）+ 锁/钥匙 | `scene_loader.py:728` `_exit_door` + `components.py:141` `Door`/`Doors` | LPC `room.c:227` `create_door` 运行时建门（需手写 LPC 代码） |
| P3 | 物品堆叠合并/拆分 + 防嵌套循环 | `transfer.py:209` `_split_stack` / `transfer.py:309` `_is_descendant` | LPC `move.c` 无堆叠概念，无嵌套防护 |
| P4 | 未识别字段透传（前向兼容） | `scene_loader.py:397` `_capture_top_level_unknown_sections` / `:410` `_capture_entity_unknown_fields` | LPC 无此概念（每个字段需代码处理） |
| P5 | Nature 时辰×天气二维文案 | `nature.py:44` `DayPhase.rain_desc_msg` + `:237` `outdoor_desc` | LPC `natured.c:144` `outdoor_room_description` 仅单维 `desc_msg` |
| P6 | 动态天气翻转 | `nature.py:320` `_maybe_change_weather` | LPC `natured.c:11` `weather_msg` 5 档数组定义但**全仓无消费方**（grep `d/` 无引用），实为死代码 |
| P7 | 方向别名 N1 归一 + 中英文混解 | `directions.py:26` `builtin_aliases` / `:46` `resolve_english_bare` / `:52` `resolve_chinese_builtin` | LPC 出口键为裸字符串（`alley1.c:14` `"east"`/`"northwest"`），无归一/别名层 |
| P8 | 房间钩子窄 ctx（不透出 World 私有结构） | `room_hooks.py:385` `RoomHookContext` | LPC `room.c` 回调直接在 room object 上操作 `this_object()`，无隔离 |
| P9 | 渡口幂等 attach + 纯内存态 | `ferry.py:42` `attach_ferries` 幂等注册 | LPC `ferry.c` call_out 不幂等，重启靠 room object 重建 |
| P10 | 房间景物 `名(id)` 扫描（客户端高亮预留） | `room_details.py:87` `scan_detail_mentions` | LPC 无此概念 |

### 负面遗漏（engine 缺失的能力）

| # | 遗漏项 | LPC 证据 | engine 现状 |
|---|--------|----------|-------------|
| N1 | **玩家船系统**（591 行：导航/天气/瞭望/所有权/触礁） | `inherit/room/ship.c` 全文 | engine 全仓无 ship/navigate/lookout/locate（grep 空结果） |
| **N2** | **区域概念**（35 区域 + REGIONS.h 映射） | `d/REGIONS.h` `region_names` mapping | engine 全仓无 region/Region 概念（grep 空结果） |
| N3 | **event_fun 钩子**（event_dawn/sunrise/noon + event_common） | `natured.c:72-75` `call_other(event_fun)` + `:100` `event_common`（inventory_check） | engine `ON_NATURE_CHANGE` 仅广播，无 save/inventory_check 回调 |
| N4 | **渡船玩家交互**（yell 召船 + 登船房 + 离船） | `ferry.c:28` `do_yell` / `:55` `check_trigger` / `:93` `on_board` | engine `ferry.py` 纯定时翻转，无 yell/无船房实体/无登船 |
| N5 | **跟随/队伍**（set_leader） | `horse.h:27` `me->set_leader(0)` | engine 全仓无 leader/follow/group（grep 空结果） |
| N6 | **马匹吃草恢复精力** | `horse.h:48-55` `resource/grass` + `add("jingli")` | engine `components.py:577` `RoomResources` 明注「grass 未打通」 |
| N7 | **坠骑受伤**（150 qi 伤） | `horse.h:22` `ob->receive_wound("qi", 150, ...)` | engine `commands.py:521` 仅文案「你摔了下来」+ Unconscious，无 qi 扣减 |
| N8 | **马匹驯服/训练**（wildness/msg_fail/succ/trained） | `clone/horse/baima.c:20-24` `set("wildness")`/`msg_*` | engine `Mount` 组件（`components.py:705`）无驯服字段 |
| N9 | **in/out 方向** | LPC 出口键含 `"enter"`/`"out"`（`ferry.c:81` `exits/enter` / `ship.c:84` `exits/out`） | engine `directions.py:11` 明注「不含 in/out（本批十向）」 |
| N10 | **房间级负重传播** | `move.c:22` `environment()->add_encumbrance(w)` + `:85` 离开时减 | engine `Container.max_weight`（`components.py:247`）仅容器自身，无环境传播 |
| N11 | **运行时动态建门** | `room.c:227` `create_door` 可在游戏运行中创建门 | engine 门仅在加载期从 YAML 建（`scene_loader.py:728`），无运行时 API |
| N12 | **item_desc 动态 callable** | `room.c:248` `set("item_desc/"+dir, (: look_door, dir :))` 闭包 | engine `RoomDetails`（`components.py:540`）仅静态 `text` 字符串 |

---

## 1. nature.py vs natured.c：昼夜时段循环 / 天气 / 户外广播

### 1.1 昼夜时段循环

**LPC 设计**（`adm/daemons/natured.c` + `adm/etc/nature/day_phase`）：
- 8 个时段：dawn(240) / sunrise(120) / morning(180) / noon(180) / afternoon(180) / evening(180) / night(120) / midnight(240)，总长 1440 游戏分钟 = 1 游戏日。
- 驱动：`call_out("update_day_phase", delay)`（`natured.c:50`），wall clock 对齐（`init_day_phase` 用 `localtime(TIME_TICK)` 算当日已过分钟定位当前相位，`:34-44`）。
- 切换时 `message("outdoor:vision", time_msg + "\n", users())`（`:71`）广播全户外玩家。
- `event_fun` 回调：切换相位时 `call_other(this_object(), event_fun)`（`:72-73`），如 `event_dawn`/`event_sunrise`/`event_noon`/`event_midnight`。
- `event_common()`（`:100`）：每次相位切换都调用，遍历 `livings()` 清理无环境对象 + `UPDATE_D->inventory_check(ob[i])` 全玩家背包检查。
- `event_sunrise()`（`:83`）：遍历 `users()` 自动 `save()` 玩家数据。

**engine 现状**（`engine/src/openmud/nature.py`）：
- `DEFAULT_PHASES`（`:83`）：4 相（dawn 240 / day 720 / dusk 240 / night 240），总长 1440。可经 YAML `day_phases` 覆盖（`:460` `_parse_nature_config`）。
- 驱动：`on_tick` 订阅（`:452` `_on_tick_nature`），每 tick 推进 `game_minutes_per_tick`（默认 1）游戏分钟。`align_from_clock`（`:257`）用注入时钟对齐相位。
- 切换时 `world.events.dispatch(ON_NATURE_CHANGE, ...)`（`:306`），`_broadcast_nature_change`（`:517`）推送给 `_outdoor_player_ids`（`:502`）中的户外玩家。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 时段数 | 8（day_phase 文件） | 默认 4（可配） | **偏差**：默认粒度粗 2 倍。可经 YAML 恢复 8 相，风险低。但 `is_day`/`is_night` 高阶谓词（`nature.py:125-126` `NIGHT_PHASES`/`DAY_PHASES`）默认只覆盖 dawn/day/dusk/night 四名，自定义相位名需自行扩展集合。 |
| 时钟驱动 | `call_out`（wall clock 秒级） | `on_tick`（game tick） | **正面偏差**：tick 驱动可注入时钟、可测、不依赖墙钟；但 LPC 的「1 真实秒=1 游戏分钟」比例在 engine 用 `game_minutes_per_tick` 表达，CLI 每命令 1 tick，节奏模型不同（命令驱动 vs 时间驱动）。 |
| event_fun | 8 个回调 + event_common | 无 | **遗漏（N3）**：engine `ON_NATURE_CHANGE` 仅分发广播上下文，无 save/inventory_check/事件回调机制。LPC 的 `event_sunrise` 自动存档与 `event_common` 全玩家背包检查在 engine 无对应。风险：M3+ 需要时段触发的世界事件（如商店开门、NPC 日程）无挂载点。 |

### 1.2 天气

**LPC**：`natured.c:11` `weather_msg` 5 档数组（无云/淡云/白云/厚云/乌云）。但 grep 全仓 `d/`/`inherit/`/`feature/`/`cmds/` **无任何消费方**引用 `weather_msg`，实为未接线的死代码。`outdoor_room_description()`（`:144`）只返回 `desc_msg`，不含天气。

**engine**：`Weather` 枚举两态 CLEAR/RAIN（`nature.py:37`）。`_maybe_change_weather`（`:320`）按 `weather_change_chance`（默认 0.1）每 tick 随机翻转。`outdoor_desc_for`（`:241`）按 phase×weather 取 `rain_desc_msg` 或拼接默认雨后缀。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 天气档位 | 5 档（死代码） | 2 态（活） | **正面偏差（P6）**：engine 真正实现了动态天气，LPC 的 5 档从未接线。但仅 2 态（晴/雨）表达力有限；LPC 的 5 档（含厚云/乌云等过渡态）虽未消费，但暗示了更细的天气梯度需求。 |
| 天气对玩法影响 | 无（weather_msg 未消费） | 无（`nature.py:38` docstring 明注「不做对玩家机制影响」） | 一致：双方都未把天气接入视野/移动等机制。 |

### 1.3 户外广播通道

**LPC**：双通道。
- PULL：`cmds/std/look.c:46` `env->query("outdoors") ? NATURE_D->outdoor_room_description() : ""`，look 时拉取户外描述。
- PUSH：`natured.c:71` `message("outdoor:vision", msg, users())`，相位切换时广播全玩家，由 message 系统按 `"outdoor:vision"` class 过滤（仅户外房间玩家可见）。

**engine**：双通道，结构对齐。
- PULL：`nature.py:387` `outdoor_desc_for_room(world, room_id)`，look 时拉取。
- PUSH：`nature.py:517` `_broadcast_nature_change`，相位切换时遍历 `_outdoor_player_ids`（`:502`，查 PlayerSession + Position + Description.outdoors）推送 `world.push_message`。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 户外判定 | `set("outdoors", "xxx")`（`alley1.c:19`），值为区域名但实际只判 truthy | `Description.outdoors: bool`（`components.py:87`） | **正面偏差**：engine 用 bool 更清晰；LPC 的字符串值从未被 natured.c 消费（只判存在性）。 |
| 广播过滤 | message class `"outdoor:vision"` 由 user object 过滤 | `_outdoor_player_ids` 显式查询户外玩家 | 功能等价；engine 更直接（不依赖消息 class 机制），但遍历全玩家查 Position+Description 有 O(玩家数) 开销（LPC message() 也是遍历 users()）。 |
| 室内玩家 | 不收 | 不收（`_outdoor_player_ids` 排除） | 一致。 |

---

## 2. world.py vs d/+room.c：房间/拓扑/区域注册

### 2.1 房间模型

**LPC**：每房 = `.c` 文件，`inherit ROOM` + `create()` 设 `short`/`long`/`exits`/`outdoors`/`objects`/`cost`/`no_clean_up` + `setup()` + `replace_program(ROOM)`（`d/village/alley1.c` 全文）。房间是可执行代码对象。

**engine**：房间 = ECS 实体，挂 `Identity` + `Description`(含 outdoors) + `Exits` + `Container` 组件（`scene_loader.py:461` `_build_rooms`，每房 `world.create_entity()` + `add_component`）。数据来自 YAML。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 房间本质 | 代码对象（LPC .c） | 数据实体（ECS + YAML） | **正面偏差（P1）**：数据驱动对 UGC 安全，不可执行任意代码。 |
| exits | `set("exits", ([ "east": __DIR__"sroad3", ... ]))`（`alley1.c:14`） | `Exits.by_direction: dict[str, Exit]`（`components.py:115`），`Exit(target=EntityId, aliases)` | 对齐。engine 额外支持出口别名与 `random_of`（`scene_loader.py:696`）。 |
| outdoors | `set("outdoors", "xxx")`（`alley1.c:19`） | `Description.outdoors: bool`（`components.py:87`） | 对齐（见 1.3）。 |
| cost（移动消耗） | `set("cost", 1)`（`alley1.c:21`） | `Terrain.cost: int`（`components.py:728`），commands._cmd_go 消费（`commands.py:472`） | **偏差**：LPC cost 挂在 room 上；engine 拆为独立 `Terrain` 组件（正交能力），语义更清晰。 |
| objects（房间生成物） | `set("objects", ([ file: amount ]))` + `reset()`/`make_inventory()` 克隆（`room.c:52,76`） | scene_loader `_collect_room_objects` + `_build_items`/`_build_npcs` 加载期放置（`scene_loader.py:137-141`） | **偏差**：LPC 运行时 `reset` 按需克隆；engine 加载期全量放置 + `spawn_scan`（`ai.py:270`）低频补刷。生命周期不同。 |
| no_clean_up | `set("no_clean_up", 0)`（`alley1.c:18`） | 无直接对应 | **遗漏**：engine 无 no_clean_up 概念，清理逻辑由 `spawn_scan` 的 `respawn` 标志控制（`ai.py:285`）。 |

### 2.2 区域注册

**LPC**：`d/REGIONS.h` 声明 `region_names` mapping，35 区域（baituo/beijing/city/dali/shaolin/village/...），每区有中文名。房间通过所在目录隐式归属区域。

**engine**：`world.py` 无区域字段。`grep -rn "region\|Region" engine/src/openmud/` 空结果。`world.room_ids: dict[str, EntityId]`（`world.py:97`）仅键->实体 id 映射，无区域分组。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 区域声明 | `d/REGIONS.h` 35 区域 + 中文名 | 无 | **遗漏（N2）**：engine 无区域概念。风险：fast travel / 地图概览 / 区域级天气 / 区域广播等能力无挂载点。MVP 场景清单（华山村/扬州/少林/野外/官道）天然是区域分组，engine 无法表达。 |

---

## 3. room_hooks.py vs room.c 回调：valid_leave/reset/门 等 hook 覆盖度

**LPC room.c 回调**（`inherit/room/room.c` 281 行）：
- 门：`create_door`（`:227`）、`check_door`（`:218`）、`look_door`（`:158`）、`open_door`（`:168`）、`close_door`（`:193`）、`query_doors`（`:259`）、`query_door`（`:261`）。
- 通行：`valid_leave`（`:267`）——门关着时 `notify_fail`。
- 生命周期：`reset`（`:76`）——按 `objects` mapping 克隆/补刷 NPC 与物品；`make_inventory`（`:52`）——克隆对象入房；`setup`（`:277`）——`seteuid` + `reset`。
- 查询：`usr_in`（`:21`）——房内是否有玩家。

**engine room_hooks.py**（732 行）：
- 协议（`:38` `RoomHook` Protocol）：`on_enter` / `on_leave` / `on_tick` / `on_dig` / `on_scrape` / `on_pull` / `on_push` / `on_jump` / `on_climb` / `veto_leave`。
- 8 个内置机关钩子（`:365` `_register_builtin_hooks`）：`DigCollapseHook`（挖洞崩塌）、`MultiStepGateHook`（刮锈拔斧推门）、`LostInMazeHook`（迷途计步否决）、`SkillGateHook`（轻功门槛）、`TimeOfDayPassageHook`（时段秘道）、`MagneticIronHook`（磁力播报）、`BanditAmbushHook`（劫匪生成）、`KillOrderHook`（阵营杀令）。
- 窄 ctx（`:385` `RoomHookContext`）：add_exit/remove_exit/hide_exit/reveal_exit/schedule/message_room/message_actor 等。

| LPC 回调 | engine 对应 | 覆盖度 | 说明 |
|----------|-------------|--------|------|
| `valid_leave`（门关挡走） | `commands.py:452-466` `_cmd_go` 检查 `DoorState` + `ON_BEFORE_LEAVE_ROOM` veto | **覆盖（不同位置）**：engine 在 go 命令层检查门状态，另用 `veto_leave`（`room_hooks.py:680`）支持自定义否决（如 LostInMaze）。 |
| `reset`（补刷 objects） | `ai.py:270` `spawn_scan`（低频扫描蓝图补刷） | **覆盖（不同机制）**：LPC 每 reset 周期克隆；engine 每 N tick 扫描蓝图 slots 补刷。 |
| `make_inventory`（克隆入房） | `scene_loader.py:137-141` 加载期放置 + `ai.py:372` `spawn_from_blueprint` 补刷 | **覆盖（不同时机）**：LPC 运行时克隆；engine 加载期放置 + 运行时补刷。 |
| `setup`（seteuid+reset） | `scene_loader.py:151` `wire_runtime(world, scene_path)` | **覆盖**：engine 的 wire_runtime 接线所有运行时子系统（nature/AI/渡口/交战/门禁/昏迷苏醒）。 |
| `create_door`（运行时建门） | 无 | **遗漏（N11）**：engine 门仅加载期从 YAML 建（`scene_loader.py:728` `_exit_door`），无运行时 API 动态创建门。风险：无法实现「打破墙壁后出现门」类动态剧情。 |
| `open_door`/`close_door` | `commands.py:562`/`:583` `_set_door_state` | **覆盖**：open/close 命令改 `Door.state`。 |
| `check_door`/`look_door` | `commands.py` look 命令读 `Doors` 组件 | **覆盖**。 |
| `query_doors`/`query_door` | `Doors.by_direction` 直接读 | **覆盖**。 |
| `usr_in`（房内是否有玩家） | `world.py:217` `entities_in_room` + 过滤 PlayerSession | **覆盖**。 |

**关键偏差**：engine `room_hooks.py` 的钩子概念与 LPC `room.c` 回调**几乎不重叠**。engine hooks 是**机关解谜**（dig/scrape/pull/push/jump/climb —— 白玉峰/玉路/沙漠/天路灵感，见各类 docstring），是 LPC 中由各 room .c 文件内手写代码实现的特例逻辑的**声明式抽象**。LPC 的 room 生命周期回调（reset/door/make_inventory）被 engine 拆散到 commands / ai / scene_loader 三个模块。这是正面设计（分离关注点 + 声明式机关），但意味着 `room_hooks.py` 不是 `room.c` 的直接对应物。

---

## 4. room_details.py vs 房间景物：item_desc / look 机制

**LPC**：`set("item_desc/<key>", value)` 设景物 look 描述。value 可为字符串或 `(: callable :)` 闭包（`room.c:248` `set("item_desc/" + dir, (: look_door, dir :) )`）。玩家 `look <key>` 时调用对应 item_desc。

**engine**：`RoomDetails` 组件（`components.py:540`）：`entries: dict[str, DetailEntry]`，`DetailEntry`（`:529`）= `text: str` + `aliases: tuple[str,...]`。`room_details.py` 提供 `resolve_detail`（`:43`，N1 归一匹配键/别名）与 `scan_detail_mentions`（`:87`，扫描 `名(id)` 语法）。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 描述形态 | 字符串或 callable 闭包 | 静态字符串 `text` | **遗漏（N12）**：engine 不支持 callable 动态描述（如「门是开着的/关着的」随状态变化）。LPC `look_door`（`room.c:158`）按 `doors[dir]["status"]` 返回不同文案，engine 门状态展示走 commands 层 look 逻辑而非 item_desc。 |
| 匹配 | 精确键名 | N1 归一（去空格/`_`/`-` + casefold）+ 别名 | **正面偏差**：engine 匹配更宽容，支持中英文混合别名。 |
| 客户端高亮 | 无 | `scan_detail_mentions` 扫 `名(id)` 语法，标记 `lookable` | **正面偏差（P10）**：预留客户端高亮/可点判定。 |

---

## 5. ferry.py vs ferry.c：渡船周期状态机 / 动态 exit 开关

**LPC ferry.c**（157 行，玩家驱动的交互式渡船）：
1. `do_yell("boat")`（`:28`）：玩家喊「船家」-> `check_trigger()`。
2. `check_trigger()`（`:55`）：设两岸 exit —— 岸 `exits/enter` -> 船房，船 `exits/out` -> 岸。`call_out("on_board", 15)`（15 秒后收踏板）。
3. `on_board()`（`:93`）：删岸 `exits/enter`，删船 `exits/out`。`call_out("arrive", 20)`（20 秒后到对岸）。
4. `arrive()`（`:114`）：设船 `exits/out` -> 对岸。`call_out("close_passage", 20)`（20 秒后收船）。
5. `close_passage()`（`:141`）：删船 `exits/out`，清 `yell_trigger`。

总计：玩家 yell -> 15s 登船窗口 -> 20s 渡河 -> 20s 下船窗口 -> 循环。有**船房实体**（`this_object()->query("boat")` 指向的 room），玩家 `enter` 进船房、`out` 出船房。

**engine ferry.py**（147 行，定时驱动的自动渡船）：
1. `attach_ferries`（`:42`）：扫描 `Ferry` 组件建 `FerryCrossing`（两岸 + 方向 + 周期），挂 `on_tick`。
2. `_on_ferry_tick`（`:102`）：每 tick `ticks_until_flip -= 1`，到 0 时翻转 `at_bank_a`，调 `_apply_crossing_exits`。
3. `_apply_crossing_exits`（`:123`）：渡船在哪岸，哪岸 `Exits` 加指向对岸的 `Exit`，对岸对应方向删 `Exit`。
4. 无船房实体、无 yell、无登船/下船叙事。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 触发模型 | 玩家 pull（yell 召船） | 定时 push（tick 翻转） | **重大偏差（N4）**：LPC 是交互式（玩家主动召唤），engine 是自动式（定时翻转）。玩家无控制感，无法「叫船」。 |
| 船房实体 | 有（`query("boat")` 指向船 room，玩家 enter/out 进出船） | 无（直接在两岸 Exits 上增删 Exit，跳过船房） | **遗漏**：engine 无渡船房间，玩家无法「在船上」体验渡河过程（LPC 的 on_board 播报「竹篙一点，扁舟向江心驶去」无法复现）。 |
| 周期 | 15+20+20=55s（call_out 秒级，分阶段） | `cross_interval` ticks（单一周期，无阶段区分） | **偏差**：LPC 分登船/渡河/下船三阶段各有时长；engine 单一 interval 无阶段。 |
| 动态 exit | 增删 `exits/enter`/`exits/out`（含船房双向） | 增删两岸 `Exits.by_direction`（单方向） | **偏差**：LPC 有船房 <-> 岸双向 exit；engine 只在岸上挂指向对岸的单向 exit。 |
| yell 文案分层 | `do_yell` 按年龄/内力分文案（`:36-44`） | 无 yell | **遗漏**：engine 无喊船交互与文案分层。 |
| `ferry_status_line`（look 追加） | LPC 在船/岸 room 的 long 里手写 | engine `ferry.py:53` 返回停靠状态行 | 对齐（engine 有状态行，但无交互触发）。 |

**风险**：engine 的渡船是「定时门」而非「渡船」，丢失了 LPC 渡船的交互性与沉浸感（喊船、登船、渡河、下船的叙事节奏）。MVP 场景清单含「水陆交通（渡口/渡船）」，当前 engine 模型无法还原渡船体验。

---

## 6. directions.py vs LPC 方向词：方向别名 / 中英文解析覆盖度

**LPC**：出口键为裸字符串，直接在 `set("exits", ([ "east": ..., "northwest": ... ]))` 中声明（`alley1.c:14-17`）。10 基本方向 + `enter`/`out`。方向匹配靠玩家输入与 exit 键直接比较（无归一层）。`ferry.c` 用 `"enter"`/`"out"` 方向。

**engine directions.py**（114 行）：
- `DIRECTION_FORMS`（`:12`）：10 方向（north/south/east/west/ne/nw/se/sw/up/down），每项映射 `(英文简写, 中文)`。
- `builtin_aliases`（`:26`）：返回 `(英文全写, 简写, 中文)` 三元组。
- `resolve_english_bare`（`:46`）/ `resolve_chinese_builtin`（`:52`）：裸英文/中文 -> 方向键。
- `merge_exit_match_names`（`:63`）：按出口 aliases -> 目标房名 -> 内置同义词三层合并去重。
- `exit_display_label`（`:97`）：`look` 出口标签「中(english)」。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 10 基本方向 | 有 | 有 | 对齐。 |
| in/out 方向 | 有（`ferry.c:81` `exits/enter` / `ship.c:84` `exits/out`） | **无**（`directions.py:11` 明注「不含 in/out」） | **遗漏（N9）**：渡船与玩家船大量用 enter/out。engine 不支持这两个方向。风险：渡口/船只/室内进入等场景方向受限。 |
| 中文方向 | 无（出口键为英文） | 有（`resolve_chinese_builtin`） | **正面偏差（P7）**：engine 支持中文方位词输入「北」/「东北」。 |
| 别名归一 | 无 | N1 归一（去空格/`_`/`-` + casefold） | **正面偏差**：engine 匹配更宽容。 |
| 多层别名合并 | 无 | `merge_exit_match_names` 三层 | **正面偏差**：出口别名 -> 目标房名 -> 内置同义词统一匹配。 |

---

## 7. transfer.py vs move.c：移动 / 负重 / 容量 对齐度

**LPC move.c**（154 行，通用移动原语）：
- `move(dest, silently)`（`:47`）：先 `unequip`（卸装备）-> 查 dest -> **encumbrance 校验**（`ob->query_encumbrance() + weight() > ob->query_max_encumbrance()`，`:76-82`）-> 移动 + `add_encumbrance`（旧环境减、新环境加，`:85-86`）-> 玩家自动 `look`（`:117`）。
- `add_encumbrance(w)`（`:16`）：更新 encumb，超限调 `over_encumbrance`，**传播到 environment**（`:22` `environment()->add_encumbrance(w)`）。
- `set_weight(w)`（`:32`）：重量变化时更新 environment 的 encumbrance。
- `remove()`（`:123`）：destruct 时从 environment 减重。
- 覆盖范围：**所有对象移动**（物品入背包、玩家入房、NPC 移动）。

**engine transfer.py**（363 行，物品转移原语）：
- `transfer(world, item, src, dst, *, player_id, amount)`（`:97`）：校验 same_container / 防嵌套循环 -> no_get/no_drop 标志 -> 容量 `max_capacity` -> 重量 `max_weight` -> `on_get`/`on_drop` 否决钩子 -> 执行（拆分/合并/整件）。
- `item_weight`（`:81`）：Stackable 用 `unit_weight * amount`，否则 `Weight.value`。
- `container_total_weight`（`:92`）：容器内物品重量之和。
- 覆盖范围：**仅物品在容器间转移**（take/drop/put）。玩家房间移动在 `commands.py:_cmd_go`。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 覆盖范围 | 通用（物品+玩家+NPC） | 仅物品转移 | **偏差**：engine 把 LPC move() 拆为两条路径——`transfer()`（物品）+ `commands._cmd_go`（玩家移动）。这是正面分离关注点，但 transfer.py 只覆盖 move.c 的物品转移子集。 |
| 负重模型 | `encumbrance` 传播到 environment（`:22`），room 的 `query_max_encumbrance` 返回 `100000000000`（`room.c:17`，近乎无限） | `Container.max_weight`（`:247`），仅容器自身，无环境传播 | **遗漏（N10）**：engine 无 room 级负重传播。LPC 房间 track 内容物总重（虽上限近乎无限）；engine 房间 Container 不校验总重（max_weight 默认 None）。风险：若需要「房间承重限制」（如桥塌）无挂载点。 |
| 卸装备 | `unequip` 先于 move（`:55`） | 无（`Equippable` 是占位，`components.py:269` 明注「M1 不实现 wield/wear」） | **遗漏**：engine 未实现装备系统，transfer 不处理卸装。 |
| 堆叠 | 无 | `Stackable` 合并/拆分（`:209`/`:326`） | **正面偏差（P3）**：engine 支持数量拆分与同名合并。 |
| 防嵌套循环 | 无 | `_is_descendant`（`:309`） | **正面偏差（P3）**：防 `put A in B` 而 B 已在 A 内。 |
| 否决钩子 | 无（move 返回 notify_fail） | `on_get`/`on_drop` vetoable（`:186-205`） | **正面偏差**：engine 有声明式否决钩子。 |
| 自动 look | 有（`:117` 玩家移动后 `command("look")`） | 无（transfer 不 look；look 在 `commands._cmd_go:534`） | **偏差**：transfer 路径不自动 look（仅物品转移无需 look）。 |

---

## 8. scene_loader.py vs LPC 房间加载：inherit ROOM / setup / replace_program 映射

**LPC 房间加载模式**（`d/village/alley1.c` 典型）：
1. `inherit ROOM;`（继承 room.c 基类）。
2. `create()`：`set("short", ...)` / `set("long", @LONG ... LONG)` / `set("exits", [...])` / `set("outdoors", ...)` / `set("objects", [...])` / `set("cost", ...)` / `set("no_clean_up", ...)`。
3. `setup()`（调 `room.c:277` = `seteuid(getuid())` + `reset()`）。
4. `replace_program(ROOM)`（room object 的程序变为 ROOM，丢弃 .c 特有代码）。
- 出口目标用 `__DIR__"sroad3"` 相对路径（`:15`），加载时解析为绝对路径再 `load_object`。

**engine scene_loader.py**（1619 行）：
1. `load_scene(scene_path)`（`:81`）：读 YAML -> 合并 includes 模板 -> `_build_rooms`（建实体+组件）-> `_build_items`/`_build_npcs` -> `_build_exits`（连出口+门）-> `_build_player` -> `wire_runtime`。
2. `_build_rooms`（`:461`）：每房 `world.create_entity()` + `Identity`+`Description`+`Exits`+`Container` + 能力字段 + 钩子绑定 + 透传未识别字段。
3. `_build_exits`（`:545`）：方向 -> `Exit(target=EntityId, aliases)`，可选 `Door`/`HiddenExit`。
4. 出口目标用房间键（字符串），`room_ids` dict 解析为 EntityId（`:580`）。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 房间定义 | .c 文件（代码） | YAML 条目（数据） | **正面偏差（P1）**：数据驱动，UGC 安全。 |
| 继承机制 | `inherit ROOM`（LPC OOP 继承） | 无继承（组件组合） | **正面偏差**：engine 用组合替代继承，更灵活。 |
| `replace_program(ROOM)` | 丢弃 .c 特有代码，room 变纯 ROOM | 无等价（房间本就是数据） | **不适用**：engine 无代码丢弃问题。 |
| `setup()` | `seteuid` + `reset()` | `wire_runtime(world, scene_path)`（`:151`）接线所有子系统 | **覆盖**：engine wire_runtime 统一接线 nature/AI/渡口/交战/门禁/昏迷苏醒。 |
| 出口路径解析 | `__DIR__"sroad3"` 相对路径 | 房间键字符串 -> `room_ids` dict | **正面偏差**：无路径问题，键全局唯一。 |
| includes / 模板合并 | 无（每房独立 .c） | `includes` + `_merge_includes_templates`（`:253`） | **正面偏差**：支持模板复用与多文件组织。 |
| 未识别字段 | 无（字段需代码处理） | 透传到 `extension_data`/`entity_extension_data`（`:397`/`:410`） | **正面偏差（P4）**：前向兼容，引擎升级旧数据不丢。 |
| 运行时建门 | `create_door`（`:227`） | 仅加载期从 YAML `door` 字段建 | **遗漏（N11）**：见第 3 节。 |
| `random_of` 出口 | 无 | `_exit_random_of_target`（`:696`）加载期随机选定 | **正面偏差**：engine 支持出口随机化（LPC 需手写代码）。 |

---

## 9. scenes.py：场景抽象覆盖度

**engine scenes.py**（44 行）：
- 定义三个场景路径常量：`DEFAULT_SCENE_PATH`（m1_default_scene.yaml）、`MVP_SCENE_PATH`（m2_mvp_scene.yaml）、`XINGXIU_MECHANICS_PATH`（xingxiu_mechanics.yaml）（`:21-25`）。
- 三个入口函数：`build_world`（`:28`）、`load_mvp_scene`（`:37`）、`load_xingxiu_mechanics`（`:42`），各自调 `load_scene`。
- 无场景抽象层（无场景类型/接口/注册表），仅路径选择。

| 维度 | 评价 |
|------|------|
| 覆盖度 | **极薄**：scenes.py 是路径选择器，非场景抽象。所有加载逻辑在 `scene_loader.py`。 |
| 风险 | 无场景元数据（版本/作者/题材包归属）、无多场景索引、无场景间切换。M3 UGC 题材包加载需额外抽象（当前由 `pack.py` 承担，不在本模块）。 |
| 与 LPC 对比 | LPC 无统一场景抽象（每房 .c 独立加载），engine 的 YAML 单文件 + `load_scene` 已是更结构化的方案。 |

---

## 10. 跨模块遗漏：玩家船（ship.c 591 行）

**LPC**（`inherit/room/ship.c`）：完整玩家船系统：
- `do_start`（`:73`）：开船（检查所有权 `is_owner`，删岸 `exits/enter`，设船 `navigate/locx/locy`）。
- `navigate`（`:112`）：导航循环（触礁检测 `jiaos`、天气 2 级翻船概率、海盗/海怪/财宝随机事件）。
- `do_go`（`:do_go`）：操舵方向移动（按 `seashape` 数据校验坐标可达性）。
- `do_stop`（停船）、`do_lookout`（瞭望找陆地）、`do_locate`（定位坐标）。
- `shipweather`/`niceweather`（海况天气循环）、`do_ready`/`do_drop`（靠岸/翻船）。
- `time_out`（`:49`）：900+random(500) 秒不操作自动翻船。
- `valid_leave`（`:55`）：最后一人下船时延迟 5s 收船。
- `clone/ship/seaboat1-3.c`：具体船实例。

**engine**：全仓 grep `ship`/`navigate`/`lookout`/`locate`/`seaboat` **空结果**。无玩家船系统。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 玩家船 | 591 行完整系统（导航/天气/瞭望/所有权/触礁/翻船/随机事件） | 无 | **遗漏（N1）**：engine 完全缺失玩家船。MVP 场景清单含「水陆交通（渡口/渡船）」，但渡船（ferry.py）与玩家船（ship.c）是两类不同系统——ferry 是 NPC 艄公摆渡，ship 是玩家自驾。engine 只有简化渡船，无玩家船。 |

---

## 11. 跨模块遗漏：坐骑系统覆盖度（engine Mount/Riding/Terrain vs clone/horse/）

**LPC**（`clone/horse/` 22 匹 + `horse.h`）：
- `horse.h:7` `condition_check()`：骑乘体力衰减。`jingli<=10` -> 坠骑 + `receive_wound("qi", 150)` 受伤 + `set_leader(0)` 解除跟随 + `unconcious()`。
- `horse.h:32` `jingli<=30` -> 喘气播报；`:37` `jingli<=max/3` -> 大口喘气。
- `horse.h:48` `init()`：房有 `resource/grass` 且马未饱 -> 吃草恢复 jingli + food。
- `baima.c:20` `set("wildness", 6)` / `msg_fail`/`msg_succ`/`msg_trained`：驯服系统（NPC_TRAINEE 继承）。
- `set_leader`：跟随机制（马跟随骑手或主人）。

**engine**（`components.py:705` `Mount` + `:715` `Riding` + `:724` `Terrain` + `commands.py:468-528` 骑乘移动）：
- `Mount`：`ability` + `jingli_current` + `jingli_max` + `ridden_by`。
- `commands.py:513-521`：骑乘移动扣 `jingli_current`，归零 -> `Unconscious` + 解除骑乘 + 文案「你摔了下来」。**无 qi 扣减**。
- `commands.py:476`：地形 `cost > mount.ability` -> 拒走「这地方骑不过去」。
- `components.py:728` `Terrain.cost`：地形通行难度。

| 维度 | LPC | engine | 偏差/风险 |
|------|-----|--------|-----------|
| 体力衰减 | 3 档播报（10/30/max/3） | 归零才倒 | **偏差**：LPC 有渐进播报（喘气->大口喘气->倒）；engine 只在归零时倒。 |
| 坠骑受伤 | `receive_wound("qi", 150)`（`:22`） | 无 qi 扣减 | **遗漏（N7）**：engine 坠骑无伤害，仅文案。 |
| 吃草恢复 | `resource/grass` + `add("jingli")`（`:48-55`） | `RoomResources` 明注「grass 未打通」（`:577`） | **遗漏（N6）**：engine 无马匹吃草恢复精力。 |
| 跟随 | `set_leader`（`:27`） | 无 | **遗漏（N5）**：engine 无 leader/follow 机制。 |
| 驯服/训练 | `wildness`/`msg_fail`/`msg_succ`/`msg_trained`（`baima.c:20-24`） | 无 | **遗漏（N8）**：engine 无马匹驯服系统。 |
| 马匹种类 | 22 种（baima/heima/camel/donkey/... 各有独立属性） | 单一 `Mount` 组件模板（可配但无内建种类） | **偏差**：engine 可经 YAML 配置不同马匹，但无 22 种现成实例。 |
| 地形通行 | 无（LPC 无 terrain 概念） | `Terrain.cost` vs `Mount.ability` | **正面偏差**：engine 引入地形通行难度，比 LPC 更结构化。 |

---

## 附录：证据索引

### LPC 一手源码
- `adm/daemons/natured.c`（193 行）：昼夜/天气/广播/event_fun。
- `adm/etc/nature/day_phase`（65 行）：8 时段数据。
- `inherit/room/room.c`（281 行）：基础房间（门/reset/make_inventory/setup/valid_leave）。
- `inherit/room/ferry.c`（157 行）：渡口渡船（yell/check_trigger/on_board/arrive/close_passage）。
- `inherit/room/ship.c`（591 行）：玩家船（start/navigate/go/lookout/locate/weather）。
- `feature/move.c`（154 行）：通用移动（encumbrance/weight/unequip）。
- `clone/horse/horse.h`（84 行）：马匹体力/坠骑/吃草/跟随。
- `clone/horse/baima.c`（45 行）：白马实例（驯服属性）。
- `d/village/alley1.c`（25 行）：房间定义模式样本。
- `d/REGIONS.h`：35 区域映射。
- `cmds/std/look.c:46`：户外描述拉取。

### engine 模块
- `engine/src/openmud/nature.py`（554 行）：NatureState/DayPhase/Weather/attach_nature。
- `engine/src/openmud/world.py`（280 行）：World ECS 容器。
- `engine/src/openmud/room_hooks.py`（732 行）：RoomHook 协议 + 8 内置机关钩子。
- `engine/src/openmud/room_details.py`（112 行）：RoomDetails N1 匹配 + 名(id) 扫描。
- `engine/src/openmud/ferry.py`（147 行）：FerryCrossing/FerryState/attach_ferries。
- `engine/src/openmud/directions.py`（114 行）：方向别名/中英文解析。
- `engine/src/openmud/transfer.py`（363 行）：transfer 物品转移原语。
- `engine/src/openmud/scene_loader.py`（1619 行）：YAML 场景加载器。
- `engine/src/openmud/scenes.py`（44 行）：场景路径选择器。
- `engine/src/openmud/components.py`：组件定义（Description/Exits/Door/Doors/Mount/Terrain/Ferry/RoomDetails 等）。
- `engine/src/openmud/commands.py:450-542`：go 命令（门检查/地形/骑乘/精力/移动）。
- `engine/src/openmud/ai.py:270`：spawn_scan 补刷。
