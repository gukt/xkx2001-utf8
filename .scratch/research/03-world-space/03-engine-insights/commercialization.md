# 世界空间层商业化与增长评估

> 调研角色：商业化与增长专家 | 主题：03-world-space（地图 / Nature / 交通）
> 证据来源：仓库根 LPC 一手源码 + `engine/src/openmud/` 已建模块（仅批判对照）。
> 决策基线：[CLAUDE.md](../../../../CLAUDE.md)「架构不变量 6」+ [mvp-scope/issues/06](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) 四个支撑点。
> 红线：[06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md)「玩家侧不 pay-to-win（花钱买加速/便利，不买压倒性优势）」。

## 0. 结论摘要（先看这）

1. **地图资产是题材包的核心可计费资产**，但当前 `PackManifest`（`engine/src/openmud/pack.py:25-36`）只挂了 `id/version/creator/title` 四个身份字段，**没有房间/区域粒度的归属与版本溯源**。要做创作者分成，必须先把「资产 -> 创作者 -> 包」的 provenance 链补到房间级。
2. **交通（坐骑/船/渡口）是天然的「便利性付费点」而非「力量付费点」**，与 Iron Realms 不 pay-to-win 红线兼容。但 LPC 原版 `clone/horse/` 的 `value` 与 `ability` **正相关**（最贵的 `xiaohongma` value=500 / ability=10 同时是最强），这套数值若照搬进付费设计就是 pay-to-win，必须改造成「付费买便利（续航/外观/快捷）」而非「付费买通过能力」。
3. **大世界（6414 房间 / 35 区域）对留存是双刃剑**：探索深度是 MUD 的核心留存抓手，但 `cost` 移动消耗 + 无 fast travel + 迷路成本会直接放大新手流失。MVP 场景清单（[10 号票](../../../mvp-scope/issues/10-mvp-scenes-selection.md)）已收窄到「华山村+扬州子集+少林+沿途」，这是正确的增长取舍。
4. **四个商业支撑点的 engine 预留现状**：货币/账本抽象（**缺**，单货币 `Currency` 无法支持分成追溯）；题材包资产元数据（**部分有**，`PackManifest.creator/version` 在位但无房间级 provenance）；消费埋点（**缺**，`world.pack_manifest.id` 是埋点锚点但无埋点管道）；世界实例隔离（**部分有**，`World` 单进程单 World 已天然隔离，`pack_manifest` 是接缝）。
5. **最该在 engine 留位置、MVP 不实现的三件事**：(a) 双货币账本与「消费三元组（题材包+物品+创作者）」流水；(b) 房间/区域级 provenance 扩展字段；(c) 可打点到 `pack_manifest.id` 的事件埋点 hook（尤其 Nature 广播、移动、渡口/骑乘消费）。

---

## 1. 地图资产作为题材包核心资产

### 1.1 LPC 原始形态：房间是扁平的、无归属的文件

LPC 房间是一个 `.c` 文件，通过 `inherit ROOM;` + `create()` 设置属性 + `replace_program(ROOM)` 完成定义（证据：`d/village/alley1.c:4-23`）。房间身份由文件路径（`__DIR__"sroad3"`）隐式决定，区域归属由目录结构 + `d/REGIONS.h:5-39` 的 `region_names` mapping 声明（35 区域，如 `"city" : "扬州"`、`"village" : "华山村"`）。

关键商业缺陷：
- **无创作者字段**：`alley1.c` / `room.c`（`inherit/room/room.c`）里没有任何作者/版本/来源标记。文件头注释 `//Cracked by Roath` 是转码痕迹，不是资产 provenance。
- **房间间引用靠硬编码路径**：`alley1.c:15-17` 的 `set("exits", (["east" : __DIR__"sroad3", ...]))` 把拓扑焊死在文件路径上。这意味着「把一批房间从一个题材包搬到另一个包」需要改路径，不利于资产组合与二次创作分成。
- **区域边界靠目录隐式表达**：`d/REGIONS.h` 只是展示名映射，没有「区域归属哪个包/哪个创作者」的元数据。

