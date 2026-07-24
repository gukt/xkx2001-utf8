# 现代世界/关卡设计师评审：LPC 世界空间层的当代可玩性与过时风险

> 角色：现代世界/关卡设计师（03-world-space 调研团队 / 现代评审组）。
> 评审对象：LPC《侠客行》世界空间层（地图拓扑 / Nature 昼夜天气 / 交通载具）。
> 评审标尺：对标当前主流开放世界导航、fast travel、地图现代化、移动节奏、MMO 区域设计。
> 证据规则：每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 类名/行号）。禁止凭空推断。
> 边界：本评审止步于设计输入层，不输出 engine 接口契约（见总则 §1.4）。

---

## 0. 评审结论速览

LPC《侠客行》世界空间层是 **1990 年代 MUD 范式的典型样本**：纯文本方向移动、逐房间 cost 计费、call_out 驱动的昼夜广播与渡船周期、骑乘体力衰减。它在「文本沉浸感」与「空间具身感」上仍有不可替代的价值，但在「导航效率」「移动疲劳」「环境玩法深度」三个维度上与当代玩家习惯存在显著落差，且部分子系统（天气、玩家船）在 LPC 源码层面就是**半成品/空壳**——不是「过时」，而是「从未完成」。

下文逐项展开，末节给出「保留 vs 现代化」清单。

---

## 1. 导航与寻路：纯文本方向移动 vs 现代地图/auto-path

### 1.1 LPC 现状

- 房间出口是 `exits` 方向映射（`d/village/alley1.c:14-17`：`set("exits", (["east":..., "northwest":...]))`），玩家用 `go <方向>` 移动（`feature/move.c:47` `move(dest, silently)`）。
- **无任何地图/小地图/区域总览/auto-path/路径标记**：全仓库 grep `fast_travel|recall|waypoint|teleport|minimap|map_view|auto_path|auto_walk` 在 `d/`、`feature/`、`inherit/`、`cmds/` 下零命中（仅 `cmds/usr/wimpy.c` 是战斗逃跑阈值，非寻路）。
- 全世界 6414 房间 / 35 区域（`d/REGIONS.h:4-39` 的 `region_names` 映射；最大区域 beijing 625 / dali 467 / city 441 / xingxiu 388 / shaolin 368）。跨区移动完全靠玩家记忆方向链或反复 `look` 确认出口。
- 玩家获得的空间信息只有当前房间的 `short`/`long`/`exits` 列表（`inherit/room/room.c` 基类未直接渲染出口，由 `look` 命令与 `feature/move.c:99-118` 的 `brief` 模式拼装）。

### 1.2 engine 现状（批判对照）

- `engine/src/openmud/directions.py:12-23` `DIRECTION_FORMS` 提供十向内置同义词（英文全写/简写/中文），`merge_exit_match_names`（`directions.py:63-94`）允许出口别名 + 目标房名别名作为导航匹配名（Polishing A1+A2）。这是对纯方向移动的**温和改良**——玩家可用目标地名而非方向键移动，降低记忆负担。
- `engine/src/openmud/commands.py:414` `_cmd_go` 仍是单步方向移动；移动后自动 `_cmd_look`（`commands.py:534`），对应 LPC `feature/move.c:117` 的 `command("look")` 自动看房。
- **仍未有**：地图/小地图、区域总览、已发现地点列表、auto-path、fast travel。grep `fast_travel|recall|waypoint|teleport|minimap|map_view|auto_path` 在 `engine/src/openmud/` 下零命中。

### 1.3 当代对标与风险

- 当代开放世界（BotW/TotK、原神、艾尔登法环）与 MMO（WoW、FFXIV）标配：小地图 + 大地图 + 兴趣点标记 + 任务指引 + 已发现传送点。即便是文字向/复古向游戏（如 Discworld MUD 现代分支、SMAUG 衍生）也普遍提供 `map` 命令或 ASCII 局部地图。
- LPC 纯方向移动的**核心风险是迷路挫败**：6414 房间无任何空间总览，新手在扬州 441 房间内迷路是必然事件，且无任何召回/指引兜底。这不是「硬核特色」，是 1990 年代技术约束下的被动选择（终端无法渲染图形）。
- engine 的出口别名机制（`directions.py:63`）缓解了「记不住方向」但没缓解「不知道自己在哪/往哪去」——缺少**空间态势感知**这一层。

