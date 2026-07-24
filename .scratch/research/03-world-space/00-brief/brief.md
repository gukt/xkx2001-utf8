# 03-world-space 调研总则

> 本次调研属于 `.scratch/research/` 下第 3 个研究主题。**主题=世界空间层**：地图（拓扑基底）+ Nature（环境叠加层）+ 交通（跨区移动层），三层统一调研，强调三者交互。本调研与 01-quest-system 最大不同在于：新引擎已建出 nature.py/world.py/ferry.py 等模块，故采用「LPC 考古为主 + 批判性对照现有 engine」模式。

## 1. 调研目标

1. **忠实还原 LPC 原始细节**：基于当前仓库一手源码，梳理《侠客行》世界空间层（地图拓扑 / Nature 昼夜天气 / 交通载具与跨区移动）的实现方式、数据结构、调用链与状态流转。
2. **提取设计灵感与风险警示**：从现代世界/关卡设计、玩家心理、商业化、性能与 UGC 创作角度，输出对新引擎可参考的方向、应避免的过时模式以及需警惕的设计陷阱。
3. **批判性对照现有 engine**：审阅 `engine/src/openmud/` 下 nature.py / world.py / room_hooks.py / room_details.py / ferry.py / directions.py / transfer.py / scene_loader.py / scenes.py，标注与 LPC 原始设计的偏差与遗漏。engine 模块**仅作批判对照对象，不作反向脑补来源**。
4. **不输出 engine 接口草案**：本次调研止步于设计输入层，具体 engine 抽象与接口设计留待后续任务单独决策。

## 2. 范围边界

### 2.1 纳入范围

**地图（拓扑基底）**
- `d/` 下 35 个区域、6414 个房间（`d/REGIONS.h` 声明区域映射；最大区域 beijing 625 / dali 467 / city 扬州 441 / xingxiu 388 / shaolin 368）。
- 基础房间继承 `inherit/room/room.c`（281 行）：门（create_door/check_door/look_door/query_doors）、valid_leave、reset、make_inventory、setup。
- 房间定义模式：`inherit ROOM;` + `create()` 设置 `short`/`long`/`exits`(方向->目标房间 mapping)/`outdoors`(户外标志)/`objects`(NPC 生成)/`cost`(移动消耗)/`no_clean_up` + `setup()` + `replace_program(ROOM)`。示例：`d/village/alley1.c`。
- 移动机制 `feature/move.c`（154 行）：`move(dest, silently)` + 负重/重量 + 装备卸下检查。

**Nature（环境叠加层）**
- `adm/daemons/natured.c`（193 行）：day_phase 循环（call_out 驱动）、`weather_msg` 5 档天气、event_fun 回调（event_dawn/sunrise/noon…）、`outdoor_room_description()`、经 `message("outdoor:vision", msg, users())` 向所有户外玩家广播。
- `adm/etc/nature/day_phase`：8 时段数据（dawn/sunrise/morning/noon/afternoon/evening/night…），每段 length/time_msg/desc_msg/event_fun。
- 户外判定：房间 `set("outdoors", "xxx")` -> 户间才收到 Nature 广播与时段描述。

**交通（跨区移动层）**
- 坐骑 `clone/horse/`（22 个马匹 + horse.h）：`condition_check()` 体力衰减，jingli<=10 马匹昏厥、骑手坠落受伤；rider/rided 关系；`set_leader` 跟随。
- 渡口 `inherit/room/ferry.c`（157 行）：`do_yell`/`check_trigger`/`on_board`/`arrive`/`close_passage`，call_out 驱动渡船周期。
- 船只 `inherit/room/ship.c`（591 行）：玩家船系统 `do_start`/`navigate`/`do_go`/`do_stop`/`do_lookout`/`do_locate`/`shipweather`/`niceweather`/`do_ready`/`do_drop`，含导航、天气、瞭望、所有权。`clone/ship/seaboat1-3.c`。
- 官道：`d/*/road*.c` / `*road*.c` 遍布各区（cross-region 连接）。

### 2.2 不纳入范围