### 1.2 engine 现状：包级 provenance 在位，房间级缺失

`engine/src/openmud/pack.py:25-36` 的 `PackManifest` 已挂了 `id`/`version`/`creator`/`title` 四个字段，`load_pack`（`pack.py:63-82`）把 manifest 挂到 `world.pack_manifest`，`reattach_pack_manifest`（`pack.py:85-98`）支持 restore 后重读。这对应 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) 支撑点 2「题材包资产元数据（创作者归属+版本溯源）」的**包级最小版本**。

但对照 [creator-contract-v0.md](../../../../docs/creator-contract-v0.md) 的 `rooms.*` 已知字段集合（`name, aliases, short, long, exits, objects, ..., cost, terrain, details, ...`），**房间级没有任何归属/来源字段**。`scene_loader.py` 把引擎不认识的键收进 `World.extension_data` / `entity_extension_data`（`world.py:71-72, 266-280`），所以创作者现在可以塞一个 `author` 透传键，但它**不在冻结契约内**（creator-contract-v0.md 第 2 条：「透传不算契约」），随时可能被收编或丢弃，不能作为分成依据。

### 1.3 商业化建议：房间级 provenance 应升为契约字段

要支撑 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) 的「创作者侧按题材包消费分成」，分成的最小单位不应是整个包（一个包可能由多人协作或混合官方+UGC 资产），而应能追溯到房间/区域级。建议（MVP 不实现，但 engine 留位置）：

- 在 `rooms.*` 契约里预留可选 `provenance: { author?, source_pack?, version? }` 段，进 `PackManifest.extra` 之外的冻结字段。
- `PackManifest` 升级方向：从「包身份」扩到「资产清单 + 每项归属」，参考 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) 引用的旧方案 provenance 思路（MVP 简化版本号即可）。
- 房间键（scene YAML 的 `rooms.<key>`）应作为稳定资产 ID，而非 LPC 那样焊死在文件路径上——engine 现已用 `room_ids: dict[str, EntityId]`（`world.py:97`）做了键->实体映射，这是正确方向，键本身可作 provenance 主键。

---

## 2. 交通作为消费点

### 2.1 坐骑：LPC 数值即「越贵越强」的 pay-to-win 隐患

`clone/horse/` 22 个马匹，`set("value", N)` 与 `set("ability", M)` 强正相关。逐档提取（证据：各 `clone/horse/*.c` 的 `create()`）：

| 马匹 | value | ability | max_jingli | 备注 |
|---|---|---|---|---|
| donkey / xiaoma | 10 | 2 | 400 | 最便宜最弱 |
| qingma | 50 | 4 | 550 | |
| baima | 80 | 4 | 630 | |
| chuanma | 100 | 5 | 670 | |
| btcamel / camel | 120 | 8 | 3000 | 骆驼续航极长 |
| bailong | 200 | 5 | 850 | |
| gongma | 220 | 6 | 900 | |
| **xiaohongma** | **500** | **10** | 1000 | 最贵=最强，且 `wildness=20000` 几乎无法驯服（`xiaohongma.c:26-28`），还带 `do_duhe` 渡河/`do_escape` 逃生独占技能（`xiaohongma.c:101-171`） |

`ability` 直接决定骑乘能否通过高 `cost` 地形：engine `commands.py:471-478` 的 `cost > mount.ability` 判定（步行回退扣 `WALK_JINGLI_PER_TERRAIN_COST`，`components.py:735-737`）。即「花更多钱买更强马 -> 能去更多区域」是 LPC 原版的既成逻辑。

**pay-to-win 红线判定**：若把 `xiaohongma` 这类「最贵=最强=独占技能」的坐骑做成真钱付费，直接违反 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md)「不买压倒性优势」红线。

