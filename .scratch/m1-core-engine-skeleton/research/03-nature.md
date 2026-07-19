> 本文是 2026-07-19 M1 扩展调研的**原始 subagent 输出**（Nature 系统调研员），完整保留，未做二次精简。汇总与 scope 决策见 [../research-m1-extension-items-npc-nature.md](../research-m1-extension-items-npc-nature.md)。
>
> 立场：LPC 是设计灵感与术语参考，不是规格源（ADR-0001）。

---

调研完成，以下是 Nature 系统调研报告。

# Nature 系统调研报告（为 M1 落地提供决策输入）

## 0. 一个必须先纠正的认知偏差

用户在任务里把"天气/季节/自然事件"都列进了调研维度，但**LPC 源码的实际实现远比拆解文档描述的窄**。拆解文档（02、05）把 NATURE_D 描述成"时间、天气、昼夜循环"守护进程，但通读 `adm/daemons/natured.c`（194 行）后会看到：

- **天气系统是半成品/未接线**：`weather_msg` 数组（5 条云况描述）声明了，但**全文件没有任何函数读取或切换它**，`outdoor_room_description()` 返回的是 `day_phase[current_day_phase]["desc_msg"]`（时辰描述），与天气无关。全仓 grep `weather` 只有 `natured.c` 自己声明 + `ship.c`（船只在恶劣天气的事件，独立于 NATURE_D）。
- **季节系统不存在**：没有 `query_season` / 季节循环，`game_time()` 只是 `CHINESE_D->chinese_date()` 的中文化日期。
- **自然事件不存在**：没有流星/地震/特殊天象的随机事件机制；`event_*` 系列是固定时辰触发的固定函数（存档、inventory_check），不是随机事件。

所以新引擎如果要做"天气 + 季节 + 随机事件"，本质是**从设计灵感出发的全新设计**，不是从 LPC 复刻。这一点对 scope 判断很关键。

## 1. Nature 系统全景

LPC 侠客行的 Nature 系统**核心设计思想是「全局单例守护进程 + 房间/物品按需查询当前时辰」**，而非「守护进程主动向订阅者推送」。具体形态：

- **NATURE_D 是一个常驻单例**（`create()` 时 `read_table` 读配置、`init_day_phase()` 算当前时辰、`call_out("update_day_phase", ...)` 定时推进）。它持有 `current_day_phase` 索引和 `day_phase` 配置数组，对外暴露极简查询接口：`outdoor_room_description()`（返回当前时辰的 `desc_msg`）、`outdoor_room_event()`（返回当前时辰的 `event_fun` 字符串名）、`game_time()`（中文日期）。
- **驱动方式是 `call_out` 定时器**，不是 `heart_beat`。每个时辰结束时 `update_day_phase()` 被回调一次：发 `outdoor:vision` 广播给所有在线玩家（时辰切换文案）-> 若该时辰配了 `event_fun` 就 `call_other` 调用它 -> 调 `event_common()`（inventory_check）。
- **时间模型**：`#define TIME_TICK (time()*60)`，即真实 1 秒 = 游戏 1 分钟，游戏 1 天 = 真实 24 分钟。8 个时辰（dawn/sunrise/morning/noon/afternoon/evening/night/midnight），每个时辰 length 在配置里以"分钟"为单位，时辰总长 = 1440 分钟 = 1 游戏天。重启时 `init_day_phase()` 用 `localtime` 重新对齐到当前真实时间对应的时辰（**时间不存档，靠与现实时钟对齐恢复**）。
- **关联架构是"被动查询"为主**：房间在 `look` 时调 `NATURE_D->outdoor_room_description()` 拼到 long 末尾；物品/房间逻辑在关键时刻调 `NATURE_D->outdoor_room_event()` 拿时辰事件名做字符串比较条件。**没有"Nature 状态变化时主动通知订阅者"的机制**--唯一的"主动推送"是时辰切换那一刻给所有在线玩家发一条 `outdoor:vision` 广播文案。

