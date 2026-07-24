# UGC 创作层应暴露的最小表面（引擎架构师 B）

> 角色：引擎架构师 B。任务：从题材包（UGC）创作者视角，界定「世界空间层」最小创作面--
> 创作者能摆什么、能连什么、能配什么，以及哪些必须锁在 engine core 不让创作者碰。
> 证据优先级：LPC 一手源码（`d/`、`inherit/room/`、`adm/daemons/natured.c`、`clone/horse/`、`clone/ship/`）
> > engine 现有模块（`engine/src/openmud/`，仅作批判对照，不作反向脑补来源）。
> 每条结论标注来源；无来源标注的推断一律不出。

---

## 0. 前置约束（决定创作面形状）

调研范围内影响「创作者能碰什么」的硬约束，来自项目 ADR，不是本角色推导：

1. **UGC 内容包禁止可执行逻辑**（[ADR-0005](../../../../../docs/adr/0005-m3-ugc-loop-creation-surface.md) + [ADR-0012](../../../../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)）：M3 创作面 = manifest + 声明式场景数据（演进自现有 `scene_loader` YAML）。UGC 包**禁止**携带可信房间钩子；`--validate` 遇 UGC 钩子应失败。可信 Python 钩子只对官方/题材包开放，经窄 `ctx`（`add_exit`/`remove_exit`/`schedule`/`message_*`）改世界。**这是本文件所有结论的最高约束**：下文「创作者」默认指 UGC 创作者，能声明的是数据，不是代码。
2. **单进程单 World**（[ADR-0009](../../../../../docs/adr/0009-single-process-single-world.md)）：Nature 时钟是 World 级单例，创作者不能开第二套气候循环。
3. **不做 LPC 行为等价**（[ADR-0001](../../../../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）：下文引用 LPC 是为提取「创作者曾需要声明什么」的设计灵感，不是要求新引擎复刻其字段语义。

---

## 1. 房间创作面：创作者需要声明什么

### 1.1 房间基础字段

LPC 房间定义模式（`d/village/alley1.c` L6-24）在 `create()` 里 `set()` 一组字段后 `setup()` + `replace_program(ROOM)`：

| LPC `set()` 字段 | 含义 | 来源 |
|---|---|---|
| `short` | 房间短名 | `d/village/alley1.c` L8 |
| `long` | 房间长描述（heredoc） | `d/village/alley1.c` L9-13 |
| `exits` | 方向 -> 目标房间路径 mapping | `d/village/alley1.c` L14-17 |
| `outdoors` | 户外标志（LPC 是字符串如 `"xxx"`/`"taihu"`，非 bool） | `d/village/alley1.c` L19；`d/taihu/matou.c` L20 `set("outdoors","taihu")` |
| `cost` | 移动消耗 | `d/village/alley1.c` L21 `set("cost",1)` |
| `objects` | NPC/物品生成表（文件名 -> 数量） | `inherit/room/room.c` L91 `query("objects")`、L115-153 `reset()` |
| `no_clean_up` | 是否豁免清理 | `inherit/room/room.c` L90 `set("no_clean_up",0)` |
| `item_desc` | 可检视物件描述 | `d/shaolin/hanshui1.c` L25-27 `set("item_desc",(["river":...]))` |

engine 现状（批判对照）：
- `scene_loader.py` L461-480 `_build_rooms` 读 `name`/`long`/`aliases`/`outdoors`，组装 `Description`+`Identity` 组件。`outdoors` 被归一化为 `bool`（L480 `outdoors=bool(data.get("outdoors",False))`），**丢失了 LPC 的区域归属字符串**（见 1.4）。
- `cost` 落到 `Terrain` 组件（`components.py` L724-728 `Terrain.cost`），`scene_loader.py` L189 `cost: 8` 是 YAML 用法。
- `objects` 走房间中心放置（[ADR-0010](../../../../../docs/adr/0010-room-centric-objects-placement.md)），`scene_loader.py` L137 `_collect_room_objects`。
- `item_desc` 落到 `RoomDetails` 组件（`components.py` L539-549），对应 `room_details.py`。

**创作面结论**：UGC 创作者应能声明 `name`/`long`/`aliases`/`outdoors`/`cost`/`objects`/`item_desc`。这组字段与 LPC 高度同构，engine 也已覆盖，作为最小面是稳的。`no_clean_up` 是 LPC 的清理调度细节，新引擎用槽位补刷蓝图（`world.spawners`/`world.item_spawners`，`world.py` L87-91）替代，**不应暴露给创作者**。

### 1.2 出口（exits）

LPC `exits` 是 `方向 -> 目标房间路径` 的 mapping（`d/village/alley1.c` L14-17），目标用 `__DIR__"sroad3"` 相对路径。`inherit/room/room.c` L267-275 `valid_leave()` 检查门状态后放行。

engine 现状：
- `scene_loader.py` L545-609 `_build_exits` 把 YAML `exits` 段连成 `Exits` 组件条目。出口支持三种形态（L661-693 `_exit_target`）：裸字符串键 / `{ to: <key> }` / `{ random_of: [...] }`。
- 出口可选挂 `aliases`（`_exit_aliases` L713）、`door` 状态（`_exit_door` L728）、`key`/`consume_key`（`_door_key_item_id` L758）、`hidden_until_unlocked`（L589-601 迁入 `HiddenExits`）。
- **拓扑校验已有**：L580-584，出口目标不在 `room_ids` 时抛 `SceneLoadError`「指向未定义的房间」。

**创作面结论**：UGC 创作者应能声明出口的方向、目标、方向别名、门状态、钥匙物品、隐藏出口。`random_of` 是声明式小原语（ADR-0012 明确「加载期 `random_of` 可作为小声明式原语，不必进钩子」），可对 UGC 开放。双向对称性由创作者自己保证两条 exit 互指（engine 不自动补反向出口，与 LPC 一致：LPC 也是两侧房间各自 `set("exits",...)`）。

### 1.3 门（doors）

LPC 门机制（`inherit/room/room.c`）：
- `create_door(dir, data, other_side_dir, status)`（L227-257）：在出口上挂门，门有 `name`/`id`/`other_side_dir`/`status`（`DOOR_CLOSED` 等）。门要求出口已存在（L232-234 `error("attempt to create a door without exit.")`）。
- `open_door`/`close_door`（L168-216）：通过 `find_object(exits[dir])` 找到对岸房间，调对岸的 `open_door(other_side_dir, 1)` 协商双侧同步。
- `check_door`（L218-225）：对岸房间回写 `status`，保证两侧门状态一致。
- `valid_leave`（L267-275）：门关着时 `notify_fail` 阻止离开。
- `look_door`（L158-166）：门作为 `item_desc` 回调，看门时返回开/关状态文案。

实例：`d/xixia/bianmen.c` L21 `create_door("west","木门","east",DOOR_CLOSED)`。

engine 现状：
- `components.py` L127-170 `DoorState`（OPEN/CLOSED/LOCKED）+ `Door`（state/key_item_id/consume_key）+ `Doors`（按方向索引）。门独立于 `Exit`（L144-146 注释：可被箱子/密室入口等非出口实体复用）。
- `scene_loader.py` L728-756 `_exit_door`/`_door_state`：`door` 字段值映射成 `DoorState`，`key` 解析为物品 EntityId。
- **门的双向对称性缺失**：engine 不做 LPC 的 `check_door` 协商。`d/xixia/bianmen.c` 的门只在 `west` 方向声明，对岸 `chaifang.c` 是否声明对称门未知；engine 也不校验双侧门状态一致。

**创作面结论**：UGC 创作者应能声明门的状态（open/closed/locked）、门名、钥匙物品、钥匙是否消耗。**门的双向同步是 engine core 责任，不应让创作者在两侧各写一遍**（LPC 的 `check_door`/`other_side_dir` 机制证明这是 engine 级协调，不是数据声明）。但 engine 现状没有这个协调层，是一个待补缺口（见 6.2）。

### 1.4 区域归属

LPC `d/REGIONS.h` 声明 35 个区域 mapping（`"village":"华山村"`、`"city":"扬州"` 等）。房间 `set("outdoors","taihu")` 的字符串值本质是区域标签，`natured.c` 的 `outdoor_room_description()` 和 `message("outdoor:vision", msg, users())` 广播按户外标志筛选。

engine 现状：`outdoors` 被降级为 `bool`（`scene_loader.py` L480），**区域归属信息丢失**。`world.py` 没有 region 概念（`world.room_ids` L97 只是房间键 -> entity id 映射）。

**创作面结论**：UGC 创作者应能声明房间的区域归属（如 `region: taihu`），engine 据此分组。这对 Nature 广播作用域、fast travel、创作者经济（按题材包内区域统计参与度，[架构不变量 6](../../../../../CLAUDE.md)）都是前置依赖。LPC 的字符串 `outdoors` 值恰好暗示了「户外标记 + 区域归属」是同一个声明面。engine 现状把两者合一为 bool 是损失。

### 1.5 移动消耗（cost）

LPC `set("cost",N)`（`d/village/alley1.c` L21）是房间级移动消耗，`feature/move.c` 的 `move()` 不直接读 `cost`（`move.c` 主要管负重/装备卸下），实际 cost 扣减在移动命令层。

engine 现状：`Terrain.cost`（`components.py` L728）+ `MOUNT_JINGLI_PER_TERRAIN_COST`/`WALK_JINGLI_PER_TERRAIN_COST`（L733/737）系数。骑乘扣坐骑精力，步行扣玩家精力。

**创作面结论**：UGC 创作者应能声明房间 `cost`（通行难度）。系数（`MOUNT_JINGLI_PER_TERRAIN_COST`）是引擎全局常量，**不应暴露给创作者调**（会让创作者能改全局移动节奏，破坏题材包间一致性）。

---

## 2. 交通创作面

### 2.1 渡口（Ferry）

LPC 渡口（`inherit/room/ferry.c`，157 行）是 trigger 驱动的动态出口：
- 创作者声明三字段（`d/taihu/matou.c` L21-23、`d/shaolin/hanshui1.c` L37-39）：
  - `set("name","江"/"湖")`：水域名（用于文案）
  - `set("boat", __DIR__"duchuan")`：渡船房间路径
  - `set("opposite", __DIR__"taihu")`：对岸房间路径
- trigger 机制（`ferry.c`）：`do_yell("船家")` -> `check_trigger()`（设 `exits/enter`=boat、boat 的 `exits/out`=本岸）-> `call_out("on_board",15)` -> `call_out("arrive",20)` -> `call_out("close_passage",20)`。周期共 55 秒，全程靠 `call_out` 调度，创作者不写代码。
- 渡船房间本身（`d/taihu/duchuan.c`）是普通 `ROOM`，只设 `short`/`long`/`outdoors`/`cost`。
- 两渡口房间**不直接互指 exits**，靠 `boat` 房间做中转：`check_trigger` 时动态插 `exits/enter`/`exits/out`。

engine 现状：
- `ferry.py`（147 行）：`Ferry` 组件（`far_bank`/`cross_interval`/`direction`，`components.py` L772-784）+ `FerryCrossing`/`FerryState`。`attach_ferries` 扫描 `Ferry` 组件建运行时态，`_on_ferry_tick` 按 `cross_interval` 翻转停靠岸，`_apply_crossing_exits` 动态增删 `Exit`。
- 创作者声明（`m2_mvp_scene.yaml` L220-223）：`ferry: { far_bank: ferry_east, cross_interval: 3, direction: across }`。
- **互指校验已有**：`scene_loader.py` L1424-1434 `_resolve_ferry_refs` 校验两岸 `far_bank` 必须互相指向。
- **偏差**：engine 没有 `boat` 中转房间概念（LPC 的渡船是一个独立房间，玩家 `enter` 后在船上等待）。engine 的渡口是「两岸直接翻转 Exit」（`ferry.py` L123-132），玩家不走中转房。这简化了创作面（创作者不用造渡船房间），但丢了「在船上等待」的体验切片。

**创作面结论**：
- UGC 创作者应能声明：两岸房间各挂 `ferry: { far_bank, cross_interval, direction }`。**两岸必须互指**（engine 已校验）。
- `cross_interval`（往返周期）对创作者开放，但应有下限护栏（`ferry.py` L87 `max(1, ferry.cross_interval)` 已做）。
- `direction`（过河方向名）对创作者开放。
- **trigger 机制锁在 engine core**：LPC 的 `do_yell`/`check_trigger`/`on_board`/`arrive`/`close_passage` 是调度逻辑，创作者只声明数据。engine 的 `_on_ferry_tick`/`_apply_crossing_exits` 同理。创作者不应能改周期内的文案时序（「艄公把踏脚板搭上堤岸」这类）。
- **渡船房间**：engine 现状不暴露中转房，若未来要支持「在船上等待」体验，应作为 engine 的可选模式，不是 UGC 创作者自己拼。

### 2.2 船（Ship / 玩家船航海）

LPC 玩家船（`inherit/room/ship.c`，591 行）是重度玩法：
- 创作者声明（通过 `clone/ship/seaboat1-3.c` + `clone/ship/harbor.h` + `clone/ship/seashape.h`）：
  - 港口房间坐标：`set("navigate/locx",X)`/`set("navigate/locy",Y)`（`ship.c` L100-101 `do_start` 从港口读坐标）
  - 港口表：`harbor.h` 的 `harbors` mapping（港口路径 -> locy）、`islands` mapping（岛屿路径 -> [locx,locy]）、`wildharbors` 列表
  - 暗礁表：`seashape.h` 的 `jiaos` 列表（`ship.c` L126-133 `navigate` 检查触礁）
  - 船本身：`set("cost",5)`、`set("exits",(["down":cabin]))`（`seaboat1.c` L16-23）
- 航海机制（`ship.c`）：`do_start`（开船，删港口 `exits/enter`、设船坐标）-> `navigate`（call_out 周期推进，按 `do_go` 方向改 locx/locy，检查触礁/到港/随机事件）-> `do_lookout`（算距最近岛屿方位）-> `do_locate`（算距最近港口距离）-> `do_ready`（到港踢玩家下船）-> `do_drop`（翻船，玩家昏迷冲岸）。
- 所有权：`is_owner`（L475-482）--船上若有 `combat_exp` 高于开船者的玩家，则不让开船（「长这么大连一点江湖规矩都不懂」）。
- 天气：`shipweather`/`niceweather`（L484-511），三档天气影响 `long_desc` 文案。
- 随机事件：`navigate` L143-183，10 种（海怪/财宝/海盗/神迹/Titanic/燃烧鸟/海妖歌/大眼睛/美人鱼/极光），纯 `tell_room` 文案。

engine 现状：**完全没有 ship 模块**。`world.py` 无 ship 运行时态，`components.py` 无 Ship 组件。

**创作面结论**：
- 玩家船航海是**重型玩法**（591 行 + 坐标系 + 所有权 + 天气 + 随机事件），不应在 M3/UGC 最小面暴露。
- 若未来要做，创作者应能声明：港口坐标、港口表、岛屿表、暗礁表、船模板。但航海调度（`navigate`/`do_lookout`/`do_locate`/`do_ready`/`do_drop`）全部锁在 engine core。
- 所有权（`is_owner` 基于战斗力比较）是玩法规则，不是数据声明，应锁 engine。
- 随机事件表（10 种）可以作为声明式数据开放给创作者（类似 `random_of`），但事件触发概率/调度锁 engine。
- **M3/UGC 阶段建议**：不暴露 ship 创作面，渡口（2.1）已覆盖「过河」基础切片。

### 2.3 坐骑（Mount / Horse）

LPC 坐骑（`clone/horse/horse.h` + `clone/horse/baima.c`）：
- 创作者声明（`baima.c` L9-38，在 NPC 模板上）：
  - `set("ridable",1)`：可骑
  - `set("max_jingli",630)`：最大精力
  - `set("ability",4)`：通行能力
  - `set("wildness",6)`：野性（影响驯服）
  - `set("value",80)`：价值
  - `set("str"/"con"/"dex"/"int",N)`：属性
  - `set("attitude","peaceful")`：态度
  - `set("msg_fail"/"msg_succ"/"msg_trained",...)`：驯服文案
  - `set("chat_chance",50)` + `set("chat_msg",({(:condition_check:)})`：周期调 `condition_check`
- 体力机制（`horse.h` L7-41 `condition_check`）：
  - `jingli<=10`：马匹昏厥、骑手坠落受伤（`receive_wound("qi",150,...)`）
  - `jingli<=30`：「只在喘气，渐渐地快跑不动了」
  - `jingli<=max_jingli/3`：「大口大口地喘着粗气」
  - 草地吃草回精（L48-56：`resource/grass` 房间回 `food`+`jingli`）
- 骑乘关系：`rider`/`rided`（马持骑手、骑手持马）、`set_leader`（跟随）。

engine 现状：
- `components.py` L705-719 `Mount`（ability/jingli_current/jingli_max/ridden_by）+ `Riding`（mount_id）+ `Terrain`（cost）。
- 创作者声明（`m2_mvp_scene.yaml` L542-545）：`mount: { ability: 5, jingli_current: 80, jingli_max: 80 }`。
- 商店卖马（`m2_mvp_scene.yaml` L552-554）：`shop: [{ mount: yangzhou_horse, price: 50 }]`，`scene_loader.py` L1437-1459 `_validate_shop_inventories` 校验坐骑模板有 `Mount` 组件。
- 移动扣精力：`MOUNT_JINGLI_PER_TERRAIN_COST`（`components.py` L733）。
- **偏差/遗漏**：
  - engine 的 `Mount` 没有 `wildness`/`attitude`/驯服文案/属性（str/con/dex/int）--这些是驯服玩法的前置，engine 未建。
  - engine 没有「马匹昏厥坠落受伤」机制（LPC `horse.h` L18-29 的 `receive_wound` + `unconcious`）。
  - engine 没有「草地吃草回精」机制（`horse.h` L48-56 的 `resource/grass`）--`RoomResources` 组件（`components.py` L573-580）存在但未接马匹回精。
  - engine 没有 `set_leader` 跟随机制。

**创作面结论**：
- UGC 创作者应能声明：坐骑模板的 `ability`/`jingli_current`/`jingli_max`（engine 已支持）。这覆盖了「官道骑乘」基础切片。
- `wildness`/驯服文案/属性/态度是驯服玩法的一部分，**若未来开放驯服**，应作为声明式数据（文案模板）+ engine core 规则（驯服概率计算）。M3 阶段不暴露。
- 体力衰减阈值（10/30/max_jingli/3）是 engine 常量，**不应让创作者调**（创作者能设 `jingli_max` 已足够控制坐骑耐力）。
- 坠落受伤机制锁 engine core。
- 草地回精：若开放，创作者声明房间 `resource: grass`（LPC `resource/grass`），engine 负责回精逻辑。`RoomResources` 组件已存在但未接，是待补缺口。

---

## 3. Nature 创作面

### 3.1 时段表（day_phase）

LPC 时段表是数据驱动的（`adm/daemons/natured.c` L161-189 `read_table`）：`adm/etc/nature/day_phase` 是纯文本表，8 段（dawn/sunrise/morning/noon/afternoon/evening/night/midnight），每段 `length`/`time_msg`/`desc_msg`/`event_fun`。创作者改这个文件就能改时段序列、文案、回调名。

engine 现状：
- `nature.py` L44-56 `DayPhase`（name/length/time_msg/desc_msg/rain_desc_msg）。
- `DEFAULT_PHASES`（L83-112）是题材无关默认四相（dawn/day/dusk/night），总长 1440 游戏分钟。
- `_parse_nature_config`（L460-499）解析 YAML `nature: { day_phases: [...] }` 段，从 `world.extension_data["nature"]` 透传。
- `attach_nature`（L398-449）优先级：显式参数 > `config_from_yaml` > `extension_data["nature"]` > `DEFAULT_PHASES`。
- **偏差**：
  - LPC 8 段 -> engine 默认 4 段（engine 注释 L82「题材无关默认四相」，刻意简化，非遗漏）。
  - LPC `event_fun` 字段（`event_dawn`/`event_sunrise`/`event_noon`）在 engine 无对应。LPC 的 `event_sunrise` 做自动存档（`natured.c` L83-97）、`event_common` 做库存检查（L100-142）。engine 把这些 event 钩子统一为 `on_nature_change` 事件分发（L279-318 `advance_tick`）。
  - LPC `time_msg`/`desc_msg` 带 ANSI 颜色码（`day_phase` 文件 L27-64 的 `[1;36m...[37;0m`），engine 的 `DayPhase` 是纯文本。

**创作面结论**：
- UGC 创作者应能声明 `nature: { day_phases: [{name, length, time_msg, desc_msg, rain_desc_msg}], game_minutes_per_tick: N }`。engine 已支持。
- 时段名（`name`）是创作者自由命名（LPC 固定 8 个，engine 允许任意），但 `NIGHT_PHASES`/`DAY_PHASES`（`nature.py` L125-126）是 engine 硬编码集合--**创作者自定义的相位名若不在集合内，`is_night`/`is_day` 谓词会返回 False**（L174-188）。这是一个隐性护栏缺口：创作者声明 `name: "twilight"` 后，条件 DSL 里的 `is_night` 不会把它算夜里。应在加载期校验相位名是否落在已知日夜集合，或允许创作者声明相位归属。
- `game_minutes_per_tick`（游玩节奏）对创作者开放，但应有下限（`nature.py` L156 已校验 `>=1`）。
- 时钟推进 / `align_from_clock`（L257-277）锁 engine core。

### 3.2 天气消息

LPC `natured.c` L11-17 `weather_msg` 5 档（万里无云/几朵云彩/白云飘/厚云堆积/乌云密布），但**只是文案数组，没有实际天气状态机**（`natured.c` 没有翻转天气的逻辑，天气始终是「晴」，`weather_msg` 从未被 `update_day_phase` 使用）。

engine 现状：
- `nature.py` L37-41 `Weather` 枚举（CLEAR/RAIN 二态）。
- `_maybe_change_weather`（L320-330）按 `weather_change_chance` 概率翻转。
- `_WEATHER_CLEAR_MSG`/`_WEATHER_RAIN_MSG`（L129-130）是硬编码文案。
- `DayPhase.rain_desc_msg` 支持时辰×天气二维文案。

**创作面结论**：
- 天气状态机（CLEAR/RAIN 二态翻转）锁 engine core，创作者不能自己加第三种天气。
- `weather_change_chance`（翻转概率）对创作者开放（engine 已支持，`attach_nature` 参数）。
- 天气文案（`_WEATHER_*_MSG`）目前硬编码，**应改为题材包可声明**（类似 `day_phases` 的 `weather_msgs: {clear: "...", rain: "..."}`）。这是 engine 现状的护栏缺口。
- LPC 的 5 档天气文案是「描述丰富度」，不是「5 种天气状态」--创作者要的是更多文案变体，不是更多天气状态。engine 的二态天气 + `rain_desc_msg` 二维文案已覆盖功能性需求。

### 3.3 event_fun 钩子

LPC `day_phase` 表的 `event_fun` 字段（`event_dawn`/`event_sunrise`/`event_morning`/`event_noon`/`event_afternoon`/`event_evening`/`event_night`/`event_midnight`）是**引擎级回调名**，`natured.c` L72-73 `call_other(this_object(), event_fun)` 按名字调 `natured.c` 自己的方法：
- `event_sunrise`（L83-97）：自动存档（`link_ob->save()`/`ob[i]->save()`）。
- `event_common`（L100-142，每个相位都调）：清理无环境 NPC、库存检查。
- 其余 `event_*`（dawn/morning/noon/afternoon/evening/night/midnight）在 `natured.c` 中**未定义**（`call_other` 调不存在的方法是 no-op）。

engine 现状：
- `on_nature_change` 事件（`nature.py` L29 + L279-318 `advance_tick` 分发 `NatureChangeContext`）。
- `_broadcast_nature_change`（L517-535）是 `on_nature_change` 的订阅者，推户外广播。
- 自动存档不在 Nature 系统里（engine 的 `save.py` 是显式调用，不挂 `on_nature_change`）。
- **偏差**：LPC 的 `event_fun` 是「相位切换时触发引擎级行为」，engine 的 `on_nature_change` 是「相位切换时分发事件」。前者是硬编码行为（存档/库存检查），后者是可订阅事件。engine 的设计更解耦，但**UGC 创作者不能订阅 `on_nature_change`**（ADR-0012：UGC 禁可执行逻辑）。

**创作面结论**：
- `event_fun` 钩子**不对 UGC 创作者暴露**。LPC 的 `event_sunrise`（自动存档）和 `event_common`（库存检查/NPC 清理）是 engine core 行为，创作者不应能声明「这个相位触发什么函数」。
- 题材包（官方可信）可以经 `on_nature_change` 订阅做题材特定行为（如「夜里 NPC 闲聊」），但走窄 `ctx`，不是 UGC 数据声明。
- 创作者能做的是声明 `time_msg`（相位切换时的广播文案），这已覆盖「玩家看到天亮了」的体验需求。

### 3.4 户外广播

LPC `natured.c` L71 `message("outdoor:vision", day_phase[...]["time_msg"]+"\n", users())` 向**所有在线玩家**广播（`users()` 是全员），但只有户外房间的玩家在 `outdoor_room_description()` 时看到描述。

engine 现状：
- `_broadcast_nature_change`（`nature.py` L517-535）遍历 `_outdoor_player_ids`（L502-514，`PlayerSession`+`Position`+房间 `Description.outdoors`），向每位户外玩家 `push_message`。
- 室内玩家不收。

**创作面结论**：
- 户外广播通道**锁在 engine core**。创作者不能直接调 `message("outdoor:vision",...)`（LPC）或 `world.push_message`（engine）。
- 创作者能做的是声明 `outdoors: true`（房间是否户外）和 `time_msg`（广播文案）。广播的筛选逻辑（谁收、谁不收）是 engine 责任。
- **偏差警示**：LPC 广播给 `users()`（全员）但只有户外玩家看到描述；engine 只给户外玩家 `push_message`。两者等价，engine 更高效。但 LPC 的 `outdoors` 字符串值（区域标签）在 engine 丢失（见 1.4），导致 engine 无法按区域筛选广播作用域。

### 3.5 房间级局部天气（贴纸）

[ADR-0013](../../../../../docs/adr/0013-local-nature-room-sticker.md)：房间可挂 `LocalNature` 组件（`components.py` L583-590），YAML 键 `local_nature`，覆盖 `phase`/`weather`。查询时按房间合成读数（`nature.py` L344-368 `resolve_effective_nature`）。贴纸是静态的，不随 tick 翻转。

**创作面结论**：
- UGC 创作者应能声明 `local_nature: { phase: "night", weather: "rain" }`，让「山顶永远是夜雨」。engine 已支持。
- 贴纸覆盖的 `phase` 必须是当前 World 相位表已有名（ADR-0013 L16），这是加载期应校验的护栏（engine 现状 `_phase_by_name` 在运行期回退当前相，L250-255，不是加载期失败）。

---

## 4. 应锁在 engine core 不让创作者碰的

汇总（按「为什么不能让创作者碰」分类）：

| 锁定项 | 理由 | LPC 来源 | engine 现状 |
|---|---|---|---|
| 广播通道（`message("outdoor:vision")`/`push_message`） | 创作者不能直接给玩家推消息，只能声明文案 | `natured.c` L71 | `nature.py` L517-535（已锁，UGC 无 API） |
| 时钟推进 / `call_out` 调度 | 创作者不能控制时间流速 / 调度周期 | `natured.c` L50-51 `call_out("update_day_phase",...)` | `nature.py` L279-318 `advance_tick`（已锁） |
| `event_fun` 钩子（存档/库存检查） | 引擎级行为，不是数据 | `natured.c` L83-97/100-142 | `on_nature_change` 事件（已锁，UGC 禁订阅） |
| 渡船 trigger 时序（`on_board`/`arrive`/`close_passage`） | 调度逻辑，创作者只声明周期 | `ferry.c` L89-139 | `ferry.py` L102-132（已锁） |
| 船航海调度（`navigate`/`do_lookout`/`do_locate`/`do_drop`） | 重度玩法逻辑 | `ship.c` L112-282/341-473/513-537 | 无（未来若做也锁 engine） |
| 坐骑体力衰减阈值 / 坠落受伤 | 引擎常量，不是数据 | `horse.h` L18-41 | `components.py` L733 常量（已锁） |
| 移动精力扣减系数 | 全局节奏，不题材包间一致 | `move.c` L76-82 负重检查 | `components.py` L733/737 常量（已锁） |
| 拓扑一致性校验 | 引擎责任，不是创作者自检 | `room.c` L232-234 门要求 exit 存在 | `scene_loader.py` L580-584/L1424-1434（已做部分） |
| 门的双向同步（`check_door`/`other_side_dir`） | 引擎级协调 | `room.c` L218-225/250-253 | **缺失**（engine 不协商双侧门状态） |
| NPC 补刷 / `reset` 调度 | 引擎调度 | `room.c` L76-155 `reset` | `world.spawners`/`item_spawners`（已锁） |
| 天气状态机（CLEAR/RAIN 翻转） | 引擎规则 | `natured.c`（无翻转，恒晴） | `nature.py` L320-330（已锁） |
| `valid_leave` 门检查 | 引擎规则 | `room.c` L267-275 | `scene_loader.py` 门 + 命令层（已锁） |

---

## 5. 创作者门槛与护栏

### 5.1 已有的护栏（engine 现状）

| 护栏 | 检查点 | 来源 |
|---|---|---|
| exit 指向不存在目标 | `scene_loader.py` L580-584：`target_key not in room_ids` 抛 `SceneLoadError` | 对齐 LPC `room.c` L232-234 门要求 exit |
| 渡口两岸互指 | `scene_loader.py` L1424-1434：`far_ferry.far_bank != room` 抛错 | LPC 靠 `boat`/`opposite` 两字段隐式约束 |
| 渡口对岸必须挂 Ferry | `scene_loader.py` L1416-1420 | 无 LPC 对应（LPC 靠 `find_object` 运行期失败） |
| 玩家起始房必须存在 | `scene_loader.py` L1315-1317：`start_room` 不在 `room_ids` 抛错 | LPC 无显式校验 |
| 门状态合法值 | `scene_loader.py` L747-754：`door` 必须是 open/closed/locked | LPC `DOOR_CLOSED` 是位掩码常量 |
| 隐藏出口必须有 locked 门 | `scene_loader.py` L592-596：`hidden_until_unlocked` 要求 `door: locked` | 无 LPC 对应（LPC 无隐藏出口概念） |
| 渡口周期下限 | `ferry.py` L87 `max(1, ferry.cross_interval)` | 无 LPC 对应 |
| Nature 相位数非空 | `nature.py` L155 `if not phases` 抛错 | 无 LPC 对应 |

### 5.2 缺失的护栏（建议补）

| 缺失护栏 | 风险 | 建议检查点 |
|---|---|---|
| **孤岛房间**（无出口也无入口） | 创作者造了进不去/出不来的房间，玩家卡死 | 加载期建拓扑图，扫所有房间，标记「无任何出/入口」的房间为 warning（不 fail，因为可能有 hook 动态插出口） |
| **单向出口**（A->B 但 B 没有 A 的反向出口） | 创作者漏写反向，玩家走到 B 回不去 | 加载期扫所有 exit，检查目标房间是否有反向 exit 指回（warning，因为迷宫/单向门是合法设计） |
| **门双侧不对称** | A 侧门 locked 但 B 侧没门，玩家从 B 侧直接进 | 加载期扫所有带门的 exit，检查对岸同方向是否有门且状态一致（error，这是数据错误不是设计选择） |
| **Nature 相位名不在日夜集合** | 创作者声明 `name: "twilight"`，`is_night`/`is_day` 永远 False | 加载期校验相位名是否落在 `NIGHT_PHASES`/`DAY_PHASES`，或允许创作者声明相位归属（`is_night: true`） |
| **LocalNature.phase 不在相位表** | 贴纸 phase 名拼错，运行期回退当前相（`nature.py` L250-255） | 加载期校验 `local_nature.phase` 必须是相位表已有名 |
| **渡口 direction 与出口方向冲突** | 渡口 `direction: across` 但房间已有 `across` 方向的静态 exit | 加载期检查 ferry direction 不与现有 exits 冲突 |
| **坐骑 ability vs Terrain.cost 失衡** | 创作者设 `ability: 1` 但所有官道 `cost: 8`，坐骑永远坠 | 加载期 warning（不是 error，因为可能是有意设计「劣马走不了陡坡」） |

### 5.3 创作者门槛建议

基于 LPC 房间定义模式的简洁性（`alley1.c` 只有 24 行）和 engine YAML 的同构性（`m2_mvp_scene.yaml` 房间段与 LPC `set()` 一一对应），UGC 创作者门槛应为：

1. **声明门槛**：一份 YAML 文件，`rooms`/`items`/`npcs`/`player` 四段。最小可玩包只需 2 个房间 + 1 个出口（`example-pack/scene.yaml` 已证明）。
2. **拓扑护栏是 warning 不是 error**：孤岛/单向出口可能是设计意图（密室/单向门），加载期标记 warning 但不 fail。只有「门双侧不对称」「exit 指向不存在目标」是 error。
3. **`--validate` 作为创作门闩**：ADR-0012 明确 UGC 包 `--validate` 遇钩子应失败。同理，`--validate` 应跑全部 5.2 护栏检查，给创作者可读的诊断信息（哪个房间的哪个 exit 指向哪里、缺什么）。
4. **不暴露脚本逃生舱**：创作者不能用 Python 写「如果玩家从北门进则动态开东门」--这是 ADR-0005/0012 的硬约束。动态出口只能用 `random_of`（声明式）或可信钩子（官方/题材包，非 UGC）。

---

## 6. engine 现状批判对照汇总

### 6.1 创作面已覆盖（engine 做对了的）

- 房间基础字段（name/long/aliases/outdoors/cost/objects/item_desc）--`scene_loader.py` `_build_rooms`
- 出口 + 方向别名 + 门 + 钥匙 + 隐藏出口--`_build_exits` + `Exit`/`Door`/`HiddenExits` 组件
- 渡口声明 + 互指校验--`Ferry` 组件 + `_resolve_ferry_refs`
- 坐骑模板（ability/jingli）--`Mount` 组件 + 商店卖马校验
- Nature 时段表 + 节奏配置--`DayPhase` + `_parse_nature_config`
- 房间级局部天气贴纸--`LocalNature` + `resolve_effective_nature`（ADR-0013）
- 出口目标存在性校验--`scene_loader.py` L580-584
- 包外声明式内容包加载--`pack.py` + `load_pack` + `--pack`/`--validate`（M3 已交付）

### 6.2 创作面缺口（engine 待补）

| 缺口 | 影响 | 来源 |
|---|---|---|
| 区域归属（`outdoors` 降级为 bool） | 无法按区域分组广播/fast travel/参与度统计 | `scene_loader.py` L480 vs LPC `set("outdoors","taihu")` |
| 门双侧同步（无 `check_door` 协调） | 创作者须在两侧各写一遍门，易不一致 | `room.c` L218-225 vs engine 无对应 |
| 孤岛/单向出口校验 | 创作者无法发现断链/孤岛 | engine 无拓扑图扫描 |
| Nature 相位名归属校验 | 自定义相位名 `is_night` 永远 False | `nature.py` L125-126 硬编码集合 |
| LocalNature.phase 加载期校验 | 拼错运行期静默回退 | `nature.py` L250-255 运行期兜底 |
| 天气文案硬编码 | 创作者不能改「下起了雨」文案 | `nature.py` L129-130 硬编码 |
| 玩家船（ship）创作面 | 航海玩法无法创作 | `ship.c` 591 行无 engine 对应（M3 不做，post-MVP） |
| 坐骑驯服玩法（wildness/文案/属性） | 驯服切片无法创作 | `baima.c` L20-29 vs `Mount` 无这些字段 |
| 草地回精 | `RoomResources` 未接马匹回精 | `horse.h` L48-56 vs `RoomResources` 未用 |
| `set_leader` 跟随 | 坐骑跟随机制缺失 | `horse.h` L27 vs engine 无对应 |

---

## 7. 一句话结论

UGC 创作层的最小表面 = **声明式 YAML（房间/exits/门/objects/ferry/mount/nature/local_nature）+ engine core 锁住的调度/广播/校验/状态机**。LPC 的 `set()`+`setup()` 模式证明这套声明面足够摆出一个可玩世界；engine 现状已覆盖 80% 的声明面，缺口集中在区域归属、门双侧同步、拓扑护栏校验、天气文案数据化--这些都是 engine core 的补全任务，不是放宽 UGC 创作面的理由。玩家船/驯服/草地回精等重型玩法 post-MVP 再评估，不进 M3 最小面。
