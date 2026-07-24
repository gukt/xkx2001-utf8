# 创作者视角：世界空间层可扩展性审视

> 角色产出（UGC 游戏专家）。从题材包创作者视角审视「世界空间层」可扩展性：摆房间、连区域、设门、设交通、配 Nature 的工作流与痛点；机制暴露/封装边界；6414 房间规模对工具的要求；地图资产可交易性；现有 engine 对创作者友好度评估。
>
> 证据要求已逐条标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。

## 1. 创作者工作流与痛点（LPC 现状 vs engine 现状）

### 1.1 摆房间：从「写 .c + 手填 exits mapping」到「写 YAML + 结构校验」

**LPC 现状**：创作者每加一个房间，要手写一份 `.c` 文件，固定套用 `inherit ROOM` + `create()` 模式。证据：`d/village/alley1.c`（24 行）——`set("short","小巷")` + `set("long", @LONG ... LONG)` + `set("exits", (["east":__DIR__"sroad3", "northwest":__DIR__"alley2"]))` + `set("outdoors","xxx")` + `set("cost",1)` + `setup()` + `replace_program(ROOM)`。

**痛点 1（断链风险高）**：`exits` 是 `方向 -> "文件名字符串"` 的 mapping，用 `__DIR__` 相对路径拼接（`alley1.c:15` `"east" : __DIR__"sroad3"`）。拼错文件名、改名后忘改引用，编译期不报错——只有玩家真走到那个出口、`load_object` 返回 0 时才静默断链。6414 房间规模下，这种字符串引用断链是日常维护负担。

**痛点 2（门单向声明）**：门要在房间 `create()` 里 `create_door(dir, data, other_side_dir, status)` 手动声明（`inherit/room/room.c:227`）。证据 `d/city/bingqiku.c:22` `create_door("north","铁门","south",DOOR_CLOSED)` ——只在本房建了门，对岸 `bingyin.c` 必须独立再建一次或靠 `check_door` 同步（`room.c:218`）。两侧状态一致性靠运行时 `open_door`/`close_door` 的 `from_other_side` 回调维护（`room.c:184`、`room.c:209`），声明期不校验对岸是否真的有对应门。

**engine 改善**：场景数据改为声明式 YAML，`load_scene` 在加载期对结构性错误收口成 `SceneLoadError`（`scene_loader.py:88-94`，消息含文件路径与出错条目键）。出口目标在加载期校验存在性：`_build_exits`（`scene_loader.py:580-584`）`if target_key not in room_ids: raise SceneLoadError(...指向未定义的房间...)`。门只需在一侧声明 `door: locked` + `key: <物品键>` + `consume_key` + `hidden_until_unlocked`（`scene_loader.py:728-744` `_exit_door`），钥匙物品先于出口构建（`scene_loader.py:139-140` 先 `_build_items` 后 `_build_exits`）。**创作者不再需要在两侧各写一次门声明。**

### 1.2 连区域：从「`__DIR__` 跨目录字符串」到「房间键引用 + includes 模板」

**LPC 现状**：跨区域连接靠官道房间链 `d/*/road*.c`，出口仍是 `__DIR__"相邻房间"` 字符串。跨区域（如 village→city）要写绝对或相对路径字符串。35 区域、6414 房间的拓扑是这些字符串 mapping 交织而成的隐式图，没有任何图级校验工具。

**engine 现状**：出口目标是「房间键」（如 `huashan_birth`、`yangzhou_guangchang`）而非文件路径（`m2_mvp_scene.yaml:9-11` `exits: { north: huashan_guide, south: road_huashan_yz }`）。加载期全量校验所有出口目标已定义（`scene_loader.py:580`）。创作者写错键名，启动那一刻就报错，不用走到那个出口才发现。

