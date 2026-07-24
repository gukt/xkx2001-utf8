# 红队性能风险挑战：世界空间层

> 角色：性能与可扩展性专家（红队 / 挑战者）。
> 挑战对象：`03-engine-insights/performance-review.md`（以下简称 PR）+ `06-engine-critique/engine-comparison.md`（以下简称 EC）的性能相关结论。
> 证据规则：每条质疑引用被质疑文件与段落，并给出一手源码证据（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号）。禁止凭空推断。
> 约束基准（与 PR 同）：单机 1000 在线 + 100 并发（CLAUDE.md 架构不变量第 1 条 / ADR-0009）。

---

## 0. 总体判定

PR 与 EC 做了扎实的逐模块开销盘点，但在**方法论**与**量级估计**上存在系统性偏差，导致风险优先级排错：

1. **方法论盲区（最严重）**：PR 全篇以「1000 在线 + 100 并发」为基准评估 engine 代码，但 engine 当前是**单玩家 stdin REPL，无任何网络层**。所有「1000 在线」分析都是假想场景，而 PR 没有标注这一点，导致读者误以为这些是当前可验证的风险。
2. **Nature 广播开销被高估**：PR §2.2 称「100 并发下每秒最多 100 次广播扫描」，但 tick 是命令驱动（`cli.py:53` 每命令推进 1 tick），单玩家不可能每秒 100 命令。实际广播频率远低于 PR 估计。
3. **存档开销被错误归因**：PR §5 把 fsync 瓶颈归到「1000 在线」场景，但真正的问题是 `DEFAULT_SAVE_INTERVAL = 10`（`tick.py:39`）--**每 10 条命令全量 fsync 一次**，这在当前单玩家 MVP 下就已经影响体验，无需等到 1000 在线。
4. **`entities_in_room` N² 风险被误置**：PR §6.1 称「1000 玩家并发时 N² 级风险」，但当前架构无并发，N² 不存在。真正的隐藏成本是 `entities_with` 每次调用都构造新 `set`（`world.py:214`），这个成本在单玩家下就存在。
5. **call_out/tick 模型差异的影响被低估**：PR §4.2/§7.2 正确指出「engine 是命令驱动，LPC 是墙钟驱动」，但只归到「玩家船」问题。实际上 Nature 本身受影响：玩家不输入命令，昼夜不推进。`modern-design-review.md §3.1` 称「24 分钟昼夜循环」对 engine 是错的。
6. **ON_TICK 扇出未量化**：PR 没有提到每条命令同步触发 6 个 `ON_TICK` 订阅者（nature / ferry / ai / combat_system / room_hooks / death_flow），这是隐藏的每命令固定开销。

---

## 1. 方法论盲区：engine 是单玩家 stdin REPL，PR 以「1000 在线」评估是空中楼阁

### 1.1 被质疑内容

- PR §0 评审结论速览表列「1000 在线下是否达标」列。
- PR §1.2「1000 在线下评估」段落。
- PR §2.1「1000 在线下评估」段落。
- PR §5.1「1000 在线下评估」段落。
- PR §6.1「1000 在线下存档阻塞数十秒」。

### 1.2 质疑

PR 全篇以 CLAUDE.md 的「单机 1000 在线 + 100 并发」为约束基准评估 engine 代码，但**engine 当前根本无法承载 2 个并发玩家**。证据：

- `engine/src/openmud/cli.py:45-53`：主循环是 `while not world.should_quit: line = input_stream.readline(); ... tick_loop.advance()`--**单线程、阻塞读 stdin、一次一条命令**。无 `socket` / `asyncio` / `threading` / `multiprocessing` / `websocket`（grep `engine/src/openmud/` 全空）。
- `engine/src/openmud/world.py:112`：`self.primary_player_id: EntityId | None = None`--**单一主玩家**。
- `engine/src/openmud/world.py:142-152`：`spawn_player_session` 注释明写「**测试/脚本假多人 seam**」「**单玩家 CLI 仍只驱动主会话**」。
- `engine/src/openmud/__main__.py:184-185`：`TickLoop(lambda: save_world(...), world=world)` + `run_repl(world, player_id, ...)`--启动一个 REPL，不是一个服务器。

### 1.3 影响

PR 的「1000 在线评估」全部是**假想场景**，无法在当前 engine 上验证。更严重的是，PR 把这些假想场景的风险排在了「当前 MVP 就存在的真实问题」前面：