**对新引擎的核心启发**：LPC 这个"被动查询"模型其实非常适合新引擎的 ECS + TickLoop 架构。TickLoop（已实现，M1 只挂存档）天然就是 Nature 时间推进的挂载点；房间/物品逻辑要拿时间时，向 Nature 系统查询当前状态即可，不需要订阅。**但"时辰切换时给所有户外玩家推送文案"这一条主动广播，是新引擎值得保留的设计**（否则玩家感知不到时间在流动），这要求 Nature 系统能在 tick 边界产生"事件"并让命令/广播层消费。这正是用户提的"Nature 事件触发器"诉求。

## 2. 核心功能点清单（按 11 个调研维度）

| # | 维度 | 出处 | 关键机制 | 对新引擎设计启发 |
|---|------|------|----------|------------------|
| 1 | 职责全貌 | `natured.c` 全文 | 管 day_phase（时辰）+ 定时存档 + inventory_check；天气/季节/自然事件**未实现** | 新引擎 Nature 职责应明确收窄为"时辰 + 天气"两件，季节/随机事件留设计位不实现 |
| 2 | 时间系统 | `natured.c` init_day_phase + `day_phase` 配置 | 8 时辰（dawn/sunrise/morning/noon/afternoon/evening/night/midnight），游戏/现实比例 60:1，重启靠 localtime 对齐 | 时辰是数据驱动的（YAML 配 length/time_msg/desc_msg/event_fun）；时间推进挂 TickLoop，重启不存档、用真实时钟对齐可复用 |
| 3 | 天气系统 | `weather_msg` 数组（未接线） | 声明了 5 条云况，无切换逻辑、无影响 | 新引擎要从零设计天气切换：建议「时辰 tick 内随机切换 + 季节权重表」，但 M1 可只做"晴/雨"两态验证管线 |
| 4 | 季节系统 | 无 | 不存在 | 留设计位（NatureState 含 season 字段），M1 不实现 |
| 5 | 自然事件 | `event_sunrise`/`event_common` | 固定时辰触发固定函数，非随机事件 | 区分"时辰切换事件"（确定性，M1 可做）与"随机自然事件"（延后）；M1 的 event 就类比 event_sunrise |
| 6 | **Nature↔文案** | `look.c:46` + `natured.c:144` | 房间设 `outdoors` 属性，look 时把 `outdoor_room_description()`（当前时辰 desc_msg）拼到 long 末尾 | 新引擎 Description 组件加 `outdoors` 标志 + 时辰描述表；look 命令拼描述时查询 Nature 当前时辰描述 |
| 7 | **Nature↔门** | `gate.c`/`muding.c` 实际用法 | 门本身不随时间自动开关；时间条件是**物品/房间逻辑主动查询** `outdoor_room_event()` | "夜里城门关闭"在 LPC 里没有现成实现，是新需求；门系统可暴露"条件开放规则"由 Nature 状态判定 |
| 8 | **Nature↔条件规则** | `sleep.c:42`/`muding.c:90` | `event = NATURE_D->outdoor_room_event(); if (event != "event_night" ...)` 字符串比较 | 通用条件判定核心：Nature 暴露结构化谓词（is_night/is_raining/phase==），DSL 表达式求值时调它 |
| 9 | Nature↔NPC | 无统一机制（散落在各 NPC 文件） | NPC 作息靠各自 `init`/`heart_beat` 里调 NATURE_D | 新引擎 NPC 行为系统未引入，此项必须延后 |
| 10 | Nature↔物品 | `muding.c:90`（神木王鼎） | 物品 do_put 里判断 `event_dawn` 才触发冰蚕事件 | 物品行为钩子查 Nature 状态做条件，M1 可用静态物品演示 |
| 11 | Nature↔存档 | `event_sunrise` + 守护进程"不保存" | NATURE_D 本身不 save_object，时间靠 localtime 对齐 | 新引擎时间不存档、重启对齐真实时钟；NatureState 是纯内存态，与 save.py 边界清晰 |

## 3. 与其他系统关联点（用户最关注，详尽展开）