**判定**：纯文本方向移动作为底层移动原语**值得保留**（它是 MUD 空间感的基础）；但其上**必须补一层空间概览能力**（区域/已发现地点列表，最低成本是文字版，不强制图形）。auto-path 非必须，但「已发现地点 fast travel」是当代基本预期，缺失会显著拉高移动疲劳（见 §2）。

---

## 2. 移动节奏：逐房间 cost + 负重 vs fast travel/载具

### 2.1 LPC 现状

- 逐房间移动带 `cost` 字段（`d/village/alley1.c:21` `set("cost", 1)`；`clone/ship/seaboat1.c` 海船 `set("cost", 5)`），`feature/move.c:16-23` `add_encumbrance` + `over_encumbrance`（`move.c:25-29` 提示「负荷过重」）做重量校验。
- **无任何 fast travel / 传送 / 召回机制**（§1.1 已证零命中）。跨 35 区域移动纯靠官道逐房间走（`d/*/road*.c` 与 `*road*.c` 遍布各区，如 `d/city/wdroad1.c:19-22` 扬州↔太湖青石大道）。
- 唯一的「跨地形加速」是骑乘（`clone/horse/horse.h`，见 §4.1），但它只降低单步精力消耗，不跳过房间序列。
- 战斗逃跑靠 `wimpy`（`cmds/usr/wimpy.c:8-20`：设「气」低于百分比时自动逃跑），是战斗内机制，非地图层。

### 2.2 engine 现状

- `engine/src/openmud/components.py:725-728` `Terrain.cost`（缺省 1）；`engine/src/openmud/commands.py:472` `cost = 1 if terrain is None else terrain.cost`。
- 移动消耗精力：步行 `walk_drain = cost * WALK_JINGLI_PER_TERRAIN_COST`（`commands.py:481`，常量 `=2`，`components.py:737`）；骑乘 `drain = cost * MOUNT_JINGLI_PER_TERRAIN_COST`（`commands.py:513`，常量 `=1`，`components.py:733`）。精力不足拒绝移动（`commands.py:482-483`「你精力不足，走不动了。」）。
- 仍是逐房间、无 fast travel、无传送。

### 2.3 当代对标与风险

- 当代游戏明确分离**「探索性遍历」**（首次走一条路，享受发现）与**「重复性通勤」**（已走过路线的往返）。前者保留逐房间/逐地移动的沉浸感，后者用 fast travel（已发现传送点、坐骑召唤、马车/渡船快捷）跳过。LPC 把两者混为一谈，全部走逐房间，导致**移动疲劳**——跨区跑商/回门派/交任务的路途是纯时间税。
- 逐房间 `cost` + 负重校验本身是**好设计**（赋予地形与物品重量以意义），问题不在机制而在**缺少逃逸阀**：玩家一旦精力耗尽（`commands.py:482`）或负重过高（`move.c:25-29`）就只能原地等待恢复，没有任何「花钱省时间」的出口。商业化角度（见商业化专家评审）这是浪费了一个本可设为消费点的设计位。
- 6414 房间规模下，若无 fast travel，跨区往返的单次时间成本对当代玩家不可接受。LPC 时代玩家时间充裕且 MUD 是社交场所，通勤本身承载社交；单机/轻量 MVP 场景下这一前提不成立。

**判定**：逐房间 `cost` + 精力/负重机制**保留**（它是地形质感与资源管理的基础）；**必须引入 fast travel 层**（已发现地点间快速移动，最好带经济/解锁成本），否则移动疲劳会劝退当代玩家。fast travel 的解锁条件本身可成为探索动机。

---

## 3. 昼夜/天气：LPC 时段广播 vs 现代动态环境

### 3.1 LPC 现状——重大发现：天气与多数时辰事件是空壳