**可接受的付费改造方向（便利性而非力量）**：
- 付费买**续航便利**：马匹 `max_jingli` 恢复速度/草场 buff（`horse.h:48-56` 的吃草恢复逻辑可参数化），不提升 `ability` 上限。
- 付费买**外观**：马匹 `short`/`long` 文案差异（`baima.c:14` 的描述），不影响数值。
- 付费买**快捷召唤**：类似 `xiaohongma.c:51` 的 `whistle` 召唤，而非更强的通过能力。
- **绝不可付费**：`ability`（地形通过力）、`do_duhe` 式独占渡河能力（这等于付费解锁地图区域，是力量优势）。

### 2.2 渡口：天然的非付费便利点

`inherit/room/ferry.c` 的渡船是**完全免费**的：`do_yell`（`ferry.c:28-53`）喊船家即触发 `check_trigger`（`ferry.c:55-91`），全程无任何金钱扣除。`call_out("on_board", 15)` + `call_out("arrive", 20)` + `call_out("close_passage", 20)`（`ferry.c:90, 111, 138`）构成约 55 秒的等待周期。

engine 对照：`engine/src/openmud/ferry.py:102-113` 的 `_on_ferry_tick` 把渡船周期翻转换成 tick 计数（`crossing.ticks_until_flip`），`ferry_status_line`（`ferry.py:53-71`）给玩家等待提示。同样是**免费**的。

商业化潜力（不 pay-to-win）：
- **付费缩短等待**：premium 货币买「优先登船」/「即时离岸」，省的是**时间便利**，不省能力。这与 Iron Realms 的「花钱买便利」完全吻合。
- **付费买渡口可达性提示**：`ferry_status_line` 已给出「约 N 个时辰后到达」（`ferry.py:68, 71`），可做免费基础版+付费精确版。
- **不可付费**：把渡口本身锁成付费（等于锁地图区域，力量优势）。

### 2.3 玩家船：高风险高消耗的「体验型消费点」

`inherit/room/ship.c` 是最复杂的交通系统（591 行）。关键消费相关特征：
- `time_out()`（`ship.c:49-53`）：`call_out("time_out", 900+random(500))`，玩家** idle 超时船翻人落海**，`do_drop()`（`ship.c:513-537`）把玩家打昏+清空背包（保留 `tie lian` 铁链）+随机冲到某港口。
- `navigate()`（`ship.c:112-282`）：`!random(100)` 触礁沉船（`ship.c:128-132`）、`!random(40)` 触发随机海事件（`ship.c:143-183`，海怪/海盗/美人鱼/极光等 10 种）。
- `is_owner`（`ship.c:475-482`）：高 `combat_exp` 玩家可夺取船只控制权（`do_start`/`do_go`/`do_stop` 都先查 `is_owner`，`ship.c:80-82, 293-295, 328-330`）——这是 **PVP 抢船** 机制。
- `harbor.h`：4 个大陆港口 + 3 个海岛港口 + 1 个荒岛（`wildharbors`，荒岛无法唤船，`ship.c:549-556` 的 `do_ready` 在荒岛多等 100 tick）。

商业化潜力：
- **体验型消费**（不 pay-to-win）：航海本身是高风险探索体验，可做 premium 货币买「临时抗风浪 buff」「触礁保险（不沉只受损）」「荒岛召唤救援」。这些买的是**容错便利**，不买战斗力。
- **PVP 抢船是社交留存点**：`is_owner` 的 `combat_exp` 比较是力量门槛，但这是游戏内力量（非真钱），不触红线。可做创作者在题材包里设计「海盗题材包」围绕船只争夺展开。
- **engine 缺口**：`engine/src/openmud/` **没有 ship 模块**（只有 `ferry.py` 渡口）。若未来题材包要做航海消费，engine 需补玩家船抽象（导航坐标系 `locx/locy`、天气 `shipweather`、`islands/harbors` 港口表）。这属于 [post-mvp-backlog](../../../mvp-scope/post-mvp-backlog.md) 范畴，MVP 不做。