### 3.1 Nature ↔ 文案（动态描述拼接）
- **数据怎么流**：`cmds/std/look.c:42-46` 里 `str = sprintf("%s - %s\n    %s%s", short, ..., long, env->query("outdoors")? NATURE_D->outdoor_room_description() : "")`。即房间的 `outdoors` 属性是开关，开了就追加 Nature 的当前时辰 `desc_msg`。
- **触发点**：玩家 `look`（被动查询，不是订阅）。Nature 时辰切换的 `update_day_phase` 里 `message("outdoor:vision", time_msg, users())` 是另一条独立路径--时辰切换瞬间给所有在线玩家发一条 `time_msg`（如"太阳从东方升起"）。
- **耦合度**：低。look 命令依赖 NATURE_D 的一个无参函数，房间只需声明 `outdoors` 字符串。新引擎复刻成本低：Description 组件加 `outdoors` 布尔/字符串字段，look 命令拼描述时查 Nature。
- **LPC 局限**：文案只能按"时辰"变（8 种），不能按"天气"变（weather_msg 没接线）。新引擎若做天气，描述表要从「时辰 -> desc」升级为「时辰 × 天气 -> desc」二维表。

### 3.2 Nature ↔ 门系统（条件出口/动态开关）
- **LPC 实际情况**：`inherit/room/room.c` 的门系统（create_door/open_door/close_door/valid_leave）**完全不知道 Nature 的存在**。门的开关是玩家/NPC 主动 `open`/`close` 或 `call_out` 定时自动关（如 `gate.c` 的 `close_door` 10 秒后自动关）。`gate.c`（重阳宫大门）的 `do_knock` 里取了 `NATURE_D->outdoor_room_event()` 但**实际没用它做时间门控**--门控靠的是敲门动作 + NPC present 检查。
- **结论**："夜里城门关闭/雨天渡口停渡"在 LPC 侠客行里**没有现成实现**，是用户基于武侠常识提出的新需求，新引擎要从零设计。
- **数据怎么流（新引擎设计建议）**：门/出口的开放规则应表达为"条件表达式"，条件求值时查 Nature 状态。建议挂在 `Exits`/`Doors` 组件上，加一个"条件开放规则"字段，`valid_leave`/`can_traverse` 检查时求值。
- **触发点**：玩家 `go` 命令时求值条件（被动）；可选地，Nature 时辰切换时主动求值所有受影响门的状态并广播变化文案。
- **耦合度**：中。门系统需要能调用条件判定器，条件判定器需要能查询 Nature。建议通过"条件表达式求值器"中介，门系统不直接 import Nature。

### 3.3 Nature ↔ 条件规则判定（通用机制，用户重点）
- **LPC 实际机制**：**没有通用条件引擎**。每个用法都是硬编码字符串比较：`sleep.c:42-44` 的 `if (event != "event_night" && event != "event_midnight" && event != "event_dawn")`，`muding.c:90` 的 `if (NATURE_D->outdoor_room_event() == "event_dawn" && interactive(me) && random(...) == 1)`。条件是 LPC 代码里直接写的 `if`，不是数据驱动的表达式。
- **数据怎么流**：调用方（命令/物品/房间逻辑）-> `NATURE_D->outdoor_room_event()` 拿字符串 -> 本地 `if` 比较。Nature 不主动推送，全靠调用方在需要的时刻拉取。
- **触发点**：散落在各命令/物品 `do_*` 函数里，时机由调用方决定。
- **耦合度**：高且散乱。每个调用方都直接 `call_other(NATURE_D, ...)`，改 Nature 接口要改所有调用点。
- **对新引擎的核心启发**：这是用户最该投入设计的地方。新引擎应做**结构化条件表达式**（如 `phase == night`、`weather == rain`、`phase == night and weather == rain`），由一个通用 Condition 求值器统一求值，Nature 只负责提供原始状态谓词。这样 DSL 才能声明式表达，而不是每个地方写 Python if。LPC 的字符串比较是反例，不要照搬。

### 3.4 Nature ↔ NPC（作息/行为随天气）
- **LPC 实际情况**：没有统一作息系统。`event_common()` 遍历 `livings()` 做的是 inventory_check 和清理无环境对象，不是 NPC 作息。NPC 行为散落在各 NPC 文件的 `init`/`heart_beat` 里（未在本次范围深挖）。
- **结论**：新引擎 NPC 行为系统尚未引入（M1 只有静态展示型 NPC），此项**必须延后到 M2+**，不能在 M1 做。