**痛点 3（单文件天花板）**：engine 的 `includes` 只支持 `items`/`npcs` 模板段合并，**不支持 rooms 段**（`scene_loader.py:200` `_INCLUDE_ALLOWED_SECTIONS = frozenset({"items","npcs"})`；`scene_loader.py:262` 注释「被 include 文件若再写 includes 或其它顶层段则失败」）。这是 M2 spec H2 的既定决定（「一份不算太大的 YAML 完全够用，多文件拼接留给需要多个题材包并存时再设计」）。但在 6414 房间规模下，全量房间拓扑挤在单份 `scene.yaml` 里，对创作者的文件组织、diff 审查、多人协作是硬约束。详见第 3 节。

### 1.3 设门：声明期校验 + 钥匙物品引用

**LPC**：门状态是 `doors` mapping（`room.c:15` `static mapping doors`），`create_door` 在 `create()` 里填，`valid_leave` 检查 `DOOR_CLOSED` 拦截通行（`room.c:267-275`）。门与钥匙的绑定关系分散在各房 `create()` 逻辑里，没有声明期的「这把钥匙能开哪扇门」的集中校验。

**engine**：门状态收敛到出口声明 `{ to: <房间>, door: locked, key: <物品键>, consume_key: true, hidden_until_unlocked: true }`（`scene_loader.py:728-744` `_exit_door` / `scene_loader.py:758` `_door_key_item_id`）。钥匙物品的 entity id 在建出口前就绪（`scene_loader.py:93` docstring「物品先于出口是因为出口的门锁可引用物品作为钥匙」）。`hidden_until_unlocked` 要求 `door: locked`（`scene_loader.py:593-597`），声明期就拦下「隐藏门没锁」这类逻辑矛盾。**对创作者：门/钥匙/一次性消耗/隐藏通道全部在一个出口条目里声明完毕，不用跨文件追。**

### 1.4 设交通：渡口配对校验 vs 玩家船缺口

**LPC 渡口**：创作者继承 `inherit/room/ferry.c`（157 行），在房间 `create()` 里 `set("boat", __DIR__"duchuan2")` + `set("opposite", __DIR__"taihu2")` + `set("water_name","湖")`。证据 `d/taihu/matou2.c:20-22`。`ferry.c` 用 `do_yell`/`check_trigger`/`on_board`/`arrive`/`close_passage` 的 `call_out` 链驱动渡船周期（`ferry.c:55-157`）。

**痛点 4（渡口手动配对，断链无校验）**：`boat` 和 `opposite` 是字符串路径，填错或对岸文件改名，`find_object` 返回 0 时 `ferry.c:70` 只打一行 `ERROR: boat not found`，不阻断加载。两岸配对关系（A 岸 opposite 指向 B 岸，B 岸 opposite 应指向 A 岸）完全靠创作者自觉，没有任何声明期校验。

**engine 改善**：渡口声明收敛到房间 `ferry:` 段（`m2_mvp_scene.yaml:220-223` `ferry: { far_bank: ferry_east, cross_interval: 3, direction: across }`）。`_resolve_ferry_refs`（`scene_loader.py:1400-1434`）在加载期做两件事：①校验 `far_bank` 指向的房间已定义且挂了 `Ferry` 组件（`scene_loader.py:1408-1422`）；②校验两岸 `far_bank` **互相指向**（`scene_loader.py:1425-1434` 互指校验）。**创作者把两岸写反、只写一边、指向不存在的房间，加载期就报错。** 这是 LPC 完全没有的图级完整性校验。

**痛点 5（玩家船完全缺失）**：LPC `inherit/room/ship.c`（591 行）是一套完整的玩家驾驶船只系统：`do_start`/`do_go`/`do_stop`/`do_lookout`/`do_locate`/`navigate`/`shipweather`/`niceweather`/`do_ready`/`do_drop`（`ship.c:73-590`），含网格导航（`navigate` 按 locx/locy 移动，`ship.c:202-218`）、触礁/海盗/美人鱼等随机事件（`ship.c:143-183`）、天气影响（`shipweather`/`niceweather`，`ship.c:484-511`）、瞭望定位（`do_lookout`/`do_locate`，`ship.c:341-473`）、所有权/劫船（`is_owner`，`ship.c:475-482`）。港口与岛屿坐标硬编码在 `clone/ship/seashape.h`（`ship.c:11` `#include "/clone/ship/seashape.h"`），创作者加新岛屿要改头文件。