- 昼夜相位：`adm/etc/nature/day_phase` 声明 8 段（dawn/sunrise/morning/noon/afternoon/evening/night/midnight），length 合计 1440 分钟 = 1 游戏日。
- 时间比例：`adm/daemons/natured.c:6` `#define TIME_TICK (time()*60)`，`natured.c:46-48` 注释明确「1 minute == 1 second in RL」——即 1 真实秒 = 1 游戏分钟，**一个完整昼夜循环 = 1440 真实秒 = 24 真实分钟**。这个循环非常快。
- 相位切换广播：`natured.c:71` `message("outdoor:vision", day_phase[...]["time_msg"], users())` 向所有户外玩家推 `time_msg`；`outdoor_room_description()`（`natured.c:144-147`）供 `look` 取 `desc_msg`。户外判定由房间 `set("outdoors","xxx")`（`d/village/alley1.c:19`）。
- **关键发现 A——天气从未实现**：`natured.c:11-17` 声明了 `weather_msg` 5 档天气数组（「万里无云」…「乌云密布」），但全仓库 grep 显示 `weather_msg` **仅在此处声明，全代码库无任何引用**（`natured.c` 自身不再用，`adm/`/`feature/`/`inherit/` 下零命中）。天气系统是**声明了但从未接线的死代码**。
- **关键发现 B——时辰事件回调多数是空函数**：`day_phase` 每段声明了 `event_fun`（event_dawn/sunrise/morning/noon/afternoon/evening/night/midnight），`natured.c:72-73` 用 `call_other(this_object(), event_fun)` 调用。但 `natured.c` 中**只定义了 `event_sunrise`（`natured.c:83-97`，自动存档）与 `event_common`（`natured.c:100-142`，无环境玩家清理 + 库存检查）**。其余 6 个 event_fun（dawn/morning/noon/afternoon/evening/night/midnight）**未定义**，LPC `call_other` 对不存在函数静默 no-op。即「昼夜影响玩法」在 LPC 里基本只体现在文本广播，时辰触发的环境/NPC 行为从未落地。
- `event_common`（`natured.c:100-142`）实际做的是：清理无环境 livings（`natured.c:118` 非玩家 destruct，玩家 move 到 `/d/city/wumiao.c`，`natured.c:119`）+ 随机抽查玩家库存（`natured.c:132-141`）。这是**运维清理**伪装成时辰事件，不是环境玩法。

### 3.2 engine 现状

- `engine/src/openmud/nature.py:37-41` `Weather` 枚举**两态**（CLEAR/RAIN），比 LPC 的 5 档简化，但**真的接线了**：`nature.py:320-330` `_maybe_change_weather` 按概率翻转，`nature.py:44-56` `DayPhase` 带 `rain_desc_msg` 构成「时辰 × 天气」二维文案。
- 但 `nature.py:38` 注释明确：**「不做对玩家机制影响（视野/移动等）」**——天气仍是纯文案。
- `ON_NATURE_CHANGE` 事件（`nature.py:29`）+ `_broadcast_nature_change`（`nature.py:517-535`）已挂事件点，**为未来天气玩法预留了接线位**但尚未接任何机制。
- 默认四相（`nature.py:83-112` dawn/day/dusk/night），`game_minutes_per_tick` 默认 1（`nature.py:148`），即 1 tick ≈ 1 游戏分钟，对应 LPC 的 60:1 节奏。

### 3.3 当代对标与风险

- 当代动态环境把昼夜/天气当**玩法变量**而非装饰：BotW 雨天攀爬打滑、雷暴引雷、夜间怪物强化、寒冷区需防寒装备；原神昼夜切换 NPC 与采集物；MMO 夜间开放特定任务/副本。LPC/engine 的昼夜天气**只做文案，不做机制**，浪费了这一层最大的玩法潜力。
- 24 分钟昼夜循环对当代玩家偏快——一个会话内昼夜来回切换多次，易导致「时辰」失去仪式感（玩家无法规划「夜间去做某事」）。现代开放世界多用 1-2 小时甚至真实时钟周期。
- LPC 天气空壳这一发现对设计输入很重要：**不要把 LPC 的 5 档天气当成「待还原的遗产」**，它是从未实现的想法。engine 选 2 态并先做文案、留事件点待接机制（`nature.py:517`）是更务实的路径。