---

## 3. 创作者经济：题材包地图创作与分成支撑点

### 3.1 创作表面现状

[creator-contract-v0.md](../../../../docs/creator-contract-v0.md) 冻结了场景 YAML 的字段集合：`rooms.*` / `items.*` / `npcs.*` / `quests.*` / `books.*` 等顶层段 + 实体级已知字段。创作者可用声明式 YAML 摆房间、连出口、设门、配 objects、设 ferry/cost/terrain/outdoors 等。

关键约束（信任边界）：
- [ADR-0012](../../../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)：UGC 包**禁止**声明 `hooks`（`creator-contract-v0.md` 第 162-170 行），运行时改世界的机关只能用引擎/题材包自带 Python，不在 YAML 内联脚本。这限制了 UGC 创作者做「动态交通机关」的能力（如 LPC `ferry.c` 的 `call_out` 周期、`ship.c` 的 `navigate`），只能用声明式 `ferry:` 段（`ferry.py` 的 `Ferry` 组件 + `cross_interval`）。
- `includes`（`creator-contract-v0.md` 第 36-41 行）：只贡献 `items`/`npcs` 模板，不贡献 `rooms`。即**房间必须写在主场景文件**，不能跨文件组合房间资产。这阻碍了「房间资产包」式的二次创作分成。

### 3.2 创作者分成所需的最小数据链

[06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) 支撑点 1 要求「每一笔消费要能追溯到『题材包+物品+创作者』三元」。对照世界空间层：

- **题材包 ID**：`world.pack_manifest.id`（`world.py:105`, `pack.py:32`）已在位，是分成的包级锚点。
- **物品**：`components.py:263` 的 `Valuable` + `ShopEntry`（`components.py:656-668`）的 `price` 已支持单物品定价，`commands.py:993-1007` 的 `_buy` / `_buy_mount`（`commands.py:1011-1033`）扣 `Currency`。但 `Currency` 是**单一银两**（`components.py:650-653`），无 premium 货币，且消费流水**不记录**到任何账本，无法事后结算分成。
- **创作者**：`PackManifest.creator`（`pack.py:34`）在位，但只到包级，不到房间/物品级。一个包内若有多个创作者协作（如官方包+UGC 房间混合），无法区分。

### 3.3 engine 应留的位置（MVP 不实现）

1. **双货币账本抽象**：`Currency` 应预留扩展为「免费货币 + premium 货币」的形状（当前 `amount: int` 单值不够）。每笔消费（`commands.py:1007, 1033` 的 `currency.amount -= price`）应经过一个**可插拔的账本接口**，记录 `(pack_id, item_template_key, creator, currency_type, amount, timestamp)` 流水。MVP 可只走单货币+空账本，但调用点必须留 hook。
2. **物品/房间级 provenance 扩展**：`PackManifest` 预留 `assets` 清单字段（透传进 `extra` 即可，`pack.py:53`），未来升为冻结字段。
3. **消费埋点 hook**：`_buy` / `_buy_mount` / 渡口 tick / 骑乘移动扣精力等关键消费/参与点，应发出可订阅的事件（类似 `ON_NATURE_CHANGE`，`nature.py:29`），供未来埋点管道订阅。当前 `commands.py` 的消费是直接改 `Currency.amount`，无事件发出。

---

## 4. 大世界规模对留存/增长的影响

### 4.1 规模事实

- 6414 房间 / 35 区域（证据：`find d/ -name "*.c" | wc -l` = 6414；`d/REGIONS.h:5-39` 35 区域）。
- 最大区域：beijing 625 房间、dali 467、city（扬州）441、xingxiu 388、shaolin 368。
- 跨区域连接靠官道 `d/*/road*.c` / `*road*.c` 与渡口/船只。