### 3.5 Nature ↔ 物品（条件行为/刷新）
- **LPC 实际案例**：`muding.c`（神木王鼎）`do_put` 里放香后，只有 `event_dawn`（凌晨）+ 随机条件才触发冰蚕事件，否则走另一条 `open_up` 路径。这是"Nature 状态作为物品行为分支条件"的真实案例。
- **数据怎么流**：物品 `do_put`（玩家动作）-> 查 `outdoor_room_event()` -> 分支。
- **触发点**：玩家与物品交互时。
- **耦合度**：中，物品逻辑直接调 NATURE_D。新引擎通过条件表达式中介可降低耦合。火把/湿柴这类"天气影响物品可用性"在 LPC 里没有现成实现，是新需求。
- **物品刷新**：`room.c` 的 `reset()` 与 Nature 无关，是独立的房间刷新机制（按 `no_clean_up` 计数触发）。

### 3.6 Nature ↔ 存档
- **LPC 实际情况**：NATURE_D 是守护进程，**不 save_object**，重启时 `create()` -> `init_day_phase()` 用 `localtime(time()*60)` 重新对齐当前时辰。`event_sunrise` 里调玩家 `save()`，但那是 Nature **触发**存档，不是 Nature **被**存档。
- **结论**：Nature 时间状态是纯内存态、靠真实时钟对齐恢复。新引擎直接复用这个模型：NatureState 不进存档，重启对齐真实时钟。这与新引擎 save.py「内存态权威 + 周期快照」的边界完全一致，零冲突。

## 4. M1 scope 建议（三档）

### M1 必做（核心闭环，验证"被动查询"管线）
1. **时辰循环引擎**：数据驱动的 day_phase 配置（YAML：phase 名/length 分钟/time_msg/desc_msg），挂载到 TickLoop 推进（每个 tick 推进一定游戏分钟，比例可配，默认沿用 60:1）。NatureState 纯内存，重启对齐真实时钟。**这是地基**。
2. **Nature 查询接口**：暴露结构化谓词 `phase` / `is_night` / `is_day` / `game_time_str`，供其他系统查询。**不要用 LPC 的字符串比较反例**，直接给结构化值。
3. **文案动态拼接（Nature↔文案）**：Description 组件加 `outdoors` 字段；look 命令拼描述时，户外房间追加当前时辰 `desc_msg`。这是用户重点里最轻量、最值得 M1 做的关联。
4. **时辰切换广播**：时辰切换时给所有"户外"房间的在线玩家推送 `time_msg`（对应 LPC 的 `message("outdoor:vision", ...)`）。让玩家感知时间流动，这是体验闭环。
5. **通用条件表达式求值器（最小版）**：支持 `phase == night`、`is_night`、`and`/`or`/`not` 组合的布尔表达式，求值时查 Nature。**这是用户重点"条件规则判定"的落地**，也是门/物品动态规则的地基。M1 只接 Nature 一个状态源，未来扩展到玩家属性/任务状态。

### M1 可做（若 M1 工作量有余量，且不阻塞）
- **天气系统骨架**：晴/雨两态，按时辰 tick 随机切换（带切换概率），NatureState 增加 `weather` 字段 + `is_raining` 谓词。描述表从「时辰 -> desc」升级为「时辰 × 天气 -> desc」二维查询。**判断**：天气是用户明确点名要的，但完整天气（6 种 + 季节权重 + 对移动/战斗/视野影响）依赖战斗/移动系统未就绪，M1 只做"切换 + 文案 + 条件谓词"骨架，不做"对玩家的影响"。
- **门/出口条件开放规则（DSL 声明 + 求值）**：Doors/Exits 组件加"条件开放"字段，`go` 命令求值条件决定能否通过 + 文案。**判断**：依赖条件求值器（M1 必做项），可顺带演示，但要克制--只做"夜里城门关"一个 demo 场景。