**判定**：昼夜相位广播**保留**（户外文案沉浸感是 MUD 的核心氛围）；天气**应从纯文案升级为机制变量**（至少影响视野/移动消耗/特定 NPC 出没），用 engine 已留的 `ON_NATURE_CHANGE` 事件点接线；昼夜循环周期建议放慢（1-2 小时级），让「时间」成为玩家可规划的资源而非背景噪声。LPC 的 5 档天气声明不必照搬，2-3 档带机制影响优于 5 档纯文案。

---

## 4. 交通载具：坐骑/渡船/玩家船 vs 现代载具玩法

### 4.1 坐骑（clone/horse/）

- 22 匹马（`clone/horse/`：baima/camel/donkey/feiyun 等）+ `clone/horse/horse.h`。
- 体力衰减：`horse.h:7` `condition_check()`，`horse.h:18` `jingli<=10` 马匹昏厥、骑手坠落受伤（`horse.h:21-23` `receive_wound("qi", 150)`）；`horse.h:32` `jingli<=30` 喘气快跑不动；`horse.h:37` `jingli<=max/3` 大口喘气。
- 恢复：`horse.h:48-55` 在 `resource/grass` 房间吃草回精力与食物。
- 跟随：`set_leader`（`horse.h:27` 昏厥后 `set_leader(0)` 断跟随）。
- 个体差异：`clone/horse/baima.c:31` `max_jingli=630`、`ability=4`（通行能力值，与 `Terrain.cost` 比较，见 §4.4）。

### 4.2 渡船（inherit/room/ferry.c，157 行）

- 周期翻转出口：`ferry.c:28` `do_yell("boat")` → `ferry.c:55` `check_trigger()` 设两岸互指 exit → `call_out("on_board", 15)`（`ferry.c:90`）→ `call_out("arrive", 20)`（`ferry.c:111`）→ `call_out("close_passage", 20)`（`ferry.c:138`）。**单程约 55 秒**，全程被动等待。
- 玩家无法跳过等待，只能 `yell boat` 触发后干等。

### 4.3 玩家船（inherit/room/ship.c，591 行）——过度复杂的孤岛玩法

- 网格化海图导航：`clone/ship/harbor.h` 声明大陆港口（`harbors` locx/locy，`harbor.h:9-14`）+ 海岛（`islands`，`harbor.h:17-21`）+ 荒岛（`wildharbors`，`harbor.h:26-28`）；`clone/ship/seashape.h` 声明暗礁坐标（`jiaos`，`seashape.h:5-18`）。
- 指令集：`ship.c:40-45` `start/go/stop/lookout/locate`，`navigate()`（`ship.c:112-282`）每 2 秒 tick 一次按方向移动 locx/locy。
- 随机海难：`ship.c:128` 触礁沉船；`ship.c:137` 暴风（weather==2 且远海）翻船；`ship.c:46` `time_out` 900+random(500) 秒无操作强制翻船。
- 随机事件：`ship.c:143-183` 10 档随机事件（海怪/财宝/海盗/神迹/幽灵船/火鸟/海妖歌声/海怪之眼/美人鱼/极光）——**全是纯文案 tell_room，无任何机制后果**（case 0/1/2 的 monster/treasure/corsair 注释空实现，case 3-9 只播文案）。
- 沉船惩罚：`ship.c:513` `do_drop()`——玩家 `unconcious()` + **全背包销毁**（除 `tie lian` 铁链，`ship.c:524-526`）+ 冲到随机港口（`ship.c:528`）。这是极严厉的惩罚。
- 所有权/抢船：`ship.c:475-482` `is_owner` 按 `combat_exp` 比较——高经验玩家可「占」低经验玩家的船（`ship.c:81-82`、`ship.c:293-295` 拒绝）。
- 舱房：`clone/ship/cabin1.c` 船舱可睡觉/有补给（`cabin1.c` `sleep_room` + `resource/water`）。

### 4.4 engine 现状