### 4.2 探索深度 vs 新手流失

**探索深度是 MUD 核心留存抓手**：6414 房间的手工内容量是巨大的探索目标，`ship.c` 的随机海事件（10 种）、`xiaohongma` 式隐藏独占技能、`d/xixia/oldwall.c` 式古长城渡口，都是驱动老玩家长期留存的「深度内容」。

**但对新手是双刃剑**：
- **移动消耗**：`alley1.c:21` 的 `set("cost", 1)` 是普遍设置（`d/village/` 多数房间 cost=1，部分室内 cost=0）。engine 对照 `components.py:728` 的 `Terrain.cost` + `commands.py:471-478` 的 `cost > mount.ability` 判定 + `WALK_JINGLI_PER_TERRAIN_COST=2`（`components.py:737`）。步行每房扣 2 精力，骑乘扣 1。新手若无马、无精力管理意识，会频繁撞到「走不动」。
- **无 fast travel**：LPC 原版无任何快速传送（除 `xiaohongma.c:130` 的 `duhe` 渡河独占技能）。6414 房间全靠步行/骑乘，对新手的迷路成本极高。
- **渡口/船只的时间门槛**：`ferry.c` 约 55 秒等待周期、`ship.c` 的 `time_out` 900+ 秒 idle 翻船——这些都是**时间税**，对碎片化玩家不友好。

### 4.3 增长取舍建议

[10 号票](../../../mvp-scope/issues/10-mvp-scenes-selection.md) 的 MVP 场景收窄（华山村+扬州子集+少林+沿途+官道+渡口/渡船+坐骑）是正确的增长策略：**用小切片验证留存，而非靠大世界堆量**。商业化上：

- **MVP 阶段**：小切片降低新手流失，但需保留「探索深度」的留痕——如 `ship.c` 式随机事件、`xiaohongma` 式隐藏内容，作为长期留存锚点。
- **增长阶段**：靠 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md)「题材包数量横向扩展」而非单世界做大。每个题材包是独立世界实例（`world.pack_manifest` + 单进程单 World [ADR-0009](../../../../docs/adr/0009-single-process-single-world.md) 天然隔离），玩家在不同题材包间是独立进度，不存在跨包力量迁移——这天然防 pay-to-win。
- **留存指标埋点（engine 应留 hook）**：移动事件（`commands.py` 的 `go` 命令）、渡口等待（`ferry.py` 的 `ferry_status_line`）、骑乘精力耗尽（`commands.py:514-518` 的 `jingli_current==0` 昏迷）都应发出可订阅事件，供未来打点到 `pack_manifest.id`，衡量「新手卡在哪一步流失」。

---

## 5. 哪些商业支撑点应在 engine 留位置（MVP 不实现但预留）

对照 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) 四个支撑点 + 世界空间层证据：

| 支撑点 | engine 现状 | 缺口 | 建议预留位置 |
|---|---|---|---|
| **1. 货币/账本抽象** | `Currency`（`components.py:650-653`）单货币银两；`commands.py:1007,1033` 直接 `amount -= price` 无流水 | 无 premium 货币、无账本、无消费三元组记录 | `Currency` 升级为双货币形状；消费调用点经可插拔账本接口；MVP 单货币+空账本即可 |
| **2. 题材包资产元数据** | `PackManifest`（`pack.py:25-36`）有 `id/version/creator/title`；`world.pack_manifest`（`world.py:105`）在位 | 无房间/区域级 provenance；`includes` 不贡献 rooms 限制资产组合 | `rooms.*` 契约预留 `provenance` 段；`PackManifest.extra`（`pack.py:53`）可临时承载资产清单 |
| **3. 消费/参与度埋点** | `world.pack_manifest.id` 是埋点锚点；`ON_NATURE_CHANGE`（`nature.py:29`）已示范事件订阅模式 | 无消费/移动/渡口/骑乘事件；无埋点管道 | 在 `_buy`/`_buy_mount`/`go`/`_on_ferry_tick`/骑乘精力耗尽等点发出可订阅事件；MVP 不接管道 |
| **4. 世界实例隔离** | `World` 单进程单 World（[ADR-0009](../../../../docs/adr/0009-single-process-single-world.md)）；`pack_manifest` 是实例身份 | 已天然隔离，无缺口 | 已满足；`pack_manifest.id` 作为实例级计费/埋点主键 |