- PR §0 速览表把 `save_world` 标为「高风险（1000 在线时阻塞数十秒）」，但 `DEFAULT_SAVE_INTERVAL = 10`（`tick.py:39`）意味着**每 10 条命令就触发一次全量 fsync**。在单玩家 MVP 下，玩家每输入 10 条命令就卡一次。这个风险不需要 1000 在线就已经存在，但 PR 把它框在了「1000 在线」场景里。
- PR §0 速览表把 Nature 广播标为「高（每相位切换扫全部在线玩家）」，但单玩家下 `_outdoor_player_ids` 返回最多 1 个元素，开销可忽略。

### 1.4 量级估计

| PR 的「1000 在线」风险 | 当前单玩家实际 | 差距 |
|---|---|---|
| Nature 广播扫 1000 玩家 | 扫 1 玩家 | 1000× 高估 |
| event_sunrise 存档 1000 玩家 ×2 = 2000 次 save | save_world 每 10 命令全量存档（含房间+NPC+物品） | 场景错位 |
| entities_in_room N²（1000 玩家并发命令） | N=1，无并发 | N² 不存在 |

**裁决**：PR 应明确分两层评估：①当前单玩家 MVP 的真实性能风险（可验证）；②未来加网络层后的可扩展性风险（需 ADR）。当前混在一起，导致风险优先级排错。

---

## 2. Nature 全员广播开销被高估：tick 是命令驱动，不是墙钟

### 2.1 被质疑内容

- PR §2.2 engine 隐患 #2：「天气翻转概率 `DEFAULT_WEATHER_CHANGE_CHANCE = 0.1`（`nature.py:133`）--每 tick 10% 概率翻转天气...100 并发下每秒最多 100 次广播扫描，**勉强可接受**」。
- PR §0 速览表 Nature 行：「高（每相位切换 `message("outdoor:vision", msg, users())` 扫全部在线玩家）」。
- PR §6.2 #6：「`NatureState.advance_tick` 每 tick 调用...100 并发下每秒 100 次 advance_tick」。

### 2.2 质疑

**PR 的「100 并发下每秒 100 次」假设了 1 tick = 1 命令 = 1 秒，且 100 个玩家各自每秒输入 1 条命令。** 这在当前 engine 架构下不可能发生：

1. **tick 是命令驱动，非墙钟驱动**：`cli.py:53` `tick_loop.advance()` 在每条命令**处理后**调用一次。`tick.py:80-85` `advance()` 先 `self._tick += 1`，再 `dispatch(ON_TICK)`，再按 `% interval` 触发存档。**玩家不输入命令，tick 不推进，Nature 不前进**。
2. **单线程串行**：`cli.py:47` `line = input_stream.readline()` 是阻塞读。同一时刻只有一条命令在处理。即使未来加网络层，如果保持单进程单 World（ADR-0009），命令也是串行排队处理，不存在「100 并发同时 advance_tick」。
3. **单玩家命令速率**：人类打字约 5-10 条命令/秒（极限），实际游玩约 1-3 条/秒。`advance_tick` 每次调用的实际频率是 ~1-3 次/秒，不是 100 次/秒。

### 2.3 实际开销估计

`_broadcast_nature_change`（`nature.py:517-535`）只在相位或天气变化时触发。频率：

- **相位变化**：默认 4 相（dawn 240 / day 720 / dusk 240 / night 240，`nature.py:83-112`），最短相 240 tick = 240 条命令。即**每 240 条命令才触发一次相位广播**。单玩家约每 1-2 分钟一次。
- **天气变化**：10%/tick（`nature.py:133`），平均每 10 条命令翻转一次。翻转时触发 `_broadcast_nature_change`。约每 10 条命令一次。
- **单玩家下 `_outdoor_player_ids`**（`nature.py:502-514`）：`entities_with(PlayerSession, Position)` 返回 1 个实体，`get_component(room, Description)` 查 1 次。**总成本 O(1)**。

### 2.4 PR 漏掉的真实风险

PR 没有量化的隐藏成本：`entities_with`（`world.py:210-215`）**每次调用都构造新 set**：

```python
matching_sets = [set(self._components.get(t, {})) for t in component_types]
return iter(set.intersection(*matching_sets))
```

`set(self._components.get(t, {}))` 从 dict keys 构造新 set。`_outdoor_player_ids` 调 `entities_with(PlayerSession, Position)` 构造 2 个 set + 求交。即使只有 1 个玩家，也要构造 2 个 set。这个成本在单玩家下可忽略，但**如果未来加到 1000 玩家，每次广播构造 2 个 1000 元素 set + 求交**，这才是 PR 应该量化的。

**裁决**：PR 的「100 并发下每秒 100 次广播扫描」量级错误。单玩家下 Nature 广播开销可忽略。PR 应改为评估「`entities_with` 每次 set 构造」的隐藏成本，以及「未来网络层加墙钟 tick 后广播频率变化」的场景。