- 坐骑：`engine/src/openmud/components.py:705-711` `Mount`（ability/jingli_current/jingli_max/ridden_by）+ `components.py:715-716` `Riding`；`commands.py:474-477` 骑乘时 `cost > mount.ability` 拒绝通行；`commands.py:513-521` 移动扣坐骑精力，`jingli==0` 坐骑昏厥 + 骑手摔下。对应 LPC `horse.h` 的 `condition_check` 昏厥逻辑，但**未实现吃草恢复**（LPC `horse.h:48-55`）。
- 地形：`components.py:725-728` `Terrain.cost`。
- 渡口：`components.py:773-784` `Ferry` 组件 + `engine/src/openmud/ferry.py`。`ferry.py:102-113` `_on_ferry_tick` 按 `cross_interval` 周期翻转两岸 Exit（`ferry.py:123-132` `_apply_crossing_exits`）。**比 LPC 简化**：LPC 是 `yell` 触发后单向一次（`ferry.c` call_out 链），engine 是周期自动翻转（无需 `yell`，玩家到岸看 `ferry_status_line`，`ferry.py:53-71` 提示剩余时辰）。去掉了「喊船」交互，更自动化但也更无参与感。
- 玩家船：**engine 完全未实现**。grep `ship|navigate|seaboat|harbor|island` 在 `engine/src/openmud/` 下无对应模块（`ferry.py` 只做两岸渡口，不做网格海图）。这是 engine 的合理遗漏（见 §4.5 判定）。

### 4.5 当代对标与风险

- **坐骑**：现代载具/坐骑设计趋势是「探索加速 + 个性化 + 情感羁绊」（BotW 马匹好感度、原神坐骑、MMO 坐骑收集）。LPC 坐骑有体力与昏厥机制（`horse.h`）已经是不错的资源管理雏形，但缺恢复回路（吃草未在 engine 接线，`horse.h:48-55`）会导致坐骑用一次就废。**判定：坐骑体力机制保留，补恢复回路；不必照搬 22 匹马的文案差异，个体差异可压缩为少量品质档**。
- **渡船**：周期性交通门控是经典关卡节奏手段（等待=制造停留=社交/观察窗口），但 LPC 的 55 秒纯被动等待（`ferry.c` call_out 链）对单机玩家无社交可填，纯枯燥。engine 改为自动周期翻转（`ferry.py:102-113`）去掉了 `yell`，但玩家仍是被动等。**判定：渡船作为「跨水域门控」保留，但应把等待窗口变成可互动时间**（船上可触发事件/交易/对话），而非纯倒计时；或允许付费优先/包船跳过等待（消费点）。
- **玩家船（ship.c 591 行）**：这是 LPC 世界空间层**最过度复杂的子系统**，服务于「跨海去海岛/海外」这一极小众玩法路径（`harbor.h` 仅 4 大陆港 + 3 海岛 + 1 荒岛）。其网格导航 + 暗礁 + 天气 + 随机事件 + 沉船全背包销毁的组合，对当代玩家是**高学习成本 + 高惩罚 + 低回报**（10 档随机事件 `ship.c:143-183` 全是空文案，无实际收益）。591 行的复杂度与其服务面严重不匹配。**判定：玩家船网格导航系统不值得原样复刻**；MVP/新引擎如需跨海，用「渡船式」定时航线（玩家付费买票，自动航行到目标港口，途中可触发 1-2 个事件）即可覆盖 90% 体验，砍掉网格导航/暗礁/抢船/沉船销毁。若坚持玩家船，至少砍掉「沉船销毁全背包」（`ship.c:519-527`，现代设计几乎不这么做）与空壳随机事件。

---

## 5. 保留 vs 现代化清单

### 5.1 值得保留（LPC 的文本空间感核心）