### 延后 M2+（依赖尚未引入的系统）
- **NPC 作息/行为随天气**：依赖 NPC 行为系统（M1 只有静态展示型 NPC），**必须延后**。
- **天气对战斗/移动/视野的影响**：依赖战斗结算（ADR-0004 已定边界但未实现）和移动系统扩展，延后。
- **季节系统**：LPC 本就没有，新引擎从零设计，留 NatureState.season 字段占位，M2 再填。
- **随机自然事件（流星/地震/特殊天象）**：需要事件广播总线 + 事件效果系统，超出 M1 范围，延后。
- **天气影响物品可用性（火把/湿柴）**：依赖物品行为钩子系统成熟，可 M2。

### 直接回答用户的核心问题

> M1 的 Nature 做到"时间循环 + 天气 + 文案动态 + 条件规则判定"这个范围是否合理？

**部分合理，需要裁剪**。建议 M1 收敛为：**时间循环（时辰，必做）+ 文案动态拼接（必做）+ 条件规则判定求值器（必做）+ 时辰切换广播（必做）+ 天气骨架（可选，只做晴雨切换+文案+谓词，不做对玩家影响）**。"天气对玩家影响""门随天气""NPC 作息"都依赖未引入系统，应推迟。条件规则判定求值器是这四项里**最该优先做、最值得投入设计**的，因为它是门/物品/NPC 三类动态规则的共同地基，LPC 没做好（字符串比较散落），新引擎必须做对。

> 哪些关联需要依赖尚未引入的系统故应推迟？

- 门随天气自动开关 -> 部分依赖条件求值器（M1 有）可做 demo，但"雨天渡口停渡"等带影响后果的延后。
- NPC 作息 -> 依赖 NPC 行为系统，**必须推迟 M2+**。
- 天气对战斗/移动/视野影响 -> 依赖战斗/移动系统，**推迟 M2+**。
- 随机自然事件 -> 依赖事件总线，**推迟 M2+**。

## 5. DSL 动态规则表达草稿（4 个示意，用于讨论非最终格式）

### 草稿 ① 房间文案随时间/天气拼接（Nature↔文案）

```yaml
# 房间 YAML：户外房间声明时辰/天气描述表，look 时由引擎查询 Nature 当前状态选 desc
rooms:
  - id: yangzhou_guangchang
    short: 扬州中央广场
    long: |
      城市的正中心是一个很宽阔的广场……
    outdoors: true                    # 开关：开启动态环境描述拼接
    nature_desc:                      # 可选：覆盖默认时辰描述（不写则用 Nature 全局 desc 表）
      by_phase:
        night:    "    夜幕笼罩着广场，四下寂然无声。\n"
        midnight: "    月色如水，广场上空无一人。\n"
      by_weather:                     # 天气维度叠加（晴/雨），与时辰独立
        rain:     "    细雨绵绵，青石板泛着水光。\n"
```

引擎行为：look 拼描述 = `long` +（outdoors 时）`nature_desc.by_phase[当前phase]`（缺省回退 Nature 全局表）+（若天气匹配）`by_weather[当前weather]`。

### 草稿 ② 门/出口的条件规则（"夜里城门关闭"，Nature↔门）

```yaml
rooms:
  - id: yangzhou_beimen
    short: 扬州北门
    exits:
      north:
        target: suburb_road1
        door:
          name: 城门
          # 条件开放规则：满足条件时此出口可通行，否则被阻拦并给文案
          # 表达式求值时查 Nature（phase 谓词）+ 玩家属性
          open_when: "nature.phase in (day, morning, afternoon) or player.is_guard"
          closed_msg: "城门已关，要等天亮才能出城。\n"
```

引擎行为：`go north` 时求值 `open_when` 表达式 -> false 则返回 `closed_msg` 并阻断移动。表达式引擎统一调条件求值器，门系统不直接 import Nature。

### 草稿 ③ 通用条件判定（"当下是夜晚且在下雨"作为可查询条件，Nature↔条件规则）

这是地基层 DSL，不是某个房间的字段，而是**可被任意系统引用的条件表达式语法**：

```yaml
# 一个独立定义、可被门/物品/NPC 复用的条件谓词库
conditions:
  is_nighttime:
    expr: "nature.phase in (night, midnight, dawn)"
  is_rainy_night:
    expr: "is_nighttime and nature.weather == rain"
  is_dawn:
    expr: "nature.phase == dawn"

# 物品行为引用条件（类比 LPC muding.c 的 event_dawn 判断）
items:
  - id: shenmu_wangding
    on_put_incense:
      # condition + effect：满足条件走 A 分支，否则走 B
      - when: "is_dawn"
        then: trigger_bingcan_event
      - default: trigger_open_up
```