---

## 3. 存档开销被错误归因：不是「1000 在线」问题，是「每 10 命令」问题

### 3.1 被质疑内容

- PR §0 速览表持久化行：「**高**（save_world 全量每实体一文件 JSON + fsync）...1000 玩家在线时**同步 save 阻塞主循环**，是最大性能隐患」。
- PR §5.1：「每日 sunrise 同步双存档 1000 玩家 = 2000 次 `save()`...**这是原版最大性能瓶颈**」。
- PR §5.2：「1000 在线下存档一次可能阻塞数十秒」。
- PR §6.1 #1：「1000 在线下全量 fsync 不可接受」。

### 3.2 质疑

PR 把存档瓶颈归到「1000 在线」场景，但 engine 的存档触发机制与 LPC 完全不同，**风险在当前单玩家 MVP 下就已经存在**：

1. **engine 存档频率 = 每 10 条命令**：`tick.py:39` `DEFAULT_SAVE_INTERVAL = 10`，`tick.py:84-85` `if self._tick % self._interval == 0: self._save()`。**每 10 条命令触发一次 `save_world`**。对比 LPC `event_sunrise` 每天（24 真实分钟）存一次。engine 存档频率是 LPC 的 **~144 倍**（10 命令 vs 1440 命令/天）。
2. **engine 全量存所有实体**：`save.py:370-372` `for entity_id in sorted(world.all_entities()): _write_json_atomic(...)`。每个实体一个 JSON 文件 + `os.fsync`（`save.py:536`）。LPC 只存玩家（房间靠 `reset` 重建，`room.c:15` `static mapping doors` 不进存档）。engine 存的实体数 >> LPC。
3. **MVP 场景实体数估计**：MVP 场景清单（华山村 + 扬州子集 + 少林 + 官道，CLAUDE.md 架构不变量 7）约 < 500 房间。每房间 1 实体 + 挂 `Identity`/`Description`/`Exits`/`Container` 等组件。加 NPC + 物品，保守估计 **1000-3000 实体**。每 10 条命令，3000 次 `os.fsync`。SSD 每次 fsync ~0.1-1ms，**3000 × 0.5ms = 1.5 秒**。即**玩家每输入 10 条命令就卡 1-2 秒**。

### 3.3 PR 的量级错误

| 维度 | PR 估计 | 实际 |
|---|---|---|
| 触发频率 | LPC 每天 1 次（sunrise） | engine 每 10 条命令 1 次 |
| 存档对象 | 1000 玩家 ×2 save | 全部实体（房间+NPC+物品+玩家） |
| 阻塞场景 | 1000 在线时数十秒 | 单玩家 MVP 下每 10 命令卡 1-2 秒 |
| 瓶颈来源 | LPC event_sunrise | engine DEFAULT_SAVE_INTERVAL + 全量 fsync |

PR 把引擎存档问题与 LPC `event_sunrise` 类比（§5.1），但两者触发频率差 144 倍。PR §7.1 甚至建议「存档与相位切换解耦」，但 engine **已经解耦了**（存档走 `TickLoop` 每 10 tick，不走 Nature 相位）--PR 的建议基于对 engine 现状的误读。

### 3.4 量级估计

- MVP 3000 实体 × `os.fsync` ~0.5ms = **1.5 秒/次存档**。
- 每 10 条命令触发 → **玩家感知：每 10 步卡 1.5 秒**。
- 如果 UGC 题材包做大到 6414 房间（PR §1.3 场景），实体数可达 **~10000+**，存档阻塞 **~5 秒/10 命令**。

**裁决**：PR 应把存档风险从「1000 在线场景」重新定位为「当前单玩家 MVP 的首要性能风险」。根因是 `DEFAULT_SAVE_INTERVAL = 10`（太频繁）+ `_write_json_atomic` 每实体 `os.fsync`（太细粒度）+ 全量存所有实体（太宽）。

---

## 4. `entities_in_room` N² 风险被误置：当前无并发，隐藏成本是 set 构造

### 4.1 被质疑内容

- PR §1.3 engine 隐患 #1：「`entities_in_room` 无反向索引--`commands.py`（行 363、1627、1674、1710、1761、1774）、`parsing.py`（615、628、645）、`messaging.py`（62）、`quest.py`（170）、`combat_system.py`（297）、`room_hooks.py`（468、546）、`ai.py`（249）共 15+ 处调用，**每个命令路径至少一次全表扫**。1000 玩家并发时这是 N² 级风险（每玩家每命令 O(N)）」。
- PR §6.1 #2：「1000 在线下 N² 风险」。

### 4.2 质疑