| 机制 | LPC 证据 | 保留理由 |
|------|----------|----------|
| 纯文本方向移动 + `exits` 方向映射 | `d/village/alley1.c:14-17`、`feature/move.c:47` | MUD 空间具身感的基础，方向感=沉浸感；engine `commands.py:414` `_cmd_go` 已合理继承 |
| 逐房间 `cost` + 精力/负重消耗 | `d/village/alley1.c:21`、`feature/move.c:16-29`；engine `components.py:725` `Terrain`、`commands.py:472-483` | 赋予地形与物品重量以意义，是资源管理基础 |
| 户外昼夜相位广播 | `natured.c:71` `message("outdoor:vision",...)`、`natured.c:144` `outdoor_room_description`；engine `nature.py:517` `_broadcast_nature_change` | 文本氛围核心，时辰感是 MUD 独有时间质感 |
| 渡船周期门控 | `inherit/room/ferry.c:90-138` call_out 链；engine `ferry.py:102-113` `_on_ferry_tick` | 经典节奏手段，制造停留与期待 |
| 坐骑体力与昏厥 | `clone/horse/horse.h:7-41`；engine `components.py:705` `Mount`、`commands.py:513-521` | 资源管理雏形，让骑乘有成本有决策 |
| 门（开/关/锁）状态 | `inherit/room/room.c:158-275`（`create_door`/`open_door`/`close_door`/`valid_leave`）；engine `components.py:127-158` `DoorState`/`Door` | 空间门控与探索解锁的基础 |
| 自动 look 入房 | `feature/move.c:117` `command("look")`；engine `commands.py:534` | 减少操作摩擦，进入即见环境 |

### 5.2 应现代化（过时或 LPC 半成品）

| 机制 | 现状与证据 | 现代化方向 |
|------|----------|----------|
| 缺地图/小地图/区域总览 | LPC 全库零 `map`/`minimap`（§1.1）；engine 同样无 | 补文字版区域/已发现地点列表（最低成本），缓解迷路挫败 |
| 缺 fast travel | LPC 全库零 `fast_travel`/`recall`/`waypoint`（§1.1）；engine 同样无 | 引入「已发现地点」快速移动（带解锁/经济成本），消除重复通勤疲劳 |
| 天气纯文案/空壳 | LPC `natured.c:11` `weather_msg` 声明但全库零引用；engine `nature.py:38` 明确不做机制 | 天气升级为玩法变量（视野/移动/NPC），用 engine `ON_NATURE_CHANGE` 事件点（`nature.py:29`）接线 |
| 多数时辰事件未实现 | LPC `day_phase` 8 段 `event_fun`，仅 `event_sunrise`（`natured.c:83`）/`event_common`（`natured.c:100`）定义，余 6 个 no-op | 时辰应驱动可玩事件（夜间 NPC/商店/任务），而非只广播文案 |
| 昼夜循环过快 | LPC 24 真实分钟一轮（`natured.c:46-48` 1min=1s）；engine `game_minutes_per_tick=1`（`nature.py:148`）同节奏 | 放慢至 1-2 小时级，让时辰成为可规划资源 |
| 玩家船网格导航 | `inherit/room/ship.c` 591 行 + `harbor.h`/`seashape.h`；engine 未实现 | 不复刻；跨海用渡船式定时航线替代，砍网格/暗礁/沉船销毁 |
| 沉船销毁全背包 | `ship.c:519-527` `do_drop` `destruct(invofusr[m])`（除铁链） | 现代设计基本不做全背包销毁，应改为部分掉落/耐久损失 |
| 随机事件空壳 | `ship.c:143-183` 10 档事件全 `tell_room` 文案无机制 | 要么接机制后果，要么砍掉 |
| 渡船纯被动等待 | `ferry.c` call_out 链 55s 无互动；engine `ferry.py` 周期翻转同样被动 | 等待窗口可互动化（船上事件/交易）或允许付费优先 |

### 5.3 需警惕的设计陷阱

- **别把 LPC 空壳当遗产还原**：天气 5 档（`natured.c:11-17`）与时辰 event_fun（`day_phase`）在 LPC 里从未接线，新引擎不应追求「还原 5 档天气」，而应从「天气能驱动什么玩法」倒推档位数。engine 选 2 态先做文案留事件点（`nature.py`）是正确方向。
- **别把「无 fast travel」当硬核特色**：LPC 无 fast travel 是技术/时代限制，不是设计选择。当代单机/轻量 MVP 没有社交填充通勤，缺 fast travel 直接导致弃游。
- **玩家船复杂度陷阱**：591 行 `ship.c` 是「因为能做所以做了」的典型，其复杂度与服务面（少数跨海玩家）严重不匹配。新引擎应警惕「把一个边缘玩法做成完整子系统」的倾向。
- **昼夜循环速度与玩法脱节**：24 分钟循环若不接机制，纯文案广播会变成噪声（频繁刷屏干扰）；若接机制，太快又让玩家无法规划。速度与机制深度需协同设计，不能分开决策。