**engine 缺口**：`ferry.py`（147 行）只实现了 NPC 渡口（`FerryCrossing`/`FerryState`/`attach_ferries`/`_on_ferry_tick`/`_apply_crossing_exits`），**没有任何玩家驾驶船只的等价物**（grep `engine/src/openmud/` 无 `ship`/`navigate`/`lookout`/`harbor`/`island` 模块）。从创作者视角，若题材包需要「玩家自己开船跨海探索」这类玩法，现有声明式能力撑不起来——这是真实表达力缺口，不是文案问题。LPC 的港口/岛屿坐标硬编码在头文件里也不数据驱动，直接照搬不可取，但机制本身（网格导航 + 随机海遇 + 天气交互）在题材包创作层有价值。

### 1.5 配 Nature：全局单例 vs 声明式时段 + 房间贴纸

**LPC 现状**：Nature 是全局单例 daemon `adm/daemons/natured.c`（193 行）。8 个时段数据写在 `adm/etc/nature/day_phase`（纯文本表，`natured.c:161` `read_table` 解析）。`update_day_phase` 用 `call_out` 循环驱动（`natured.c:54-77`），切换时 `message("outdoor:vision", msg, users())` 向**所有**户外玩家广播（`natured.c:71`）。户外判定靠房间 `set("outdoors","xxx")`（`alley1.c:19`）。

**痛点 6（Nature 全局无差异）**：所有户外房间共享同一套时段与天气。`natured.c` 是单进程单例，创作者无法让「扬州城里下雨、华山脚下晴」——天气是全局的，`weather_msg` 5 档（`natured.c:11-17`）对全服户外同时生效。`event_sunrise`（`natured.c:83-97`）在日出时全局存档所有玩家，是全局副作用，创作者无法干预。

**engine 改善**：创作者在场景顶层 `nature:` 段声明 `day_phases` 列表（每段 `name`/`length`/`time_msg`/`desc_msg`/`rain_desc_msg`，`m1_default_scene.yaml:173-194`），加 `weather_change_chance`（`nature.py:149`）。时段数与文案完全由题材包决定（LPC 固定 8 段，engine 可 4 段可 N 段）。更关键的是 `LocalNature` 能力（`capabilities.py:1072-1078` `known_fields={"local_nature"}`）+ `EffectiveNature`（`nature.py:334-356` `resolve_effective_nature`）允许**房间级 Nature 贴纸**覆盖全局（ADR-0013）：某房间可声明 `local_nature: { phase: night }` 强制夜里，或 `weather: rain` 强制下雨。**创作者第一次能让「鬼屋永远黑夜」「密洞永远下雨」这类局部氛围设计成立**，LPC 做不到。

**痛点 7（Nature 配置缺引擎自带默认）**：`m2_mvp_scene.yaml`（737 行 MVP 场景）顶层**没有 `nature:` 段**（grep 确认）。创作者若不写 `nature:`，引擎回退默认四相（`nature.py` 注释「无段时回退默认四相」）。这意味着 MVP 官方包本身没展示 Nature 创作面，新创作者缺少「照着抄」的范例。`m1_default_scene.yaml:173` 有完整范例但只是测试场景，不在 MVP 可玩路径上。

## 2. 机制暴露/封装边界（哪些给创作者，哪些封住）

### 2.1 适合暴露给题材包创作者的机制