**「1000 玩家并发时 N²」在当前架构下不存在**：

1. **无并发**：`cli.py:47` 单线程阻塞读 stdin，同时只有 1 条命令在处理。不存在「1000 玩家并发命令」。
2. **单玩家 N=1**：`entities_with(Position)` 返回玩家 1 + 房间内 NPC。MVP 单房间 NPC 通常 < 10。`entities_in_room` 成本 O(1 + NPC) ≈ O(10)。
3. **PR 的 N² 公式**：「每玩家每命令 O(N) × 1000 玩家 = N²」。但单玩家下是 O(N) × 1 = O(N)。即使未来加网络层且保持单进程单 World（ADR-0009），命令也是串行排队，仍是 O(N) × 串行命令数，不是 N²。

### 4.3 PR 漏掉的真实隐藏成本

PR 说「全表扫」但没有精确量化 `entities_with` 的实现（`world.py:210-215`）：

```python
matching_sets = [set(self._components.get(t, {})) for t in component_types]
return iter(set.intersection(*matching_sets))
```

**每次调用都从 dict keys 构造新 set + 求交**。`entities_in_room`（`world.py:227-232`）内部调 `entities_with(Position)`，即每次 `entities_in_room` 调用：

1. 构造 1 个 set（全部 Position 实体的 id 集合）-- O(P)，P = 全部有 Position 的实体数（所有玩家 + 所有 NPC）
2. 遍历 set，逐个 `require_component(entity, Position).room != room` -- O(P)

在单玩家 + 500 NPC 的 MVP 下，P ≈ 501。15 处调用 × 501 = ~7500 次操作/命令。这在单玩家下**可忽略**，但 PR 没有给出这个量级。

**如果未来加到 1000 玩家 + 1000 NPC**，P ≈ 2000。15 处 × 2000 = 30000 次/命令。关键是 **set 构造本身是 O(P)**，不是 O(1)。PR 只说「全表扫」没说「每次构造新 set」，低估了反模式严重度。

### 4.4 量级估计

| 场景 | P（Position 实体数） | entities_in_room 成本/次 | 15 处调用/命令 |
|---|---|---|---|
| 单玩家 MVP（1 玩家 + 500 NPC） | ~501 | ~1000 op | ~15000 op |
| 1000 在线（1000 玩家 + 1000 NPC） | ~2000 | ~4000 op | ~60000 op |
| 6414 房间全图 NPC | ~5000+ | ~10000 op | ~150000 op |

**裁决**：N² 风险对当前架构不适用。PR 应改为评估「`entities_with` 每次 set 构造的 O(P) 成本」+「反向索引在单玩家下也有收益（消除 set 构造）」。

---

## 5. call_out/tick 模型差异：Nature 在 idle 时不推进，「24 分钟昼夜循环」是错的

### 5.1 被质疑内容

- PR §4.2：「LPC 的 call_out 是墙钟驱动，engine 是命令驱动--**这是根本性差异**」。
- PR §7.2：「玩家船在 engine 下要么「玩家不输入就不动」（破坏 LPC 体验），要么引入独立墙钟定时器」。
- `03-engine-insights/modern-design-review.md §3.1`：「一个完整昼夜循环 = 1440 真实秒 = 24 真实分钟」。
- PR §0 速览表 call_out 密度行：「达标」。

### 5.2 质疑

PR 正确识别了墙钟 vs 命令驱动差异，但**低估了影响范围**。PR 只把它归到「玩家船」问题（§7.2），实际上 **Nature 本身、渡船、AI 补刷都受影响**：

1. **Nature 昼夜在 idle 时不推进**：`nature.py:279-318` `advance_tick` 只在 `ON_TICK` 分发时调用。`ON_TICK` 只在 `tick_loop.advance()`（`tick.py:83`）时分发。`tick_loop.advance()` 只在 `cli.py:53` 每条命令后调用。**玩家站着不动（不输入命令），游戏时间完全冻结**。LPC 的 `call_out("update_day_phase", length)`（`natured.c:69`）是墙钟驱动，玩家 idle 时昼夜照常推进。
2. **`modern-design-review.md §3.1` 的「24 分钟昼夜循环」对 engine 是错的**：该文称「1 真实秒 = 1 游戏分钟...一个完整昼夜循环 = 1440 真实秒 = 24 真实分钟」。这引用的是 LPC 的 `TIME_TICK = time()*60`（`natured.c:6`）。但 engine 的 `game_minutes_per_tick = 1`（`nature.py:148`）是 **1 tick = 1 游戏分钟**，不是 1 秒 = 1 分钟。engine 的 1440 游戏分钟 = 1440 tick = **1440 条命令**，不是 1440 秒。单玩家 3 命令/秒时 ≈ 8 分钟；玩家 idle 时 = 永不完成。
3. **渡船在 idle 时不翻转**：`ferry.py:102-113` `_on_ferry_tick` 在 `ON_TICK` 时递减 `ticks_until_flip`。玩家 idle 时渡船冻结。LPC `ferry.c:90` `call_out("on_board", 15)` 是 15 秒墙钟，玩家 idle 时渡船照常走。
4. **AI 补扫在 idle 时不运行**：`ai.py:153` `_on_ai_tick` 挂 `ON_TICK`。玩家 idle 时 NPC 不补刷。LPC 的 NPC `heart_beat` 是墙钟驱动。
5. **PR §0 速览表把 call_out 密度标为「达标」**：这掩盖了「idle 时世界冻结」的体验风险。