引擎行为：条件求值器把 `nature.phase` / `nature.weather` 解析为对 NatureState 的查询；命名条件（`is_nighttime`）可被其他表达式引用。**这一层是把 LPC 散落的字符串 `if` 收敛为声明式表达式的关键**。

### 草稿 ④ Nature 事件触发器（"日出时向所有户外玩家推送文案"，Nature↔事件）

```yaml
# Nature 时辰配置里直接挂事件钩子（对应 LPC day_phase 的 event_fun 字段）
nature:
  phases:
    - name: dawn
      length_min: 240
      time_msg: "东方的天空中开始出现一丝微曦。"
      desc_msg: "东方的天空已逐渐发白"
      on_enter:                     # 时辰切换时触发的事件
        - kind: broadcast_outdoor   # 引擎内置事件类型：广播给所有户外玩家
          msg: "东方的天空中开始出现一丝微曦。"
        - kind: trigger_save         # 类比 LPC event_sunrise 自动存档
    - name: sunrise
      length_min: 120
      time_msg: "太阳从东方的地平线升起了。"
      on_enter:
        - kind: broadcast_outdoor
          msg: "太阳从东方的地平线升起了。"
```

引擎行为：TickLoop 推进到时辰边界时，Nature 系统读 `on_enter` 列表，逐个派发事件（`broadcast_outdoor` 走命令/广播层给户外玩家发文案，`trigger_save` 走 save.py）。这是把 LPC `call_other(this_object(), event_fun)` 的硬编码函数调用，改为**数据驱动的事件类型 + YAML 声明**，新引擎不要求 UGC 写 Python 函数即可定义时辰事件（受限 Python 钩子作为 `kind: script` 的高级逃生口预留）。

---

## 关键文件路径（供后续 ticket 落地参考）

- LPC 自然守护进程：`/Users/gukt/github/xkx2001-utf8/adm/daemons/natured.c`
- 时辰配置：`/Users/gukt/github/xkx2001-utf8/adm/etc/nature/day_phase`
- 房间基类（门系统）：`/Users/gukt/github/xkx2001-utf8/inherit/room/room.c`
- look 命令（文案拼接入口）：`/Users/gukt/github/xkx2001-utf8/cmds/std/look.c`
- go 命令：`/Users/gukt/github/xkx2001-utf8/cmds/std/go.c`
- sleep 命令（条件判定真实案例）：`/Users/gukt/github/xkx2001-utf8/cmds/std/sleep.c`
- 重阳宫大门（门 + Nature 取用但未用于门控）：`/Users/gukt/github/xkx2001-utf8/d/zhongnan/gate.c`
- 神木王鼎（物品条件判定真实案例 event_dawn）：`/Users/gukt/github/xkx2001-utf8/d/xingxiu/muding.c`
- 新引擎 TickLoop（Nature 推进挂载点）：`/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/tick.py`
- 新引擎组件（Description 待加 outdoors）：`/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/components.py`
- 新引擎 look 命令（文案拼接落点）：`/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/commands.py`
- 旧架构拆解文档：`docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/02-守护进程系统.md`（NATURE_D 章节）、`05-世界构建系统.md`（5.2 环境与天气）、`08-世界观与文案.md`

## 一句话总结给决策

LPC Nature 系统的实际功能远比文档描述窄（只有时辰 + 自动存档，天气是半成品、季节/随机事件不存在），其最有价值的设计是「全局单例 + 被动查询 + 时辰切换广播」架构，以及散落在各处的「字符串比较条件判定」反例。新引擎 M1 应做**时辰循环 + 文案动态拼接 + 通用条件表达式求值器 + 时辰切换广播**这四件必做项，天气只做晴雨骨架，门随天气/NPC 作息/天气影响/随机事件全部依赖未引入系统而推迟 M2+。条件表达式求值器是四件里最该做对的，因为它是门/物品/NPC 三类动态规则的共同地基。