| 机制 | LPC 来源 | engine 暴露方式 | 评价 |
|------|----------|----------------|------|
| 房间拓扑（short/long/exits/aliases） | `alley1.c` set 系列 | YAML `rooms:` 段 + `_ROOM_INTRINSIC_FIELDS`（`scene_loader.py:201-212`） | 已暴露，声明式，友好 |
| 门/钥匙/隐藏通道 | `room.c:227` create_door | 出口 `{door/key/consume_key/hidden_until_unlocked}`（`scene_loader.py:728`） | 已暴露且增强（声明期校验） |
| 渡口周期 | `ferry.c` set("boat"/"opposite") | 房间 `ferry: {far_bank/cross_interval/direction}`（`m2_mvp_scene.yaml:220`） | 已暴露且增强（互指校验 `scene_loader.py:1425`） |
| 昼夜时段 | `natured.c` + `day_phase` 文件 | 顶层 `nature: day_phases:` 列表（`m1_default_scene.yaml:173`） | 已暴露，题材包自定义时段数与文案 |
| 天气概率 | `natured.c:11` weather_msg | `weather_change_chance`（`nature.py:149`） | 已暴露 |
| 房间局部 Nature | （LPC 无） | `local_nature` 能力（`capabilities.py:1072`） | engine 新增，LPC 无对应 |
| 移动消耗 | `alley1.c:21` set("cost",1) | `Terrain` 能力 `known_fields={cost,terrain}`（`capabilities.py:1030-1036`） | 已暴露 |
| 坐骑（基础） | `clone/horse/baima.c` + horse.h | NPC `mount: {ability/jingli_current/jingli_max}`（`m2_mvp_scene.yaml:542`）+ 商店 `shop: [{mount: <键>, price}]`（`m2_mvp_scene.yaml:552-554`） | 已暴露，声明式买马 |
| 房间景物细节 | `room.c` item_desc 机制 | `RoomDetails` 能力 `details:` 段（`capabilities.py:1037`；`m2_mvp_scene.yaml:42-53` shi_shi/qi_gan） | 已暴露，含别名 + 语义色 markup（`room_details.py`） |
| 随机出口 | （LPC 靠 room 逻辑） | `exits: {<方向>: {random_of: [...]}}`（`scene_loader.py:696`） | engine 新增，加载期选定 |
| NPC 拦路 | （LPC 靠 valid_leave 脚本） | `block_exits: {<方向>: {npc: <键>, deny_message: ...}}`（`scene_loader.py:612-658`） | 已暴露且数据驱动（`m2_mvp_scene.yaml:101-103` ling_hanlin 拦西向） |

### 2.2 应封装（不直接暴露给题材包创作者）的机制

| 机制 | LPC 来源 | engine 处理 | 封装理由 |
|------|----------|-------------|----------|
| 渡船 call_out 周期状态机 | `ferry.c:55-157` check_trigger/on_board/arrive/close_passage | `ferry.py:102` `_on_ferry_tick` + `_apply_crossing_exits`（`ferry.py:116-132`） | 创作者只声明两岸配对与间隔，周期翻转由引擎 tick 驱动，不应让创作者写 call_out |
| 门状态对岸同步 | `room.c:184/209` from_other_side 回调 | 加载期单侧声明 + 运行时命令层同步 | 对岸同步是引擎一致性责任，不是创作者数据 |
| Nature 全员广播 | `natured.c:71` message("outdoor:vision",...) | `on_nature_change` 事件分发（`nature.py:282-284`）+ 户外广播订阅者 | 广播路由是引擎基础设施，创作者只写文案 |
| Nature 重启对齐 | `natured.c:28-52` init_day_phase 按 localtime 校准 | `NatureState` 时钟对齐（`nature.py` 注释「重启对齐」） | 时钟对齐是引擎耐久性，不是题材数据 |
| 房间 reset/objects 补刷 | `room.c:76-155` reset + make_inventory | `SpawnerBlueprint`/`item_spawners`/`random_object_slots`（`world.py:87-91`）+ ADR-0010 槽位补刷 | 补刷策略是引擎运行时态，创作者只声明 `objects: {<键>: <数量>}` |
| 坐骑力竭坠骑 | `horse.h:8-41` condition_check（含 jingli<=10 昏厥坠骑、<=30 喘气、<=mj/3 大口喘气） | `commands.py:513-521` 移动时 drain + jingli==0 昏厥+坠骑 | **部分封装**：engine 只在移动时扣精力并在 0 时坠骑，LPC 的周期性 condition_check（chat_chance 50 驱动，即使不走也衰减）与中间警告（喘气/大口喘气）未覆盖。创作者声明 `mount.jingli_max` 后，衰减/警告节奏由引擎管，但比 LPC 弱 |
| 物品重量/容量 | `feature/move.c:47-82` move + encumbrance 检查 | `transfer.py` TransferResult/TransferContext（物品转移层）+ `Terrain.cost`（移动消耗） | 注意：engine `transfer.py` 是**物品**转移（堆叠/拆分/重量），不是玩家移动；玩家移动消耗走 `commands.py:481-521`。两者分离是合理的封装边界 |
| 玩家船导航网格 | `ship.c:112-282` navigate + seashape.h 硬编码 harbors/islands | **无 engine 等价物** | 若未来暴露，应是声明式「海域网格 + 港口/岛屿坐标 + 随机事件池」，而非 LPC 的头文件硬编码 |