### 5.3 量级估计

| 子系统 | LPC（墙钟） | engine（命令驱动） | 差异 |
|---|---|---|---|
| Nature 昼夜推进 | 1 秒 = 1 游戏分钟，idle 照常 | 1 命令 = 1 游戏分钟，idle 冻结 | idle 时无昼夜 |
| 渡船翻转 | 15-20 秒 call_out，idle 照常 | 15-20 tick = 15-20 命令，idle 冻结 | idle 时渡船不走 |
| NPC 补刷 | heart_beat 墙钟 | spawn_scan_interval tick，idle 冻结 | idle 时 NPC 不补 |
| 玩家船 navigate | 每 2 秒 call_out | 无实现（若实现也挂 tick） | idle 时船不走 |

**裁决**：PR 应把 call_out/tick 模型差异从「玩家船问题」提升为「整个时序架构差异」。当前 engine 是「世界只在玩家行动时才演化」，与 LPC「世界独立于玩家演化」是根本不同的世界感。这不是性能问题，是架构问题，但直接影响性能评估的基准（tick 频率 = 玩家命令频率，不是墙钟）。

---

## 6. ON_TICK 扇出：每条命令同步触发 6 个订阅者，PR 未量化

### 6.1 被质疑内容

- PR §4.2：「单一 `on_tick` 事件，`TickLoop.advance` 串行分发所有订阅者（nature / ferry / ai / combat / room_hooks）」。
- PR §6.3 低风险 #7-10 只列了 ferry / crossing / components_of / EventBus.register，**没有量化 ON_TICK 扇出总数**。

### 6.2 质疑

PR 提到了 5 个订阅者但漏了 `death_flow`，且没有量化总扇出成本。实际 grep `ON_TICK` 注册点：

| 订阅者 | 注册点 | 每 tick 做什么 |
|---|---|---|
| nature | `nature.py:444` | `advance_tick` → 可能触发 `ON_NATURE_CHANGE` → `_broadcast_nature_change` → `_outdoor_player_ids`（构造 2 个 set + 遍历玩家） |
| ferry | `ferry.py:48` | `_on_ferry_tick` → 遍历全部 crossings 递减计数 |
| ai | `ai.py:153` | `_on_ai_tick` → 低频 spawn_scan（每 N tick 一次扫全部蓝图） |
| combat_system | `combat_system.py:86` | `_on_combat_tick` → 战斗回合推进 |
| room_hooks | `room_hooks.py:701` | `_on_tick` → 机关钩子推进 |
| death_flow | `death_flow.py:413` | `_on_unconscious_tick` → 昏迷苏醒计时 |

**6 个订阅者同步串行执行**（`events.py:70-71` `for handler in self.handlers_for(event_name): handler(*args, **kwargs)`）。每条命令都要跑完这 6 个 handler 才返回给玩家。

### 6.3 量级估计

每条命令的 ON_TICK 固定开销（不含命令本身的 entities_in_room 调用）：

- nature `advance_tick`：O(1) 累加 + 可能 O(P) 广播（P = PlayerSession 实体数，单玩家 = 1）
- ferry `_on_ferry_tick`：O(crossings)，MVP 1-2 对渡口 ≈ O(2)
- ai `_on_ai_tick`：O(1) 计数；每 N tick 触发 spawn_scan = O(全部蓝图)
- combat `_on_combat_tick`：O(活跃战斗数)
- room_hooks `_on_tick`：O(房间钩子数)
- death_flow `_on_unconscious_tick`：O(昏迷实体数)

单玩家 MVP 下这些多为 O(1)-O(小常数)，**可忽略**。但 PR 应该量化这个扇出，因为：

1. 未来每加一个 tick 驱动子系统（Effect 衰减、任务计时、CD 冷却），扇出就 +1。
2. 如果引入墙钟 tick（解 §5 的问题），扇出频率从「每命令」变为「每墙钟单位」，成本结构完全不同。