---

## 6. 证据索引

### LPC 源码（一手真相源）
- `inherit/room/room.c`：基础房间（门 `create_door:227`/`look_door:158`/`check_door:218`/`valid_leave:267`，`reset:76`，`make_inventory:52`，`setup:277`）
- `feature/move.c`：移动原语（`move:47`，`add_encumbrance:16`，`over_encumbrance:25`，自动 look `:117`）
- `adm/daemons/natured.c`：Nature（`weather_msg:11` 声明未用，`init_day_phase:28`，`update_day_phase:54`，广播 `:71`，`event_sunrise:83`，`event_common:100`，`outdoor_room_description:144`）
- `adm/etc/nature/day_phase`：8 段相位数据（length/time_msg/desc_msg/event_fun），合计 1440 分钟
- `d/REGIONS.h`：35 区域映射（`region_names:4-39`）
- `d/village/alley1.c`：房间定义模式（exits/outdoors/cost/setup/replace_program）
- `d/city/wdroad1.c`：跨区官道（扬州↔太湖，`exits:19-22`）
- `inherit/room/ferry.c`：渡船（`do_yell:28`/`check_trigger:55`/`on_board:93`/`arrive:114`/`close_passage:141`）
- `inherit/room/ship.c`：玩家船 591 行（`do_start:73`/`navigate:112`/`do_go:284`/`do_lookout:341`/`do_locate:423`/`shipweather:484`/`do_drop:513`/`do_ready:539`/`is_owner:475`，随机事件 `:143-183`）
- `clone/ship/harbor.h`：港口/海岛/荒岛坐标（`harbors:9`/`islands:17`/`wildharbors:26`）
- `clone/ship/seashape.h`：暗礁坐标（`jiaos:5`）
- `clone/ship/cabin1.c`：船舱（sleep_room + resource/water）
- `clone/ship/seaboat1.c`：海船定义（`cost:5`）
- `clone/horse/horse.h`：坐骑体力（`condition_check:7`，昏厥 `:18-30`，喘气 `:32-40`，吃草 `:48-55`）
- `clone/horse/baima.c`：白马个体（`max_jingli:630`，`ability:4`）
- `cmds/usr/wimpy.c`：战斗逃跑阈值（非地图层）
- `include/room.h`：门状态常量（`DOOR_CLOSED:5`/`DOOR_LOCKED:6`）

### engine 模块（批判对照对象）
- `engine/src/openmud/directions.py`：十向同义词（`DIRECTION_FORMS:12`，`merge_exit_match_names:63`，`exit_display_label:97`）
- `engine/src/openmud/commands.py:414` `_cmd_go`（移动 + 门/地形/精力/骑乘校验 + on_before/enter/leave_room）
- `engine/src/openmud/components.py`：`Mount:705`/`Riding:715`/`Terrain:725`/`Ferry:773`/`Door:141`/`DoorState:127`/`LocalNature:584`
- `engine/src/openmud/nature.py`：`Weather:37`（2 态）/`DayPhase:44`/`NatureState:136`/`ON_NATURE_CHANGE:29`/`_broadcast_nature_change:517`/`DEFAULT_PHASES:83`/`align_from_clock:257`
- `engine/src/openmud/ferry.py`：`FerryCrossing:22`/`FerryState:36`/`attach_ferries:42`/`_on_ferry_tick:102`/`_apply_crossing_exits:123`/`ferry_status_line:53`
- `engine/src/openmud/transfer.py`：物品转移原语（`transfer:97`，重量校验 `_check_weight:281`）

### 规模与比例数据
- 房间总数：6414（`find d -name *.c`），区域数：35（`d/REGIONS.h`）
- 最大区域：beijing 625 / dali 467 / city 441 / xingxiu 388 / shaolin 368
- 昼夜循环：1440 游戏分钟 = 1440 真实秒 = 24 真实分钟（`natured.c:46-48`）
- 坐骑数：22（`clone/horse/`）
- 玩家船复杂度：`ship.c` 591 行 + `harbor.h`/`seashape.h` 网格数据