### 2.3 封装边界的关键判断

**应封装的共性**：所有「运行时状态机翻转」「跨实体一致性同步」「时钟对齐」「全员广播路由」都是引擎责任，创作者只贡献**声明式静态数据**（两岸是谁、间隔几 tick、时段文案、坐骑上限）。这与 CLAUDE.md「机制归引擎、内容归题材包」边界一致。

**应暴露的共性**：所有「这个世界长什么样」（房间/出口/门/景物/时段文案/天气概率/移动消耗/坐骑属性）都该是题材包数据。engine 用「能力注册表 + 已知字段集 + 透传」手法（`capabilities.py` `CapabilitySpec.known_fields` + `scene_loader.py:174-198` `_TOP_LEVEL_KNOWN_SECTIONS`）让新增能力是纯增量，不破坏旧包——这对创作者友好度是正面的（见第 5 节）。

## 3. 6414 房间/35 区域规模对创作工具的要求

### 3.1 规模事实

- LPC `d/` 下 35 区域（`d/REGIONS.h:4-39` 声明 35 个 region_names 映射）、6414 个 `.c` 房间文件（`find d/ -name "*.c" | wc -l` = 6414）。
- 最大区域：beijing 625 / dali 467 / city 扬州 441 / xingxiu 388 / shaolin 368；最小 village 华山村 63（逐区 `find` 统计）。
- 每个房间一份独立 `.c`，平均 20-30 行，总量约 15-19 万行房间定义代码。

### 3.2 对工具的要求

**要求 1（图级完整性校验）**：6414 节点的隐式图，手动保证「每个出口都有对端」「每个门两侧状态一致」「每个渡口两岸配对」不可能靠人眼。LPC 完全没有这类工具——断链靠玩家走到才发现。engine 的 `load_scene` 加载期校验（`scene_loader.py:580` 出口目标存在性、`scene_loader.py:1425` 渡口互指）是基础，但还不够：**缺「孤岛房间检测」（没有任何入口的房间）、「死路检测」（只有进没有出的房间）、「门两侧一致性校验」（A 声称 north 有门，B 的 south 是否也有门）的图遍历校验**。这些在 6414 规模下是刚需，MVP 小场景（m2_mvp_scene 约 30 房间）感觉不到。

**要求 2（文件组织/拆分）**：单份 `scene.yaml` 装下 6414 房间不现实（m2_mvp_scene 737 行才约 30 房间，线性外推 6414 房间约 15 万行 YAML）。engine 的 `includes` 只允许 `items`/`npcs` 模板段（`scene_loader.py:200`），**rooms 段不能拆分到多文件**。这对官方武侠题材包（若未来要做全量）是硬约束。M3 spec 明确「不支持目录里有多份场景文件拼接」（`m3-ugc-loop-creation-surface/spec.md` Implementation Decisions A1），理由是「多文件拼接留给需要多个题材包并存时再设计」。从创作者视角，这个决定在 MVP 小场景成立，但一旦题材包规模过百房间就需要重新评估。