**裁决**：PR 应把 ON_TICK 扇出列为低风险但需监控的指标，而非完全不提。

---

## 7. 交通并发风险：渡船在 engine 下无 yell 触发，idle 时不翻转

### 7.1 被质疑内容

- PR §3.1：「1000 在线下评估：9 个渡口 × 每渡口最多 1 个活跃周期 = 9 个并发 call_out，**完全可忽略**」。
- PR §3.4 engine 隐患 #1-3：「`_on_ferry_tick` 每 tick 遍历 crossings...O(crossings) 可忽略」。
- PR §0 速览表渡船并发行：「低（call_out + 临时 exit，9 处渡口）」。

### 7.2 质疑

PR 的「渡船并发低」结论对 LPC 是对的，但对 engine 的渡船模型描述不完整：

1. **engine 渡船是纯定时翻转，无 yell 触发**：`ferry.py:102-113` `_on_ferry_tick` 每 tick 递减 `ticks_until_flip`，到 0 翻转 `at_bank_a`。**没有 LPC 的 `do_yell` 玩家触发**（`ferry.c:28` `do_yell`）。engine 渡船不管有没有玩家都在定时翻转。
2. **idle 时不翻转**：如 §5 所述，`_on_ferry_tick` 挂 `ON_TICK`，玩家 idle 时 tick 不推进，渡船冻结。PR §3.4 没提这点。
3. **LPC 渡船是按需触发**：`ferry.c:55` `check_trigger()` 只在玩家 `yell` 时启动周期。无玩家时渡船不耗 call_out。engine 渡船不管有没有玩家都在烧 tick。

### 7.3 量级影响

| 维度 | LPC | engine |
|---|---|---|
| 触发 | 玩家 yell（按需） | 定时翻转（无条件） |
| idle 行为 | 不触发（省 call_out） | 冻结（tick 不推进） |
| 翻转频率 | 15+20+20=55 秒（墙钟） | cross_interval tick（命令驱动） |
| 玩家在场判定 | yell 即在场 | 无判定（空房间也翻转） |

engine 的渡船在「无人观看时空翻转」不是性能问题（crossings 数少），但**语义偏差**导致 PR 的「并发低」结论虽然量级对，但遗漏了「engine 渡船模型与 LPC 根本不同」这一事实。EC §5 已指出这是「重大偏差（N4）」，但 PR 没有把这一点纳入性能评估。

**裁决**：渡船并发确实低，PR 量级估计正确。但 PR 应标注「engine 渡船是纯定时翻转，无玩家交互触发，与 LPC 模型不同」，否则读者会误以为 engine 渡船与 LPC 渡船性能特征相同。

---

## 8. 6414 房间全量加载：PR 没有连接到存档成本

### 8.1 被质疑内容

- PR §1.3 engine 隐患 #3：「`scene_loader.load_scene` 一次性 `_build_rooms` 全量建 6414 房间，冷启动加载全图...MVP 场景清单房间数 < 500 暂无压力，但 UGC 题材包做大时**加载时间随房间数线性增长**」。
- PR §6.2 #4：「冷启动加载全部 6414 房间，UGC 大题材包加载慢」。

### 8.2 质疑

PR 把全量加载归为「加载慢」问题，但漏了**更严重的连带效应**：全量加载的每个房间都是一个 entity，都会被 `save_world` 全量 fsync（§3）。

1. **加载 → 存档的乘数效应**：`scene_loader.py:461` `_build_rooms` 为每个房间 `world.create_entity()` + `add_component(Identity)` + `add_component(Description)` + `add_component(Exits)` + `add_component(Container)`。6414 房间 = 6414 entity × 4+ 组件。加 NPC（`_build_npcs`）、物品（`_build_items`），entity 总数轻松破万。
2. **每 10 条命令全量存档全部 entity**：`save.py:370` `for entity_id in sorted(world.all_entities())`。万级 entity × fsync = **每 10 命令卡 5+ 秒**。PR §1.3 说「加载慢」，但没说「加载多 = 存档慢」这条因果链。
3. **PR §7.3 提到懒加载差异但没连到存档**：「LPC 房间懒加载...engine 全量加载（`load_scene` 一次性建全部房间）」。PR 说了「内存随房间数线性增长」，但没说「存档时间随房间数线性增长 × 每 10 命令一次」。

### 8.3 量级估计

| 房间规模 | entity 数估计 | 每 10 命令存档阻塞（fsync ~0.5ms/entity） |
|---|---|---|
| MVP < 500 房间 | ~1000-3000 | ~0.5-1.5 秒 |
| 6414 房间全图 | ~10000-20000 | ~5-10 秒 |
| UGC 大题材包 10000+ 房间 | ~20000-40000 | ~10-20 秒 |

