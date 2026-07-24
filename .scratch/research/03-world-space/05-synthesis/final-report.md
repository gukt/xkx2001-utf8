# 世界空间层调研最终报告

> 主题：03-world-space（地图拓扑基底 + Nature 环境叠加层 + 交通跨区移动层）
> 阶段：Phase 3 评审委员会汇总（5 人：玩法切片策划 + 引擎架构师 A + UGC 游戏专家 + 现代世界/关卡设计师 + 商业化与增长专家）
> 基线：LPC 一手源码为唯一真相源；engine 模块仅作批判对照对象；止步设计输入层，不输出可直接落地的 engine 代码或接口契约。
> 输入：Phase 1 初稿 14 份 + Phase 2 红队报告 5 份 + 06-engine-critique 1 份。所有文件均已 Read，无缺失。

---

## 0. 执行摘要

本次调研以《侠客行》LPC 源码为唯一真相源，系统梳理了世界空间层的三层脉络--地图拓扑（34 区域 / 3691 房间 / exits mapping 统一底座）、Nature 环境叠加（8 时段循环 + 户外广播 + 天气死代码）、交通跨区移动（坐骑 / 渡船 / 玩家船三态）--并批判性对照了 engine 现有 9 个模块。

调研最重要的五项发现：第一，LPC 的全局天气系统（`natured.c:11` `weather_msg` 5 档）是**从未接线的死代码**，8 个 `event_fun` 回调中 7 个是空操作，新引擎不应把这两者当作「待还原的遗产」。第二，engine 当前是**单玩家 stdin REPL、无网络层**，所有「1000 在线」性能分析都是假想场景；真正的 MVP 首要性能风险是 `save_world` 每 10 条命令全量 fsync（`tick.py:39` `DEFAULT_SAVE_INTERVAL=10`），这在当前单玩家下就会导致每 10 步卡 1-2 秒。第三，engine 的 tick 是**命令驱动而非墙钟驱动**，玩家 idle 时昼夜冻结、渡船冻结、NPC 不补刷--这与 LPC「世界独立于玩家演化」是根本不同的世界感。第四，engine 对渡船的简化（去 yell 触发、去船房实体）是**负面偏差**，导致玩家在渡口完全丧失代理权（过岸后可被计时器甩下、无召回手段）。第五，LPC 坐骑实际是**三档**（普通 20 匹 + bailong + xiaohongma 自实现特种技能），engine 的单一 `Mount` 组件模板未识别这一差异化，且 `RoomResources` 草地恢复机制未接线，导致坐骑体力只减不回、沦为一次性消耗品。

评审委员会对红队质疑的核心裁决：fast travel 不作为引擎必须项（采纳 modern-challenges），但「导航态势感知」（区域归属 + 主干道渐进提示 + 地标距离查询）升为 P0 引擎必须项（genmap.c 已证明 BFS 可行）；昼夜循环速度与天气机制化均驳回「必须现代化」，降级为题材包自决 / post-MVP；玩家船 MVP 不做但引擎保留载具抽象；商业化分成模型在当前 engine 形态下**根本不成立**（`includes` 不支持 rooms + `creator` 是自由字符串 + 透传不算契约三层叠加），不是「MVP 不实现但留位置」而是架构层阻断。

---

## 1. 范围与方法

### 1.1 调研范围

三层统一调研，强调三者交互：

- **地图（拓扑基底）**：`d/` 下 41 个子目录、34 个区域键（`d/REGIONS.h`）、3691 个 `inherit ROOM` 房间。基础房间 `inherit/room/room.c`（281 行），玩家移动命令 `cmds/std/go.c`（289 行），对象搬迁原语 `feature/move.c`（154 行）。
- **Nature（环境叠加层）**：`adm/daemons/natured.c`（193 行）驱动 8 时段循环（`adm/etc/nature/day_phase`），`feature/message.c` 的 `outdoor:vision` 户外广播通道。
- **交通（跨区移动层）**：坐骑 `clone/horse/`（21 个 .c，含 20 匹具名马 + 1 测试残留）、渡口 `inherit/room/ferry.c`（157 行）、海船 `inherit/room/ship.c`（591 行）、官道 `d/*/road*.c`（164 个）。

### 1.2 不纳入范围

- 不做 LPC 行为等价验证（ADR-0001）。
- 不把 engine 侧现有实现当作正确形态反向脑补。
- 不输出可直接落地的 engine 代码或接口契约。
- 不纳入具体区域内容设计（房间文案 / 迷宫布局的文学性）。

### 1.3 调研方法

三阶段多 Agent 并行 Workflow：Phase 1（11 席并行初稿）-> Phase 2（5 路红队对抗，每条质疑须引用被质疑文件与段落）-> Phase 3（评审委员会汇总）。资料来源优先级：LPC 一手源码 > engine 模块（仅批判对照）> 旧文档（必要时二手参考）。

### 1.4 事实校正汇总（相对 Phase 1 初稿的修正）

红队横向对比验证（`04-redteam-review/cross-check-report.md`）复现了多条事实错误，评审委员会确认以下修正：