### 5.1 交通专项预留（post-MVP）

`engine/src/openmud/` 当前只有 `ferry.py`（渡口，147 行），**无 ship 模块**。若未来题材包要做航海消费（如海盗题材包），engine 需补：
- 玩家船抽象：导航坐标系（`ship.c:118-119` 的 `locx/locy`）、港口表（`harbor.h` 的 `harbors`/`islands`/`wildharbors`）、天气（`ship.c:484-505` 的 `shipweather`）。
- 船只所有权与 PVP（`ship.c:475-482` 的 `is_owner` `combat_exp` 比较）。
- 这属于 [post-mvp-backlog](../../../mvp-scope/post-mvp-backlog.md) M5 范畴，MVP 不做，但 `ferry.py` 的 `FerryCrossing`/`FerryState` 形状可作为未来 ship 抽象的参考（非复用）。

### 5.2 付费红线清单（绝不可越）

基于 [06 号票](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md)「不 pay-to-win」+ 世界空间层证据：

| 付费方向 | 判定 | 证据 |
|---|---|---|
| 付费买更高 `Mount.ability`（通过更多地形） | **红线** | `commands.py:471-478` `cost > mount.ability`；LPC `xiaohongma` value=500/ability=10 是 pay-to-win 隐患 |
| 付费解锁渡口/船只可达区域 | **红线** | 等于付费锁地图，力量优势 |
| 付费买 `do_duhe` 式独占渡河能力 | **红线** | `xiaohongma.c:130-171` 独占技能 |
| 付费买船只 PVP `is_owner` 优势 | **红线** | `ship.c:475-482` `combat_exp` 比较 |
| 付费缩短渡口等待 | 可接受（便利） | `ferry.c:90,111,138` 的 `call_out` 周期 |
| 付费买马匹续航/外观/召唤 | 可接受（便利） | `horse.h:48-56` 吃草恢复、`baima.c:14` 描述 |
| 付费买船只抗风浪/触礁保险 | 可接受（容错） | `ship.c:128-132,135-141` 触礁/翻船 |
| 付费买 fast travel（非战斗） | 可接受（便利） | LPC 无 fast travel 是过时设计 |

---

## 6. 风险提示（交红队深化）

1. **`includes` 不贡献 rooms 限制创作者资产组合**：[creator-contract-v0.md](../../../../docs/creator-contract-v0.md) 第 36-41 行规定 `includes` 只贡献 `items`/`npcs`。这意味着创作者无法把「一批房间」打包成可复用资产库供他人组合——阻碍了 Roblox 式「资产市场」的分成基础。是否放宽 `includes` 贡献 `rooms` 是 post-MVP 决策，但 engine 现状是硬限制。
2. **`hooks` 禁止 UGC 使用**：[ADR-0012](../../../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md) 禁止 UGC 包声明 `hooks`。LPC `ferry.c`/`ship.c` 式动态交通机关（`call_out` 周期、`navigate` 坐标系）无法用声明式 YAML 完整表达，UGC 创作者只能用引擎预置的 `ferry:` 段。这限制了创作者做差异化交通消费点的能力。
3. **`PackManifest.creator` 是自由字符串**：`pack.py:34` 的 `creator: str | None` 无身份校验。分成需要强身份（账号体系），这属于 [post-mvp-backlog](../../../mvp-scope/post-mvp-backlog.md) Web 平台范畴，engine 侧只留字符串字段即可，但要知道它现在不能作为分成法律依据。
4. **LPC 房间路径硬编码与 engine 键映射的迁移成本**：LPC `exits` 用 `__DIR__"sroad3"` 焊死路径；engine 用 `room_ids: dict[str, EntityId]`（`world.py:97`）解耦了键与实体。但若要把 LPC 的 6414 房间作为「官方武侠包」资产导入，路径->键的映射需要一个迁移层，这影响「官方包」的创作成本与版本管理。