**裁决**：PR 应把「全量加载」与「全量存档」连成一条风险链：加载越多 → entity 越多 → 每 10 命令存档越慢。当前分开放在 §1.3 和 §5，读者看不到因果关联。

---

## 9. 玩家船 navigate 并发：PR 的「每船每 2s O(17) 扫描」基于 LPC call_out，engine 无法复刻

### 9.1 被质疑内容

- PR §3.2：「每船 navigate 每 2 秒一次 O(10 暗礁 + 3 岛屿 + 4 港口) = O(17) 线性扫，3 船 = 每秒 ~25 次线性扫，**可忽略**」。
- PR §3.2「致命隐患」：「`do_drop` 翻船时 N 玩家同时 move 到随机港口，瞬时 N 次 call_other + 房间加载」。
- PR §7.2：「玩家船 navigate 是墙钟 call_out 每 2 秒一次...engine 单 on_tick 模型是命令驱动...玩家船在 engine 下要么「玩家不输入就不动」」。

### 9.2 质疑

PR 的玩家船性能分析全部基于 LPC `call_out` 模型，但 engine **没有玩家船模块**（EC §10 N1），且 engine 的 tick 模型无法复刻 `call_out`（§5）。PR §3.2 的「每船每 2s O(17)」分析对 engine 不适用：

1. **engine 无 ship 模块**：grep `ship|navigate|lookout|harbor|island` 在 `engine/src/openmud/` 空结果（EC §10）。PR 分析的 ship 性能特征是 LPC 的，不是 engine 的。
2. **若按 engine tick 模型实现，navigate 频率 ≠ 2 秒**：LPC `ship.c:106` `call_out("navigate", 2)` 是 2 秒墙钟。engine 若挂 `ON_TICK`，频率 = 命令频率（~1-3/秒），且 idle 时冻结。PR §3.2 的「每秒 ~25 次线性扫」假设了 2 秒墙钟周期，对 engine 不成立。
3. **PR §3.2 的「致命隐患 do_drop」对 engine 不存在**：engine 无 ship，无 `do_drop`。PR 分析的是 LPC 的风险，不是 engine 的风险。

### 9.3 裁决

PR 应明确标注：玩家船性能分析（§3.2）是 **LPC 原版的风险评估**，engine 由于无 ship 模块，这些风险当前不存在。若未来实现 ship，需基于 engine tick 模型重新评估，不能直接套用 LPC call_out 的「每 2 秒」频率。

---

## 10. PR 结论中「达标」判定过于乐观

### 10.1 被质疑内容

- PR §0 速览表：大世界拓扑查询「达标但需建索引」、渡船并发「达标」、call_out 密度「达标」。
- PR §8 给后续 engine 设计的性能输入：6 条建议方向。

### 10.2 质疑

PR 的「达标」判定基于「1000 在线」假想场景的量级估计，但如 §1 所述，engine 是单玩家 REPL。在当前架构下：

1. **「大世界拓扑查询达标」**：单玩家下 O(500) 全表扫确实达标，但 PR 的「需建索引」建议是给 1000 在线准备的。当前不需要。
2. **「渡船并发达标」**：渡船 crossings 数少，单玩家下确实达标。但 engine 渡船无 yell 触发（§7），语义偏差未纳入「达标」判定。
3. **「call_out 密度达标」**：engine 无 call_out，用 ON_TICK。6 个订阅者扇出（§6）未量化，标「达标」过早。
4. **持久化标「高风险」但归因错误**（§3）：标了高风险但归到「1000 在线」，实际是「每 10 命令」。

### 10.3 裁决

PR 应把 §0 速览表拆为两列：「当前单玩家 MVP 是否达标」+「未来 1000 在线是否达标」。当前混为一列，导致「达标」判定过于乐观（因为用单玩家的低负载通过了「1000 在线」标准的量级估计）。

---

## 11. 修正后的风险优先级（红队建议）

基于上述质疑，建议把 PR 的风险优先级重排为：