- 不做 LPC 行为等价验证（[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）。
- 不把 engine 侧现有实现当作正确形态反向脑补（engine 仅作批判对照）。
- 不依赖旧文档结论（`docs/archive/` 仅作必要时二手参考）。
- 不输出可直接落地的 engine 代码或接口契约。
- 不纳入具体区域内容设计（房间文案/迷宫布局的文学性），只调研机制与结构。

## 3. 调研团队与职责（12 席 + 评审委员会）

### 3.1 一手考古组

| 角色 | 职责 | 产出 |
|------|------|------|
| LPC 源码考古员 | 逐目录盘点地图/Nature/交通相关源码，输出代码清单、调用链、数据结构、关键回调与状态变量 | `01-raw-findings/source-inventory.md` |
| 玩法切片策划 | 挑 4-6 类代表性玩法切片（如扬州城内导航、华山村->少林官道骑乘、渡口过江、昼夜商店、天气影响、玩家船航海） | `01-raw-findings/gameplay-slices.md`、`02-user-stories/player-stories.md` |

### 3.2 机制抽象组

| 角色 | 职责 | 产出 |
|------|------|------|
| 空间/移动机制设计师 | 抽象通用机制：拓扑/出口、门、导航、移动与移动消耗、坐骑体力、渡船周期、船只导航、昼夜时段、天气、户外广播 | `01-raw-findings/mechanisms.md`、`02-user-stories/system-stories.md` |
| 引擎架构师 A | 把通用机制映射到题材无关 engine 核心，输出抽象方案与可选方向 | `03-engine-insights/abstraction-options.md` |
| 引擎架构师 B | 思考题材包（UGC）创作层应暴露的最小表面 | `03-engine-insights/ugc-surface.md` |
| UGC 游戏专家 | 从创作者视角审视空间/交通可扩展性（摆房间、连区域、设门、设交通、配 Nature） | `03-engine-insights/creator-perspective.md`、`02-user-stories/operator-stories.md` |
| 横向对比验证员 | 交叉检查各区域/各交通实现，找出共用模式与特例，验证抽象覆盖度 | `04-redteam-review/cross-check-report.md` |

### 3.3 现代评审组

| 角色 | 职责 | 产出 |
|------|------|------|
| 现代世界/关卡设计师 | 对标开放世界导航、fast travel、地图现代化、移动节奏，评估 LPC 机制当代可玩性与过时风险 | `03-engine-insights/modern-design-review.md`、`04-redteam-review/modern-challenges.md` |
| 玩家心理与留存专家 | 探索动机、迷路挫败、移动疲劳、心流节奏、社交压力 | `03-engine-insights/player-psychology.md`、`04-redteam-review/player-experience-risks.md` |
| 商业化与增长专家 | 题材包地图资产、交通作为消费点、创作者经济、用户增长 | `03-engine-insights/commercialization.md`、`04-redteam-review/commercial-risks.md` |
| 性能与可扩展性专家 | 大世界拓扑查询、Nature 全员广播开销、交通并发、call_out 周期、6414 房间规模 | `03-engine-insights/performance-review.md`、`04-redteam-review/performance-risks.md` |

### 3.4 终审组（评审委员会，5 人）

玩法切片策划 + 引擎架构师 A + UGC 游戏专家 + 现代世界/关卡设计师 + 商业化与增长专家。

职责：审阅所有初稿与红队报告 -> 组织对抗 -> 对分歧裁决 -> 统一文风、消除矛盾 -> 生成最终报告。

## 4. 调研方法

### 4.1 多 Agent 并行 Workflow（三阶段）

- **Phase 1：并行初稿**（11 席并行）：各角色同步阅读源码并产出指定章节初稿。一手考古组与机制抽象组先跑，现代评审组同时跑（基于源码而非初稿，避免 barrier 等待）。
- **Phase 2：红队对抗**（5 路并行）：横向对比验证、现代玩法挑战、体验风险挑战、商业化风险挑战、性能风险挑战。每条质疑必须引用被质疑文件与段落。
- **Phase 3：评审委员会汇总**（1 个 xhigh agent）：统一文风、消除矛盾、对红队质疑裁决、标注未决问题，生成最终报告。

### 4.2 资料来源优先级

1. 当前仓库根目录下 LPC 源码（`d/`、`adm/daemons/natured.c`、`adm/etc/nature/`、`clone/horse/`、`clone/ship/`、`inherit/room/`、`feature/move.c`）--**唯一真相源**。
2. `engine/src/openmud/` 下已建模块--**仅作批判对照对象**（产出在 `06-engine-critique/`）。
3. `docs/archive/` 与现有 `.scratch/m1-core-engine-skeleton/research/03-nature.md` 等--必要时二手参考。

## 5. 输出目录结构（7 层）

```
.scratch/research/03-world-space/
├── 00-brief/               # 本总则
├── 01-raw-findings/        # source-inventory / gameplay-slices / mechanisms
├── 02-user-stories/        # player / operator-wizard / system-auto（三层全覆盖）
├── 03-engine-insights/     # abstraction-options / ugc-surface / modern-design-review
│                           # / player-psychology / commercialization / performance-review / creator-perspective
├── 04-redteam-review/      # cross-check / modern-challenges / player-experience-risks
│                           # / commercial-risks / performance-risks
├── 05-synthesis/           # final-report.md
└── 06-engine-critique/     # 逐项对照 nature.py/world.py/ferry.py/room_hooks.py/room_details.py
                            # /directions.py/transfer.py/scene_loader.py/scenes.py 与 LPC 设计
```

## 6. 关键约束

- **基于一手资料**：所有结论必须能从当前仓库源码中找到证据（标注文件路径 + 函数/对象名）。
- **全局与细节兼顾**：既要有宏观脉络（6414 房间/35 区域/8 时段/3 类交通），也要有代表性实例细节（alley1.c 房间模式、ferry.c 渡口周期、ship.c 导航）。
- **现代视角批判**：对过时、不符合当代玩家习惯或商业化潜力的设计显式标注。
- **engine 对照可证伪**：每条 engine 偏差/遗漏标注必须同时给出 LPC 证据与 engine 模块位置。
- **User Stories 完整**：覆盖玩家、巫师/运营、系统/NPC 自动触发三层。