**要求 3（可视化/预览）**：LPC 无编辑器、无预览，创作者改完只能 `update` 房间再走一遍。engine 同样无编辑器（ADR-0006 明确「编辑器/留言板丢弃，Web 评审台 post-MVP」），但交付了 `--validate` 校验模式（M3 块 C，`m3-ugc-loop-creation-surface/spec.md` 块 C）作为「评审台最小替身」——创作者改完跑 `python -m openmud --pack <目录> --validate`，秒级反馈字段/引用错误，不用进 REPL。**这是 6414 规模下唯一可用的迭代通道**，但它只校验语法与引用，不校验图拓扑（孤岛/死路/平衡性），也不给可视化地图。

**要求 4（diff/审查友好）**：YAML 声明式天然比 LPC `.c` 代码更适合 git diff 与 code review。6414 房间的增量改动（加一条出口、改一个门状态）在 YAML 里是几行 diff，在 LPC `.c` 里要 `update` 整个文件。这对多人协作维护大题材包是实质性优势。

## 4. 创作者经济视角：地图资产作为题材包核心资产的可交易性

### 4.1 商业化支撑点对照

CLAUDE.md 架构不变量第 6 条列出四个「要留位置但不强制 MVP 实现」的支撑点。世界空间层与其中两个直接相关：

- **支撑点 #2（题材包资产元数据：创作者归属 + 版本溯源）**：engine 已落地「简化版」——`manifest.yaml` 的 `id`/`version`/`creator`/`title` 四字段（`pack.py:25-33` `PackManifest`；`m3-ugc-loop-creation-surface/example-pack/manifest.yaml` 实例 `id: derelict-outpost` / `version: "0.1.0"` / `creator: m3-example`）。从创作者经济视角，`creator` 字段是未来「分成账本」的数据种子：地图作为题材包核心资产，其创作者归属已在 manifest 里有位置。但 MVP 不做任何归属校验/分成逻辑（`m3-ugc-loop-creation-surface/spec.md` 块 A User Story 2 明确「即便 M3 本身不实现任何归属校验/分成逻辑」）。

- **支撑点 #4（世界实例隔离：每个题材包独立进程）**：CLAUDE.md 架构不变量第 1 条「单进程单 World」（ADR-0009）与第 6 条「世界实例隔离」共同约束：每个题材包在自己的进程里跑，进程间不共享世界状态。从创作者经济视角，这意味着一个题材包的地图资产是**自包含的**——`scene.yaml` + `manifest.yaml` 即全部，不依赖其他包的房间。这对可交易性是正面的：买一个题材包 = 买一份完整可玩的世界，不存在「这个包引用了另一个包的房间」的跨包依赖纠缠。

### 4.2 地图资产的可交易性评估

**正面（可交易的基础已在）**：
- 题材包是自包含目录（`manifest.yaml` + `scene.yaml`），可整体分发（`pack.py:63` `load_pack(pack_dir)`）。
- 包有独立身份（`id`/`version`）与创作者归属（`creator`），未来平台可按 `id` 上架/检索/计费。
- 主题无关性已被非武侠示例包证明（`derelict-outpost` 科幻题材，3 房间，M3 块 D，`m3-ugc-loop-creation-surface/issues/04` 记录「未发现 GAP」——现有声明式能力撑得起非武侠世界）。