---

## 附：证据索引

### LPC 一手源码
- `d/REGIONS.h:5-39` — 35 区域映射
- `inherit/room/room.c:52-155` — `make_inventory`/`reset`/门系统
- `d/village/alley1.c:4-23` — 房间定义模式（`set exits/outdoors/cost` + `setup` + `replace_program`）
- `adm/daemons/natured.c:54-77` — `update_day_phase` + `message("outdoor:vision", ..., users())` 全户外广播
- `inherit/room/ferry.c:28-157` — `do_yell`/`check_trigger`/`on_board`/`arrive`/`close_passage` 渡船周期
- `inherit/room/ship.c:49-53,73-110,112-282,475-482,513-537` — `time_out`/`do_start`/`navigate`/`is_owner`/`do_drop`
- `clone/horse/horse.h:7-41` — `condition_check` 体力衰减/昏厥
- `clone/horse/baima.c:21,28` — value=80, ability=4
- `clone/horse/xiaohongma.c:26-28,101-171` — value=500, ability=10, wildness=20000, `do_duhe`/`do_escape` 独占
- `clone/ship/harbor.h:9-31` — `harbors`/`islands`/`wildharbors` 港口表
- `feature/move.c:47-60` — `move(dest, silently)` + 装备卸下
- 各 `clone/horse/*.c` 的 `set("value")`/`set("ability")`/`set("max_jingli")` — 马匹数值梯度

### engine 模块（批判对照）
- `engine/src/openmud/pack.py:25-36,39-60,63-82` — `PackManifest`/`load_manifest`/`load_pack`
- `engine/src/openmud/world.py:97,105,266-280` — `room_ids`/`pack_manifest`/`entity_extension_data`
- `engine/src/openmud/components.py:650-653,656-668,705-718,724-737` — `Currency`/`ShopEntry`/`Mount`/`Riding`/`Terrain` + 移动精力常量
- `engine/src/openmud/commands.py:471-478,499-518,993-1007,1011-1033` — `go` 移动判定/骑乘精力/`_buy`/`_buy_mount`
- `engine/src/openmud/ferry.py:22-51,102-113` — `FerryCrossing`/`FerryState`/`_on_ferry_tick`（无 ship 模块）
- `engine/src/openmud/nature.py:29,502-535` — `ON_NATURE_CHANGE`/`_outdoor_player_ids`/`_broadcast_nature_change`
- `engine/src/openmud/scene_loader.py` — 现行创作契约 v0 实现（`includes` 只贡献 items/npcs）

### 决策文档
- [CLAUDE.md](../../../../CLAUDE.md) 架构不变量 6（商业化支撑点）
- [mvp-scope/issues/06](../../../mvp-scope/issues/06-scaling-commercialization-support-points.md) — 四支撑点原文
- [mvp-scope/issues/10](../../../mvp-scope/issues/10-mvp-scenes-selection.md) — MVP 场景收窄
- [mvp-scope/post-mvp-backlog.md](../../../mvp-scope/post-mvp-backlog.md) — M5 Web 创作者平台
- [docs/adr/0009](../../../../docs/adr/0009-single-process-single-world.md) — 单进程单 World
- [docs/adr/0012](../../../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md) — UGC 禁 hooks
- [docs/creator-contract-v0.md](../../../../docs/creator-contract-v0.md) — 创作契约冻结字段