| 初稿位置 | 初稿值 | 正确值 | 裁决 |
|---------|-------|-------|------|
| `mechanisms.md §1.1` | region_names 38 键 | **34 键** | 推翻（grep 复现） |
| `source-inventory.md §0.1` | 43 个子目录 | **41 个子目录** | 推翻（ls / find 复现） |
| `source-inventory.md §1.3` | 22 个 .c 马匹 | **21 个 .c（20 匹具名马 + 1 测试残留）** | 推翻 |
| `mechanisms.md §1.3` | default_dirs 22 键 | **23 键** | 推翻 |
| `source-inventory.md §1.1` | 户外 1842 / inherit ROOM 3684 | **1848 / 3691** | 轻微推翻（grep 选项差异） |
| `engine-comparison.md N9` | in/out 方向遗漏 | **实际缺 13 方向**（8 个 *up/*down 变体 + out/enter/in/left/right） | 待澄清 -> 修正 |
| CLAUDE.md「35 区域」 | 35 | **34 键**（约数偏差 1） | 建议统一以 34 为准 |

**新增覆盖盲点**：LPC 坐骑实际分三档--普通 20 匹（`include horse.h`，共享 `condition_check`）+ bailong（自实现，6 处渡河 + 拒驯服）+ xiaohongma（自实现，8 处渡河 + 哨子逃生 + 拒驯服）。后两匹**不 include horse.h**，abstraction-options §4.1 与 engine-comparison §11 均未识别这一结构差异。

---

## 2. 现状总览：地图 / Nature / 交通 三层脉络

### 2.1 地图（拓扑基底）

**exits mapping 是世界空间层的统一数据底座**（红队裁决 1.1 确认，7 类实例覆盖）。房间通过 `set("exits", ([ <方向>: <目标房间路径>, ... ]))` 声明出口，跨区用绝对路径 `/d/<region>/<room>`，同区用 `__DIR__"<room>"` 相对路径。无独立「区域边界」抽象--区域是 `d/REGIONS.h` 的纯命名映射（34 键），不参与拓扑，拓扑上是全连通图。

**门（状态机）**：`inherit/room/room.c:227` `create_door` 按方向索引，`status` 位掩码（`DOOR_CLOSED=1`/`DOOR_LOCKED=2`/`DOOR_SMASHED=4`，但 room.c 只对 CLOSED 做开关，LOCKED/SMASHED 是预留位）。门的关键设计是**双向同步**--`open_door(dir, from_other_side)` 调对侧房间 `open_door(other_side_dir, 1)`，`from_other_side` 标志避免无限递归。门无锁/钥匙机制（预留位未实现）。

**移动调用链**（`cmds/std/go.c:main`）：校验（负重 / busy / 战斗 / jingli 门槛）-> 取 exit -> 门校验（`valid_leave`）-> 加载目标 -> 骑乘校验 -> 消耗 jingli（步行 `cost*2`、骑乘马 `cost*2` + 骑手 1/5 概率 -2）-> `me->move(obj)` -> 触发跟随 `follow_me`。`room.cost` 是 jingli 消耗基数，每步消耗 `cost*2`。

### 2.2 Nature（环境叠加层）

**昼夜 8 时段循环**（`adm/etc/nature/day_phase`）：dawn(240) / sunrise(120) / morning(180) / noon(180) / afternoon(180) / evening(180) / night(120) / midnight(240)，总长 1440 游戏分钟 = 1 游戏日。LPC 时间比例 `TIME_TICK = time()*60`，1 真实秒 = 1 游戏分钟，**一个完整昼夜循环 = 1440 真实秒 = 24 真实分钟**。

**关键发现--天气系统是死代码**（红队裁决 4.4 确认）：`natured.c:11` 声明 `weather_msg` 5 档数组，但全仓 grep 仅此一处定义，无任何读取 / 广播 / 切换。`message.c:31-34` 留了 `weather:` 消息子类过滤分支，但全仓无任何房间 `set("weather")`、也无任何代码 `message("weather:...")` 广播。Nature 实际只驱动「昼夜时段」，不驱动「天气变化」。

**关键发现--event_fun 多数是空操作**（红队裁决 4.5 确认）：8 个 event_fun 回调中，仅 `event_sunrise`（`natured.c:83`，自动存档）与 `event_common`（`natured.c:100`，清理无环境对象 + 库存检查）有定义，其余 6 个（dawn / morning / noon / afternoon / evening / night / midnight）全仓无定义，`call_other` 调用不存在的函数是 no-op。「昼夜影响玩法」在 LPC 里基本只体现在文本广播与 day_shop 夜间关门。

**户外广播通道**（`natured.c:71`）：`message("outdoor:vision", time_msg, users())` 广播给**全体在线玩家**，真正的「只户外房间收到」过滤发生在每个玩家对象的 `receive_message()` 里（`feature/message.c:25-27` 检查 `environment()->query("outdoors")`）。`outdoors` 的值是字符串标签（如 `"village"`/`"shaolin"`），但引擎层只消费其布尔真假，标签是区域 / 音效元数据，不被通用机制消费。

### 2.3 交通（跨区移动层）

**坐骑**（`clone/horse/`）：骑乘关系是双向引用（玩家 `rided`、马 `rider`）+ `set_leader` 跟随。体力衰减 `condition_check()` 三档（`<=max/3` 大口喘气、`<=30` 喘气快跑不动、`<=10` 坠骑 + `receive_wound("qi",150)` + 马昏厥）。草地 `resource/grass` 吃草恢复一半缺口。LPC 坐骑实际三档（见 §1.4 事实校正）。

**渡船**（`inherit/room/ferry.c`，157 行）：玩家 `yell boat` 触发 `check_trigger()` -> 15s 登船窗口 -> `on_board()` 撤出口 -> 20s `arrive()` 到对岸 -> 20s `close_passage()` 复位。总周期 ~55s，靠 `call_out` 串行驱动。渡船是一个独立 room（玩家 `enter` 进船、`out` 出船），两岸靠动态增删 `exits/enter`/`exits/out` 实现。

**海船**（`inherit/room/ship.c`，591 行）：最复杂的交通子系统。网格导航（`locx/locy` 坐标）+ 暗礁（`seashape.h` jiaos 10 处）+ 局部天气（`shipweather` 三态 0/1/2）+ 随机事件（`!random(40)` 触发 10 种，其中 case 0-2 海怪/财宝/海盗未实现、case 3-9 共 7 档已实现为 `tell_room` 氛围文案）+ 沉船 `do_drop`（昏迷 + 全背包销毁仅留铁链 + 随机冲港）+ 所有权 `is_owner`（`combat_exp` 比较，PvP 抢船）+ 超时 `time_out`（900+random(500) 秒无操作翻船）。

**三者共性**：ferry 与 ship 共享「载具 room + 周期调度 + 动态 exit 开关」骨架；horse 不改拓扑，改移动语义（骑乘关系 + 跟随），应单列（红队裁决 3.2 推翻 abstraction §4.1 的「三态统一」伪通用表述，建议拆为「载具类（ferry/ship）」+「骑乘类（horse）」两张表）。

---

## 3. 关键发现

### 3.1 LPC 半成品警示

- **weather_msg 5 档天气是死代码**：声明但从未接线，新引擎若做天气需从零设计，不应照搬「5 档」当作已验证机制。
- **event_fun 7/8 空操作**：时段切换除 sunrise 存档 + event_common 清理外，无其他游戏效果触发。
- **ship 随机事件 case 0-2 未实现**：海怪/财宝/海盗仅注释占位；case 3-9 共 7 档已实现为氛围文案（非「全是空文案」）。
- **门无锁/钥匙机制**：`DOOR_LOCKED`/`DOOR_SMASHED` 是预留位，room.c 只对 `DOOR_CLOSED` 做开关。

### 3.2 engine 架构性差异（非简单遗漏）

- **tick 命令驱动 vs 墙钟驱动**（性能红队 §5）：engine 的 `ON_TICK` 只在每条命令处理后分发（`cli.py:53`），玩家 idle 时昼夜不推进、渡船不翻转、NPC 不补刷。LPC 的 `call_out` 是墙钟驱动，世界独立于玩家演化。这是「世界只在玩家行动时才演化」vs「世界独立演化」的根本差异，不只影响玩家船。
- **engine 是单玩家 stdin REPL**（性能红队 §1）：无 `socket`/`asyncio`/`threading`，`world.primary_player_id` 单一主玩家。所有「1000 在线」分析是假想场景，真正的 MVP 风险被掩盖。
- **save_world 每 10 命令全量 fsync**（性能红队 §3）：`DEFAULT_SAVE_INTERVAL=10` + 每实体一文件 + `os.fsync` + 全量存所有实体。MVP ~1000-3000 实体时每 10 命令卡 1-2 秒，这是当前 MVP 首要性能风险。

### 3.3 engine 负面偏差（体验阻塞级）

- **渡船去 yell 化 + 去船房**（engine-comparison N4）：engine `ferry.py` 是纯定时翻转两岸 Exit，无 yell 触发、无船房实体、无登船/渡河/下船叙事。玩家过岸后若 `ticks_until_flip` 到期，对岸 Exit 被删，玩家**搁浅无自救**（无 yell 召回）。MVP 路径含 `ferry_west`/`ferry_east`，这是体验阻塞点。
- **坐骑体力无恢复回路**（engine-comparison N6）：`RoomResources` 明注「grass 未打通」，MVP 场景 0 间 grass 房。马匹 jingli 只减不回，沦为一次性消耗品。
- **门双侧同步缺失**（abstraction-options §1.2）：engine 的 `Door` 组件按方向各自独立，无 LPC `check_door`/`other_side_dir` 协商机制，两个房间门状态会漂移不一致。
- **区域概念缺失**（engine-comparison N2）：engine 全仓无 region/Region 概念，`outdoors` 降级为 bool，丢失 LPC 的区域标签字符串。影响 fast travel / 地图概览 / 区域级埋点的前置依赖。
- **跟随/队伍缺失**（engine-comparison N5）：engine 无 `set_leader`/`follow_me` 等价物。

### 3.4 LPC 的设计意图证据（非技术限制）

- **genmap.c + mapdb.c 证明寻路工具存在但刻意不暴露给玩家**（modern-challenges 质疑 1）：`clone/obj/genmap.c`（BFS 地图生成器，作者 chu@xkx，1998-05-09，`MAX_NODE=5` 限流防崩）+ `clone/obj/mapdb.c`（`query_room_exits`/`query_map` 查询接口）确实存在，消费者是 6 个 NPC/任务文件（`d/city/npc/ftb_zhu.c`、`d/beijing/gulou2.c`、`d/wudang/sheshenya.c`、`d/qilian/obj/jinhe.c`、`d/wizard/center.c`、`d/beijing/zhonglou2.c`）。**没有任何玩家命令暴露这套地图**。这是「有工具却选择不暴露」的设计选择，不是「技术做不出」。现代 engine 无 LPC driver 崩溃风险，BFS 距离计算在加载期一次性预算完全可行。

---

## 4. 三层 User Stories 汇总

### 4.1 玩家故事（10 条，`02-user-stories/player-stories.md`）

| # | 切片 | 核心体验 |
|---|------|---------|
| US-1 | 城内探索与门禁 | 关门出口不可见；`open` 后双侧同步；`go <关门方向>` 被拦 |
| US-2 | 跨区骑乘长途旅行 | 马替玩家扛 jingli 消耗；三档预警；坠骑受伤；官道沿途草地补给 |
| US-3 | 骑马撞开挡路者 | `exit_blockers` 战力/敏捷检定；骑乘冲撞 vs 步行突破 |
| US-4 | 渡口喊船过江 | `yell boat` 触发；15s 上船窗口；55s 周期；错过被留岸 |
| US-5 | 昼夜变化与夜间商店 | 户外同时收广播；look 显示时段；night/midnight 商店关门；sunrise 自动存档 |
| US-6 | 驾驶海船出海 | `start`/`go`/`lookout`/`locate` 导航；网格推进；瞭望方位 / 定位距离（有误差） |
| US-7 | 航海遇险 | 触礁/暴风雨翻船；全背包销毁（仅留铁链）；超时翻船兜底 |
| US-8 | 航海随机事件 | 10 种事件；7 档已实现氛围文案；3 档（海怪/财宝/海盗）未实现 |
| US-9 | 荒岛守船 | `wildharbors` 无法喊船；留人守船触发 `do_ready` 100s 延迟 |
| US-10 | 船只所有权 PvP | `is_owner` 基于 `combat_exp`；低战力者无法 `start`/`go`/`stop` |

### 4.2 系统/NPC 自动触发故事（20 条，`02-user-stories/system-stories.md`）

覆盖 7 类自动驱动源：call_out 定时器（时段循环/渡船周期/船只导航/港口调度）、NPC 心跳 chat 调度（马匹体力/随机行为）、event_fun 回调（存盘/清理/库存检查）、进入触发 init（吃草）、移动后处理（跟随）、被动状态查询（day_shop 夜间关门）、driver reset 调度（房间补刷）。共性风险：call_out 串无统一调度框架易漏清；NPC 心跳是概率触发非确定性周期；event_fun 多数空操作；天气自动变化完全缺失。

### 4.3 巫师/运营故事（`02-user-stories/operator-stories.md`）

覆盖 A 房间拓扑搭建（A1-A4 摆房间/连区域/检测孤岛/批量校验）、B 门与通路（B1-B3 单侧声明门/隐藏通道/NPC 拦路）、C 交通（C1-C4 渡口配对/卖坐骑/官道难度/跨海航行缺口）、D Nature 配置（D1-D3 自定义时段/局部贴纸/户外广播校验）、E 维护运营（E1-E5 透传排查/包升级/存档隔离/非武侠验证/图拓扑可视化缺口）、F 规模演进（F1-F2 拆分大场景文件缺口/坐骑变体复用缺口）。

**关键缺口**：孤岛房间检测（engine 无图遍历）、单文件 rooms 段天花板（`includes` 不支持 rooms）、玩家船创作面完全缺失、图拓扑可视化（post-MVP）。

---

## 5. 设计建议

> 止步设计输入层，不输出可直接落地的 engine 代码或接口契约。

### 5.1 engine core 必收 / 可下沉清单

| 机制层 | 推荐方向 | core 必收 | 下沉题材包 |
|-------|---------|----------|-----------|
| 房间/出口/门 | §1 | Exit/Exits/Door + **双向门同步（应补）** + HiddenExit 机制 | 门钥匙匹配规则、揭示触发条件 |
| 移动/消耗/负重 | §2 方向 B | traverse_check 闸口 + Terrain.cost 数据 + drain 契约 | 资源池类型（jingli/燃料）、分级喘息文案、吃草回精力 |
| Nature 横切层 | §3 方向 A | 相位推进 + ON_NATURE_CHANGE + 户外广播默认实现 + LocalNature 合成 | 相位表文案、时段副作用（存档/刷怪）、天气档位扩展 |
| 交通三态 | §4 方向 B | 载具实体 + 周期调度 + 动态 exit 绑定；Mount/Riding 单列 | 状态转移图、坐标网格定义、沉船事件文案 |
| 跨区/边界 | §5 方向 A | 无新增（扁平 room_ids + 加载期 exit 校验） | region 显示分组、区域切换播报（用 on_enter_room） |

**评审委员会补充裁决**：

1. **双向门同步是 core 必须补的遗漏**（拓扑一致性是不变量，不应让创作者在两侧各写一遍）。采纳 abstraction-options §1.3 判定。
2. **载具实体抽象是否在 MVP 阶段定形**：当前只有 ferry 1 个实例，ship 未实现。若抽象先行于实例，存在过度设计风险；若等 ship 落地再定形，ferry 与 ship 的抽象可能在 ship 实现时被推翻。**裁决：MVP 阶段 ferry 用现有简化模型即可，载具抽象留待 ship 落地时再定形**（采纳 cross-check 裁决 3.1）。
3. **特种坐骑命令扩展点**（N13 新增）：bailong/xiaohongma 的 `do_duhe`/`do_escape` 是武侠题材特化，MVP 可不做但 engine 是否留位置？**裁决：MVP 不做，post-MVP 评估。当前 engine `commands.py` 无此扩展点，UGC 创作者无法声明「这匹马能渡河」**（采纳 cross-check 裁决 3.3）。
4. **移动消耗资源池题材化**：官方武侠题材包用 jingli，科幻题材用 fuel--core 的 drain 契约形状需后续接口任务定。**关键约束：移动消耗不应复用战斗资源池**（见 §5.3 现代化方向）。

### 5.2 UGC 创作面最小表面

**创作面 = 声明式 YAML（房间/exits/门/objects/ferry/mount/nature/local_nature）+ engine core 锁住的调度/广播/校验/状态机**。engine 现状已覆盖约 80% 的声明面，缺口集中在：

- **区域归属**（`outdoors` 降级为 bool）：应恢复字符串标签语义或新增 `region` 字段。这对 Nature 广播作用域、导航态势感知、创作者经济（按区域统计参与度）都是前置依赖。
- **门双侧同步**：创作者不应在两侧各写一遍门（LPC 的 `check_door`/`other_side_dir` 证明这是 engine 级协调）。
- **拓扑护栏校验**：孤岛房间 / 单向出口 / 门两侧一致性 / Nature 相位名归属 / LocalNature.phase 加载期校验 / 渡口 direction 冲突 / 坐骑 ability vs Terrain.cost 失衡。护栏是 warning 不是 error（孤岛/单向可能是设计意图），只有「门双侧不对称」「exit 指向不存在目标」是 error。
- **天气文案数据化**：`_WEATHER_*_MSG` 硬编码应改为题材包可声明。
- **玩家船创作面**：M3/UGC 阶段不暴露，渡口已覆盖「过河」基础切片。
- **坐骑驯服玩法 / 草地回精 / set_leader 跟随**：post-MVP 再评估。

**应锁在 engine core 不让创作者碰的**：广播通道、时钟推进 / call_out 调度、event_fun 钩子、渡船 trigger 时序、船航海调度、坐骑体力衰减阈值 / 坠落受伤、移动精力扣减系数、拓扑一致性校验、门的双向同步、NPC 补刷 / reset 调度、天气状态机、valid_leave 门检查。

### 5.3 现代化方向（评审委员会裁决）

**现代化累积影响评估**（modern-challenges 质疑 7 要求）：每条现代化建议对「未知感 / 距离感 / 氛围 / 节奏 / 探索 / 仪式」六个沉浸维度的削弱需显式评估。确立判据：一条现代化建议若同时满足「削弱某个沉浸维度」+「该削弱无法通过题材包配置关闭」+「MVP 范围内无明确需求驱动」三条，则降级 post-MVP。

| 现代化建议 | 裁决 | 理由 |
|-----------|------|------|
| 补地图概览（文字版区域/已发现地点列表） | **采纳（P0 引擎必须）** | genmap.c 已证明 BFS 可行；区域归属数据已存在；不剧透结构（列表 ≠ 传送） |
| 补 fast travel（已发现地点传送） | **驳回「必须」，改为题材包级别设计选择** | 坐骑+渡船+官道驿站已是题材风味 fast travel；再叠传送层让坐骑/渡船冗余；MVP 36 房间无需求 |
| 导航态势感知（区域归属 + 主干道渐进提示 + 地标距离查询） | **采纳（P0 引擎必须）** | genmap.c 证明可行；不消解探索（给距离感非自动寻路）；为题材包放大预留 |
| 天气升级为机制变量 | **驳回「应」，降级 post-MVP** | LPC 天气是死代码，无义务还原；engine 2 态 + rain_desc_msg 已超越；机制化需导航保护就位后才能做（否则叠加迷路风险） |
| 昼夜放慢到 1-2 小时 | **驳回，题材包自决** | 放慢破坏 day_shop 门控（10+ 商店依赖快循环）；engine 已支持 game_minutes_per_tick YAML 配置；不在引擎层强制 |
| 玩家船网格导航复刻 | **MVP 不做，引擎保留载具抽象** | CLAUDE.md 场景清单列「渡口/渡船」非「船只航海」；abstraction-options §4 方向 B 留位；砍掉「沉船销毁全背包」（改为分级） |
| 沉船销毁全背包 | **改为分级（轻损/重损/全损），全损只在玩家明显冒险时触发** | 采纳 player-psychology 底线 4；全损保留为可选冒险行为（如无视暴风警告仍出海） |
| 渡船等待可互动化 / 付费跳过 | **驳回作为 MVP 建议；补回 yell + 船房实体（P0）** | engine ferry 丢船房+yell 是负面偏差（N4）；55s 等待是节奏 feature；付费跳过在基础等待被改造后才允许（post-MVP） |
| 坐骑体力可视化 + 恢复回路 | **采纳（P0 恢复回路 + P1 可视化）** | engine 无恢复回路，马匹变一次性消耗品；先接通 RoomResources 草地恢复，再做可视化 |
| 移动疲劳软着陆 | **采纳（P0），须连同 jingli 与战斗资源池关系一起设计** | jingli 是跨系统共享池（战斗/练功/陷阱/乞讨），分级提示只延缓不解决根因 |
| exit_blockers 前置提示 | **采纳（P1）** | 官道不透明硬阻断；声明式 `warn_message` 即可解决 |

---

## 6. engine 对照结论（引用 06-engine-critique 要点）

### 6.1 正面偏差（engine 做得更好的，P1-P10）

P1 房间数据驱动（YAML 非 .c 代码）/ P2 声明式门 + 锁/钥匙 / P3 物品堆叠合并/拆分 + 防嵌套循环 / P4 未识别字段透传（前向兼容）/ P5 Nature 时辰×天气二维文案 / P6 动态天气翻转 / P7 方向别名 N1 归一 + 中英文混解 / P8 房间钩子窄 ctx / P9 渡口幂等 attach + 纯内存态 / P10 房间景物 `名(id)` 扫描。

**P6 加注**（红队裁决 4.3）：engine 天气比 LPC 死代码强（至少会翻转 + 影响 long_desc 文案），但仍是纯文案层，未接机制（与 LPC 一样不接），是「less dead」而非「alive」。

### 6.2 负面遗漏（engine 缺失的，N1-N14）

| # | 遗漏项 | 严重度 | 裁决 |
|---|-------|-------|------|
| N1 | 玩家船系统（591 行） | 低（MVP 不做） | post-MVP 保留载具抽象 |
| N2 | 区域概念（34 区域 + REGIONS.h） | **高（P0）** | 影响导航/埋点/广播作用域，应补 |
| N3 | event_fun 钩子 | 低 | engine ON_NATURE_CHANGE 已解耦，时段副作用下沉事件点是正确方向 |
| N4 | 渡船玩家交互（yell + 船房） | **高（P0，MVP 阻塞）** | 应补回船房实体与 yell 触发 |
| N5 | 跟随/队伍（set_leader） | 中 | post-MVP 评估 |
| N6 | 马匹吃草恢复精力 | **高（P0）** | RoomResources grass 未接，马匹变一次性消耗品 |
| N7 | 坠骑受伤（150 qi） | 中 | engine 坠骑无伤害仅文案；post-MVP 评估分级 |
| N8 | 马匹驯服/训练 | 低 | post-MVP 评估 |
| N9 | 方向键缺失 | 中 | 实际缺 13 方向（8 *up/*down + out/enter/in/left/right），渡船/船只必需 enter/out |
| N10 | 房间级负重传播 | 低 | engine 用 container_total_weight 按需求和是合理简化 |
| N11 | 运行时动态建门 | 低 | engine 门仅加载期从 YAML 建，无运行时 API；post-MVP 评估 |
| N12 | item_desc 动态 callable | 低 | engine RoomDetails 仅静态 text；门状态展示走 commands 层 |
| N13 | 特种坐骑命令扩展点 | 中（新增） | bailong/xiaohongma do_duhe/do_escape；MVP 不做 post-MVP 评估 |
| N14 | 坐骑三档差异化 | 中（新增） | engine 把所有马匹视为同构，未识别 2 匹特种马结构差异 |

### 6.3 性能风险重排（采纳 performance-risks）

PR 应明确分两层评估：①当前单玩家 MVP 的真实性能风险（可验证）；②未来加网络层后的可扩展性风险（需 ADR）。

| 优先级 | 风险 | 影响场景 | 根因 |
|-------|------|---------|------|
| **P0** | save_world 每 10 命令全量 fsync | 当前单玩家 MVP | `DEFAULT_SAVE_INTERVAL=10` + 每实体 fsync + 全量存 |
| **P0** | tick 命令驱动导致 idle 时世界冻结 | 当前单玩家 MVP | `cli.py:53` 每命令 1 tick，无墙钟 |
| P1 | 全量加载 -> entity 多 -> 存档乘数效应 | 当前 MVP + UGC 扩展 | scene_loader 全量建图 × save_world 全量存 |
| P1 | `entities_with` 每次构造 set | 当前（可忽略）-> 未来扩展 | `world.py:214` `set(dict.keys())` |
| P2 | Nature 广播 `_outdoor_player_ids` 全扫 | 未来 1000 在线 | `nature.py:509` 无缓存户外玩家集合 |
| P2 | ON_TICK 6 订阅者扇出 | 当前（可忽略）-> 未来扩展 | `events.py:70` 同步串行 |
| P3 | 玩家船 navigate 性能 | 未来（engine 无 ship） | LPC call_out 模型不可复刻 |

---

## 7. 红队质疑裁决表

### 7.1 cross-check-report（横向对比验证，19 条裁决）

| # | 质疑条目 | 裁决 | 理由 |
|---|---------|------|------|
| 1.1 | exits mapping 作为统一拓扑底座 | **accept** | 7 类实例均验证 |
| 1.2 | abstraction §4.1 horse 三态表只引 baima 一例 | **accept（推翻初稿）** | bailong/xiaohongma 不 include horse.h 未被识别；坐骑应分三档 |
| 1.3 | mechanisms §1.1「region_names 38 键」 | **accept（推翻）** | 实际 34 键 |
| 1.4 | source-inventory §0.1「43 子目录」 | **accept（推翻）** | 实际 41 子目录 |
| 1.5 | source-inventory §1.3「22 个 .c 马匹」 | **accept（推翻）** | 实际 21 个 .c |
| 1.6 | mechanisms §1.3「default_dirs 22 键」 | **accept（推翻）** | 实际 23 键 |
| 1.7 | engine-comparison N9「in/out 遗漏」list 不全 | **accept（待澄清->修正）** | 实际缺 13 方向 |
| 2.1 | 官道跨区模式一致（无独立边界抽象） | **accept** | 5 处跨区 exit 样本一致 |
| 2.2 | 官道 init 遇匪是玩法层非通用机制 | **accept** | mechanisms §1.4 判定准确 |
| 3.1 | ferry + ship 共享载具骨架但复杂度不对称 | **accept** | 157 vs 591 行；MVP 只做 ferry，载具抽象留待 ship 落地 |
| 3.2 | abstraction §4.1「三态共性」表述伪通用 | **accept（推翻初稿）** | horse 与 ferry/ship 无强共性，应拆表 |
| 3.3 | bailong/xiaohongma do_duhe 需特种坐骑扩展点 | **accept** | 2 匹特种马自实现；MVP 不做 post-MVP 评估 |
| 4.1 | engine-comparison P1-P10 正面偏差 | **accept** | 逐条核验无误；P6 加注「仍是纯文案」 |
| 4.2 | engine-comparison N1-N12 负面遗漏 | **accept + 补充 N13/N14** | N9 list 不全；建议增 N13/N14 |
| 4.3 | P6「动态天气正面偏差」定性偏正 | **accept（部分推翻）** | engine 天气仍是纯文案，未接机制 |
| 4.4 | weather_msg 死代码判定 | **accept** | 全仓 grep 仅 1 处定义 |
| 4.5 | event_fun 7 个空操作判定 | **accept** | 全仓 grep 仅 sunrise/common 有定义 |
| 5.1 | 户外/inherit ROOM 计数轻微偏差 | **accept（轻微推翻）** | 1848 vs 1842；3691 vs 3684 |
| 5.2 | player-psychology genmap 消费者列表不完整 | **accept + 补充** | 实际 6 消费者，初稿列 3 |
| 5.3 | engine ferry.py 无 yell/无船房实体 | **accept** | ferry.py 全文核验 |
| 5.4 | engine 模块行数与 brief 一致 | **accept** | 147/554/280/1619 全部核验 |

### 7.2 modern-challenges（现代玩法挑战，7 条质疑）

| # | 质疑条目 | 裁决 | 理由 |
|---|---------|------|------|
| 1 | fast travel「必须」论与文本沉浸矛盾 | **accept（驳回「必须」）** | fast travel 是题材包级别设计选择；genmap.c 证明无 fast travel 是设计选择非技术限制；坐骑+渡船已是题材风味 fast travel |
| 2 | 「迷路=D1 高危」受众错配 + 范围混淆 | **部分 accept** | 定性成立但定量高估；MVP 36 房间不触发断崖；engine 必须为放大预留保护（见 player-experience-risks 折中） |
| 3 | 玩家船「不值得复刻」论证不充分 | **accept** | MVP 本就不做 ship（场景清单未列）；引擎保留载具抽象；MDR「10 档全空文案」应修正为 3 档未实现/7 档已实现 |
| 4 | 昼夜放慢 + 天气机制化是过度现代化 | **accept** | 放慢破坏 day_shop；天气机制化列 post-MVP 且有前置依赖；采纳 player-psychology 基线 |
| 5 | 渡船「纯被动等待=枯燥」忽略节奏价值 | **accept** | 55s 等待是节奏 feature；应补回 yell+船房而非付费跳过 |
| 6 | MDR 与 player-psychology 内部矛盾需裁决 | **accept** | 已逐条裁决（见上表）；以 player-psychology 为基线，MDR 现代化建议降级 post-MVP |
| 7 | MDR 未承认「累积性现代化漂移」 | **accept** | 最终报告已加「现代化累积影响评估」章节 + 判据 |

### 7.3 player-experience-risks（玩家体验风险，7 条质疑）

| # | 质疑条目 | 裁决 | 理由 |
|---|---------|------|------|
| 1 | 「6414 房间」未对齐事实校正，MVP 规模让 D1 断崖高估 | **accept** | 真正房间 3691；MVP 36 房间；engine 必须把保护建进引擎（为放大预留） |
| 2 | 「走累了昏迷」被低估--jingli 是跨系统共享池 | **accept** | 分级提示只延缓不解决根因；须连同 jingli 与战斗资源池关系一起设计 |
| 3 | 马匹体力在 engine 无恢复回路 | **accept（P0）** | RoomResources grass 未接；MVP 0 grass 房；必须补恢复回路 |
| 4 | 渡船在单机 + engine 去 yell 化后玩家无代理权 | **accept（P0）** | engine 去 yell 后玩家纯被动等计时器、搁浅无自救；应恢复召唤权 |
| 5 | 「天气接线为机制」会引入新迷路流失点 | **accept** | 导航保护就位前不接线天气视野机制（时序约束） |
| 6 | genmap.c 既有 BFS 基础设施被当成「未决问题」 | **accept（升为 P0 已决）** | LPC 限流根因是 driver 性能，现代 engine 不存在；应提供地标距离查询能力 |
| 7 | 官道抢劫/exit_blockers 不透明触发 | **accept（P1 新增）** | 声明式 `warn_message` 即可解决 |

### 7.4 commercial-risks（商业化风险，5 类系统性盲区）

| # | 质疑条目 | 裁决 | 理由 |
|---|---------|------|------|
| 1.1 | 坐骑「付费买续航便利」是 pay-to-win 灰色地带 | **accept** | engine 无草地恢复时，付费买续航=付费买可达性；恢复机制必须先免费落地 |
| 1.2 | 渡口「付费缩短等待」是 predatorial design | **accept** | 基础等待是体验空窗时，付费缩短=把设计缺陷变现；须先改造基础等待 |
| 1.3 | 玩家船「付费抗风浪/触礁保险」是 pay-to-win 变体 | **accept** | 惩罚烈度未降级前，付费买保险=保护费式 monetization |
| 1.4 | ship.c is_owner 红线判定悬空且定性不足 | **accept** | engine 无 ship 模块红线无法触发；须区分「游戏内力量 PvP」与「真钱替换游戏内规则」 |
| 2.1 | 分成模型在当前 engine 形态下根本不成立 | **accept** | includes 不支持 rooms + creator 自由字符串 + 透传不算契约三层叠加；不是「留位置」而是架构层阻断 |
| 2.2 | outdoors 降级为 bool 使区域级分成/埋点失去前置依赖 | **accept** | 应先恢复字符串标签或新增 region 字段 |
| 2.3 | LPC 房间路径硬编码使「官方武侠全量包」provenance 不成立 | **accept** | 应明确官方包是「LPC 迁移」还是「新写」（ADR-0001 定位 LPC 为灵感非规格源） |
| 3.1 | 6414 房间官方包在当前 engine 下无法产出 | **accept** | 单文件 rooms 段天花板 + 全量加载；横向扩展战略前置依赖 engine 突破 |
| 3.2 | 大世界无 fast travel 是 D1 流失，「付费买 fast travel」是 pay-to-win 变体 | **accept** | fast travel 须先作为免费基础能力；付费只能买额外加成 |
| 3.3 | 大世界探索深度与新手机会流失矛盾未被商业化消化 | **accept** | 商业化前置依赖体验现代化 |
| 4.1 | 支撑点 4「世界实例隔离」标「已满足」误判 | **accept** | 满足隔离但未满足资产可组合（Roblox 模式核心） |
| 4.2 | 支撑点 2 遗漏版本兼容性声明 | **accept** | PackManifest 应预留 engine_compat 字段 |
| 4.3 | 完全未讨论内容审核 | **accept** | 应补支撑点 5「内容审核导出」 |
| 4.4 | 完全未讨论反作弊/反刷 | **accept** | 应补支撑点 6「反刷/反作弊埋点」 |
| 4.5 | 支撑点 1 遗漏双货币兑换汇率 | **accept** | Iron Realms 模式核心是玩家间市场互换；应拆分为 4 子项 |
| 综合 | 「最该留位置三件事」不足以支撑商业化 | **accept** | 应扩展为至少七件（见 commercial-risks §5） |

### 7.5 performance-risks（性能风险，10 条质疑）

| # | 质疑条目 | 裁决 | 理由 |
|---|---------|------|------|
| 1 | engine 是单玩家 stdin REPL，PR 以「1000 在线」评估是空中楼阁 | **accept** | 应分两层评估（当前 MVP 真实风险 vs 未来可扩展性） |
| 2 | Nature 广播开销被高估 | **accept** | tick 命令驱动，单玩家下 `_outdoor_player_ids` 返回 1 元素；隐藏成本是 `entities_with` 每次 set 构造 |
| 3 | 存档开销被错误归因 | **accept（P0）** | 真实风险是 `DEFAULT_SAVE_INTERVAL=10` 每 10 命令全量 fsync，当前 MVP 就存在 |
| 4 | entities_in_room N² 风险被误置 | **accept** | 当前无并发，N² 不存在；隐藏成本是 set 构造 O(P) |
| 5 | call_out/tick 模型差异影响被低估 | **accept（P0）** | 影响范围是整个时序架构（Nature/渡船/AI），非仅玩家船；idle 时世界冻结 |
| 6 | ON_TICK 扇出未量化 | **accept** | 6 个订阅者同步串行；应列为低风险但需监控 |
| 7 | 渡船在 engine 下无 yell 触发，idle 时不翻转 | **accept** | 量级对但遗漏语义偏差 |
| 8 | 6414 房间全量加载未连接到存档成本 | **accept** | 加载越多 -> entity 越多 -> 每 10 命令存档越慢（乘数效应） |
| 9 | 玩家船 navigate 性能基于 LPC call_out，engine 无法复刻 | **accept** | engine 无 ship，分析是 LPC 风险非 engine 风险 |
| 10 | PR「达标」判定过于乐观 | **accept** | 应拆为两列（当前 MVP vs 未来 1000 在线） |

---

## 8. 未决问题

### 8.1 引擎设计层

1. **jingli 是否拆成「移动体力」与「战斗精力」两个池**？LPC 共用 jingli（`kungfu/skill/*.c` + `go.c` + `train.c` 共证），是失配惩罚根因。engine 是否沿用单池，还是借重写机会拆分？（影响移动疲劳软着陆的设计形状）
2. **载具实体抽象是否在 MVP 阶段定形**？当前只有 ferry 1 个实例。若抽象先行于实例存在过度设计风险；若等 ship 落地再定形，ferry 与 ship 抽象可能在 ship 实现时被推翻。
3. **单 on_tick 模型 vs 墙钟定时器**：玩家船 / 自动巡逻 NPC / 昼夜推进等「时间驱动」需求在 engine 单 on_tick（命令驱动）模型下如何实现？是否需要引入独立墙钟定时器层？（影响可扩展性架构，可能需 ADR）
4. **全量存档 vs LPC reset 重建**：engine 选择存档所有可变态实体（含房间门），LPC 只存玩家靠 reset 重建世界。哪种更适合 1000 在线 + UGC 横向扩展？（影响存档策略与重启体验）
5. **懒加载 vs 全量加载**：UGC 大题材包下 engine 是否回归 LPC 懒加载模式？跨区 exit 引用如何解？（影响启动时间与内存）
6. **特种坐骑命令扩展点是否进 MVP**：bailong/xiaohongma 的 do_duhe 是武侠题材特化，MVP 可不做但 engine 是否留位置？
7. **方向词缺失 13 个的处理优先级**：MVP 是否需要补 enter/out（渡船/船只必需）？left/right/*up/*down 是否可延后？

### 8.2 体验与商业化层

8. **MVP 36 间房是否仍需建区域归属/导航提示**，还是等官方武侠包放大时再建？若 MVP 不建，engine 接口是否预留？
9. **渡船在 engine 已去 yell 的前提下，是否恢复某种玩家主动权**（召唤/等候/召回），还是接受「纯定时门」并靠 `ferry_status_line` 提示兜底？
10. **`xiaohongma` 独占渡河技能是否属力量优势**？commercialization 已判 ability 付费为红线，但「独占交通能力」对「可达区域」的 gating 效应未评估。
11. **官方武侠包是「LPC 迁移」还是「新写」**？ADR-0001 定位 LPC 为灵感非规格源，若新写则 provenance 从零建但创作成本高。
12. **「多小的包能卖钱」阈值**：横向扩展战略要求每个包有足够内容量支撑付费，小切片包的付费意愿是否足够？

### 8.3 事实待澄清

13. **weather_msg 是否在历史上有过接线实现、后被移除**？当前是死代码，但 day_phase 数据结构留了天气扩展位。需考古确认是「设计未完成」还是「曾经有后移除」。
14. **is_owner 霸船在单机 MVP 下应完全移除，还是改造为「NPC 船客/海盗霸船」的 PvE 压力**？

---

## 9. 附录：文件清单

### 9.1 输入文件（均已 Read，无缺失）

| 路径 | 产出角色 | 状态 |
|------|---------|------|
| `00-brief/brief.md` | 调研总则 | 已读 |
| `01-raw-findings/source-inventory.md` | LPC 源码考古员 | 已读（含事实校正，见 §1.4） |
| `01-raw-findings/gameplay-slices.md` | 玩法切片策划 | 已读 |
| `01-raw-findings/mechanisms.md` | 空间/移动机制设计师 | 已读（含事实校正） |
| `02-user-stories/player-stories.md` | 玩法切片策划 | 已读 |
| `02-user-stories/system-stories.md` | 空间/移动机制设计师 | 已读 |
| `02-user-stories/operator-stories.md` | UGC 游戏专家 | 已读 |
| `03-engine-insights/abstraction-options.md` | 引擎架构师 A | 已读 |
| `03-engine-insights/ugc-surface.md` | 引擎架构师 B | 已读 |
| `03-engine-insights/modern-design-review.md` | 现代世界/关卡设计师 | 已读 |
| `03-engine-insights/player-psychology.md` | 玩家心理与留存专家 | 已读 |
| `03-engine-insights/commercialization.md` | 商业化与增长专家 | 已读 |
| `03-engine-insights/performance-review.md` | 性能与可扩展性专家 | 已读 |
| `03-engine-insights/creator-perspective.md` | UGC 游戏专家 | 已读 |
| `06-engine-critique/engine-comparison.md` | engine 批判对照员 | 已读 |
| `04-redteam-review/cross-check-report.md` | 横向对比验证员（红队） | 已读 |
| `04-redteam-review/modern-challenges.md` | 现代玩法挑战者（红队） | 已读 |
| `04-redteam-review/player-experience-risks.md` | 玩家体验风险挑战者（红队） | 已读 |
| `04-redteam-review/commercial-risks.md` | 商业化风险挑战者（红队） | 已读 |
| `04-redteam-review/performance-risks.md` | 性能风险挑战者（红队） | 已读 |

### 9.2 关键 LPC 源码证据索引

- `d/REGIONS.h` - 34 区域映射（`region_names`）
- `d/village/alley1.c` - 房间定义模式样例
- `inherit/room/room.c`（281 行）- 基础房间（门/reset/make_inventory/setup/valid_leave）
- `feature/move.c`（154 行）- 对象搬迁原语（负重/weight/unequip）
- `cmds/std/go.c`（289 行）- 玩家移动命令（exits/门/骑乘/cost/follow）
- `feature/team.c`（127 行）- 跟随/队伍（set_leader/follow_me）
- `feature/message.c`（~75 行）- 消息接收与户外/天气过滤
- `adm/daemons/natured.c`（193 行）- Nature daemon（昼夜循环/广播/event_fun）
- `adm/etc/nature/day_phase`（65 行）- 8 时段数据
- `inherit/room/ferry.c`（157 行）- 渡口（yell/check_trigger/on_board/arrive/close_passage）
- `inherit/room/ship.c`（591 行）- 海船（start/navigate/go/lookout/locate/shipweather/do_drop）
- `inherit/room/harbor.c`（~140 行）- 港口（yell 唤船/登船收费）
- `clone/ship/harbor.h` / `seashape.h` - 港口/海岛/暗礁坐标
- `clone/horse/horse.h`（~85 行）- 马匹体力/坠骑/吃草/跟随
- `clone/horse/baima.c` / `bailong.c` / `xiaohongma.c` - 普通/特种马实例
- `clone/obj/genmap.c` / `mapdb.c` - BFS 地图生成器/路径数据库（存在但不暴露玩家）
- `inherit/char/trainee.c`（232 行）- 可驯服动物基类

### 9.3 关键 engine 模块证据索引

- `engine/src/openmud/nature.py`（554 行）- NatureState/DayPhase/Weather/ON_NATURE_CHANGE
- `engine/src/openmud/world.py`（280 行）- World ECS 容器（room_ids/entities_in_room/entities_with）
- `engine/src/openmud/room_hooks.py`（732 行）- RoomHook 协议 + 8 内置机关钩子
- `engine/src/openmud/room_details.py`（112 行）- RoomDetails N1 匹配 + 名(id) 扫描
- `engine/src/openmud/ferry.py`（147 行）- FerryCrossing/FerryState（纯定时翻转，无 yell/无船房）
- `engine/src/openmud/directions.py`（114 行）- 方向别名/中英文解析（缺 13 方向）
- `engine/src/openmud/transfer.py`（363 行）- 物品转移原语（堆叠/拆分/防嵌套）
- `engine/src/openmud/scene_loader.py`（1619 行）- YAML 场景加载器
- `engine/src/openmud/scenes.py`（44 行）- 场景路径选择器
- `engine/src/openmud/components.py` - 组件定义（Description/Exits/Door/Mount/Terrain/Ferry/RoomResources/LocalNature/Currency）
- `engine/src/openmud/commands.py` - go 命令（门/地形/骑乘/精力/移动）+ _buy/_buy_mount
- `engine/src/openmud/cli.py` - 单玩家 stdin REPL 主循环
- `engine/src/openmud/tick.py` - DEFAULT_SAVE_INTERVAL=10 + ON_TICK 分发
- `engine/src/openmud/save.py` - save_world 全量每实体 fsync
- `engine/src/openmud/pack.py` - PackManifest（id/version/creator/title，无 engine_compat）

---

## 终审一句话

Phase 1 产出整体质量较高，主要事实判定（weather_msg 死代码、event_fun 空操作、engine 缺失 ship/region/leader/follow、渡船 yell 交互缺失、ferry 简化模型偏差等）经红队核验均准确；但在区域键数（34 非 38）、子目录数（41 非 43）、马匹 .c 数（21 非 22）、方向键数（23 非 22）、特种坐骑覆盖盲点（bailong + xiaohongma 双双未 include horse.h）、engine 单玩家 REPL 与 tick 命令驱动六处存在事实错误或覆盖盲点，已在报告中修正。评审委员会以 player-psychology 为体验基线、MDR 现代化建议降级 post-MVP、commercial-risks 收紧便利性付费边界、performance-risks 重排风险优先级，完成统一文风与分歧裁决。