**缺口（影响可交易性但 MVP 不要求）**：
- **无版本兼容性声明**：`manifest.yaml` 只有 `version` 字符串，没有「依赖引擎哪个版本」「依赖哪些能力」的声明。创作者升引擎后旧包是否还能跑，没有契约。这对平台化（一个平台跑多个不同版本题材包）是潜在摩擦点。
- **无资产清单/体积约束**：6414 房间级别的题材包，加载内存、启动时长、`--validate` 耗时都未约束。平台若要上架大量题材包，需要 per-pack 资源预算（CLAUDE.md 支撑点 #3「消费/参与度埋点」相关，但那是埋点不是预算）。
- **无跨包组合**：当前一个进程只能加载一个包（ADR-0009 单进程单 World），创作者无法把「我的地图」与「别人的 NPC 包」组合发售。CLAUDE.md 明确「承载扩展靠题材包数量横向扩展，不是单世界做大」，所以跨包组合不是 MVP 目标，但从创作者经济视角，它限制了「地图作者 + 剧情/NPC 作者协作分成」这类模式。

### 4.3 地图作为核心资产的特殊性

地图（房间拓扑 + 出口 + 门 + 交通）是题材包里**最难迁移、最难复用**的资产：
- 文学性内容（房间 long 描述、景物 details）与题材强绑定，换题材即作废。
- 拓扑结构（出口图）是创作者的核心设计劳动，但 engine 不提供「导出拓扑为可视化地图」「拓扑模板复用」能力。
- 相比之下，NPC 行为（`behaviors`）、物品能力（`CAPABILITIES`）更接近「可复用组件」。这意味着在创作者经济里，地图作者的劳动估值与保护需求最高，但工具支撑最低。

## 5. 现有 engine 对创作者友好度的影响（scene_loader / world.py 评估）

### 5.1 友好之处

**① 声明式 + 加载期收口**：`load_scene`（`scene_loader.py:81-152`）把所有结构性错误收口成 `SceneLoadError`，消息含文件路径 + 出错条目键（`scene_loader.py:88-94`）。创作者不用读 Python 堆栈，报错直接指向「场景文件 X 的房间 Y 的出口 Z 指向未定义的房间 W」。这对迭代效率是数量级提升（对比 LPC `load_object` 返回 0 的静默断链）。

**② 能力注册表 + 已知字段集 + 透传**：新增房间能力是纯增量（`capabilities.py:82-92` `CapabilitySpec` + `ROOM_CAPABILITIES` 列表，`capabilities.py:1001-1079`）。旧场景数据里引擎不识别的字段不报错不丢弃，原样透传到 `world.extension_data`（`world.py:71`）或 `entity_extension_data`（`world.py:266`）。**创作者用旧引擎的字段写包，引擎升级后不用重写**（`scene_loader.py:174-177` 注释明确「M3 引入规则引擎时旧场景数据不必重写」）。这是「不锁死未来」的关键友好度设计。

**③ 校验模式（--validate）**：M3 块 C 交付的秒级反馈通道，不启动 REPL、不碰存档（`m3-ugc-loop-creation-surface/spec.md` 块 C）。报错风格与真实加载一致（`spec.md` 块 C User Story 11），不会「校验过了、一启动却报另一种错」。

**④ 包身份 + 指向加载**：`load_pack(pack_dir)`（`pack.py:63`）+ `--pack <目录>` CLI，让内容包可来自仓库任意位置（`spec.md` 块 B User Story 5）。创作者不用把包塞进 `engine/data/`，不用重新打包发布引擎。

**⑤ 渡口互指校验**：`_resolve_ferry_refs`（`scene_loader.py:1400-1434`）是 LPC 完全没有的图级校验，直接消除「两岸写反」这类高频创作错误。

### 5.2 不友好/需警惕之处

**① 单文件 rooms 段天花板**：`includes` 不支持 rooms（`scene_loader.py:200`）。大题材包（百房间级以上）的 `scene.yaml` 会膨胀到难以 diff/审查。这是创作者组织内容的硬约束，M3 spec 的「一份 YAML 够用」假设在小场景成立、在官方武侠全量包不成立。