| 优先级 | 风险 | 影响场景 | 根因 |
|---|---|---|---|
| **P0** | save_world 每 10 命令全量 fsync | 当前单玩家 MVP | `DEFAULT_SAVE_INTERVAL=10` + 每实体 fsync + 全量存 |
| **P0** | tick 命令驱动导致 idle 时世界冻结 | 当前单玩家 MVP | `cli.py:53` 每命令 1 tick，无墙钟 |
| **P1** | 全量加载 → entity 多 → 存档乘数效应 | 当前 MVP + UGC 扩展 | `scene_loader` 全量建图 × `save_world` 全量存 |
| **P1** | `entities_with` 每次构造 set | 当前单玩家（可忽略）→ 未来扩展（累积） | `world.py:214` `set(dict.keys())` |
| **P2** | Nature 广播 `_outdoor_player_ids` 全扫 | 未来 1000 在线 | `nature.py:509` 无缓存户外玩家集合 |
| **P2** | ON_TICK 6 订阅者扇出 | 当前（可忽略）→ 未来扩展 | `events.py:70` 同步串行 |
| **P3** | 玩家船 navigate 性能 | 未来（engine 无 ship） | LPC call_out 模型不可复刻 |

---

## 附录：证据索引

### engine 模块

| 文件 | 关键位置 | 用途 |
|---|---|---|
| `engine/src/openmud/cli.py` | `run_repl` L45-53（`while not world.should_quit: line = input_stream.readline(); ... tick_loop.advance()`） | 单玩家 stdin REPL 主循环 |
| `engine/src/openmud/__main__.py` | L184-185（`TickLoop(...) ` + `run_repl`） | 启动入口，无网络层 |
| `engine/src/openmud/world.py` | `primary_player_id` L112 / `spawn_player_session` L142-152 / `entities_with` L210-215（`set(dict.keys())` + `set.intersection`）/ `entities_in_room` L217-232 | 单玩家模型 + ECS 查询实现 |
| `engine/src/openmud/tick.py` | `DEFAULT_SAVE_INTERVAL=10` L39 / `advance` L73-85（每 tick dispatch ON_TICK + 每 10 tick save） | tick 驱动模型 + 存档频率 |
| `engine/src/openmud/nature.py` | `advance_tick` L279-318 / `_outdoor_player_ids` L502-514 / `_broadcast_nature_change` L517-535 / `DEFAULT_WEATHER_CHANGE_CHANCE=0.1` L133 / `attach_nature` L398-449 | Nature tick 驱动 + 广播 |
| `engine/src/openmud/save.py` | `save_world` L351-385（`for entity_id in sorted(world.all_entities())` 每实体写 JSON）/ `_write_json_atomic` L526-537（`os.fsync` L536） | 全量每实体 fsync 存档 |
| `engine/src/openmud/ferry.py` | `_on_ferry_tick` L102-113 / `_apply_crossing_exits` L123-132 | 渡船纯定时翻转，无 yell |
| `engine/src/openmud/events.py` | `dispatch` L63-71（同步串行 `for handler in handlers_for: handler(...)`） | ON_TICK 同步扇出 |
| `engine/src/openmud/scene_loader.py` | `_build_rooms` L461-492 | 全量建图 |
| ON_TICK 订阅者注册点 | nature L444 / ferry L48 / ai L153 / combat_system L86 / room_hooks L701 / death_flow L413 | 6 个同步 tick 订阅者 |

### LPC 一手源码

| 文件 | 关键位置 | 用途 |
|---|---|---|
| `adm/daemons/natured.c` | `update_day_phase` L54-77 / `message("outdoor:vision", msg, users())` L71 / `event_sunrise` L83-97（遍历 users() 双存档）/ `event_common` L100-142（`livings()` 全扫 + `inventory_check` 全玩家）/ `call_out("update_day_phase", length)` L69 | LPC 墙钟驱动 Nature + 全员广播 + 全量存档 |
| `inherit/room/ferry.c` | `do_yell` L28 / `check_trigger` L55 / `call_out("on_board", 15)` L90 / `call_out("arrive", 20)` L111 / `call_out("close_passage", 20)` L138 | LPC 渡船玩家触发 + 墙钟周期 |
| `inherit/room/ship.c` | `call_out("navigate", 2)` L106/279 / `navigate` L112-282 / `do_drop` L513-537 / `call_out("time_out", 900+random(500))` L46 | LPC 玩家船墙钟导航 |
| `feature/message.c` | `receive_message` L11-35（`case "outdoor": if(!environment()->query("outdoors")) return;` L25-27） | LPC 户外过滤在接收端 |

### 被质疑的 Phase 1 文件

| 文件 | 被质疑段落 |
|---|---|
| `03-engine-insights/performance-review.md` | §0 速览表 / §1.2-1.3 / §2.1-2.2 / §3.1-3.4 / §4.2 / §5.1-5.2 / §6.1-6.3 / §7.1-7.4 / §8 |
| `03-engine-insights/modern-design-review.md` | §3.1「24 分钟昼夜循环」 |
| `06-engine-critique/engine-comparison.md` | §5（ferry 偏差 N4）/ §10（ship 遗漏 N1） |