**② 透传的双刃剑**：未知字段静默透传（`world.py:71` extension_data）让旧包不破坏，但也意味着**创作者拼错字段名（如 `outdoor` 写成 `outdors`）不报错**——字段被透传吞掉，房间静默失去户外属性，玩家收不到 Nature 广播但没有任何报错。在 6414 规模下，这类「静默失效」比报错更难排查。LPC 至少在 `set()` 后能 `query()` 自查，engine 的透传让创作者误以为字段生效了。

**③ scene_loader.py 体量（1619 行）对创作者透明度**：创作者不直接读 `scene_loader.py`，但它的校验逻辑分散在 `_build_exits`/`_exit_door`/`_resolve_ferry_refs`/`_validate_shop_inventories`/`_validate_faction_refs` 等十几个函数里（`scene_loader.py:545/728/1400/1437/1474`）。创作者遇到报错时，要理解「为什么这条 exit 被拒」可能要追多个函数。这不是缺陷而是复杂度代价，但意味着**创作者文档必须把「哪些字段组合合法、哪些互斥」讲清楚**（如 `hidden_until_unlocked` 必须配 `door: locked`，`to` 与 `random_of` 互斥，`scene_loader.py:593/673`）。目前没有面向创作者的字段参考文档（只有 spec 与代码注释）。

**④ Nature 创作面在 MVP 包未展示**：`m2_mvp_scene.yaml` 无 `nature:` 段（grep 确认），新创作者缺少「照着抄」的范例。`m1_default_scene.yaml:173` 有范例但是测试场景。创作者第一次配 Nature 要去翻 `nature.py` 的 `DayPhase`/`NatureState` 字段（`nature.py:44-163`），门槛偏高。

**⑤ 玩家船完全无支撑**：`ship.c`（591 行）的玩家驾驶导航系统在 engine 无任何等价物（grep 确认）。创作者若要做「跨海探索」题材，现有能力撑不起来。这不是友好度问题而是表达力缺口，但会影响「题材无关」宣言在航海类题材上的可信度。

**⑥ world.py 对创作者基本透明但有一处需注意**：`World.extension_data`（`world.py:71`）与 `entity_extension_data`（`world.py:266`）是透传数据的落脚点。创作者一般不直接碰，但调试「我写的字段被透传到哪了」时要理解这个机制。`world.py:117-140` 的 `push_message`/`drain_messages`/`pending_messages` 是收件箱，创作者不直接用，但理解 Nature 广播如何到达玩家要追到这里。

## 6. 总结：创作者视角的核心判断

1. **engine 的声明式 + 加载期校验路线对创作者友好度是数量级提升**，直接消灭了 LPC 的字符串断链、门单向声明、渡口手动配对三大高频痛点（证据：`scene_loader.py:580` 出口校验、`scene_loader.py:1425` 渡口互指校验、`scene_loader.py:728` 门单侧声明）。
2. **单文件 rooms 段天花板是最大的规模隐患**：`includes` 不支持 rooms（`scene_loader.py:200`），6414 房间级别的官方武侠全量包无法用单份 YAML 组织。MVP 小场景成立，但官方包若要做全量需重新评估多文件拼接。
3. **透传机制是双刃剑**：保护了向后兼容，但让字段拼错静默失效（`world.py:71` extension_data），6414 规模下比报错更难排查。
4. **玩家船导航是真实表达力缺口**：LPC `ship.c` 591 行的驾驶/网格/天气/瞭望系统在 engine 无等价物，航海类题材包创作者会撞墙。
5. **地图资产可交易性基础已留位但未实现**：`manifest.yaml` 的 `creator`/`version`（`pack.py:25-33`）是分成账本数据种子，但无版本兼容性声明、无资产清单约束、无跨包组合（ADR-0009 单进程单 World）。地图作为最难迁移的核心资产，工具支撑最低。
6. **Nature 创作面已超越 LPC**（`local_nature` 房间贴纸，`capabilities.py:1072`，LPC 无对应），但 MVP 官方包未展示，新创作者缺范例。
