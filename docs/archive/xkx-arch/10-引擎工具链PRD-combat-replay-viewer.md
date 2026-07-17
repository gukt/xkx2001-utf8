# 引擎工具链 PRD：Combat Replay Viewer（战斗回放查看器）

> 创建日期：2026-07-11
> 阶段：0 引擎工具链 PRD（最小三件之三）
> 关联：[04](04-迁移路径与避坑清单.md) §二 M1 / §三阶段 1 范围检查点 6 / §五范围检查点 10 / [ADR-0002](../docs/adr/ADR-0002-resolve-attack-extraction.md) / [ADR-0011](../docs/adr/ADR-0011-spec-conformance-checker.md) / [ADR-0012](../docs/adr/ADR-0012-performance-microbenchmark.md)

---

## 一、定位与目标

Combat Replay Viewer 是引擎工具链最小三件之一，基于 **CombatContext 快照 + input log + CombatRoundResult ledger** 重放战斗回合，支持逐步回放、快进跳转和确定性 diff，是 combat 确定性的可视化验证工具。

核心定位：

1. **确定性验证工具**：同 seed + 同快照 + 同 input -> 同输出。Replay Viewer 通过重放验证这一不变量，是 [04](04-迁移路径与避坑清单.md) §五范围检查点 6（combat 确定性回放验证）和检查点 10（每阶段 combat replay viewer 验证无回归）的执行载体。
2. **M1 开源资产的前身**：[04](04-迁移路径与避坑清单.md) §二 M1 交付物为"combat 确定性回放引擎开源"，含 CombatContext 快照 + seeded RNG + input log + 输出帧 + 开源仓库。Replay Viewer 的战报归档格式预览是 M1 交付物的直接前身，阶段 1 实现的回放能力将作为 M1 开源仓库的核心组件。
3. **交织不变量可视化**：do_attack 七步管线的文本与副作用交织不可分离（[CLAUDE.md](../CLAUDE.md) 架构不变量），ledger 按 msg/eff 真实调用顺序记录（[ADR-0011](../docs/adr/ADR-0011-spec-conformance-checker.md)）。Replay Viewer 将这一交织时序以人类可读方式呈现，对照 ConformanceChecker 的 8 项检查。

**范围边界**（[04](04-迁移路径与避坑清单.md) §六不做清单）：

- combat 确定性范围 = combat-only（全仿真确定性后置 M3 后）。Replay Viewer 只覆盖 `resolve_attack` 回合级回放，不覆盖 tick 级全仿真。
- 不修改 `resolve_attack` 内核：Replay Viewer 是 ledger 的消费者，非侵入式集成。
- 不做 TUI 交互式回放 / Web 可视化（后置）。

---

## 二、核心功能

### 2.1 战斗回放

| 模式 | 说明 | CLI 选项 |
|---|---|---|
| 逐回合回放 | 从第 1 回合开始，逐回合显示帧内容，等待用户确认后继续 | `replay <log> --step` |
| 快进回放 | 连续输出所有回合帧，不暂停 | `replay <log>` |
| 跳转回合 N | 直接跳到第 N 回合，显示该回合帧 | `replay <log> --round <N>` |
| 范围回放 | 回放第 M 到 N 回合 | `replay <log> --from <M> --to <N>` |

每回合帧（Frame）输出内容：

- **回合编号 + 结果码**：`Round 5 [HIT]` / `Round 3 [DODGE]` / `Round 7 [PARRY]`
- **文本消息**：按 ledger 中 `LEDGER_MESSAGE` 条目的真实顺序输出
- **副作用列表**：按 ledger 中 `LEDGER_EFFECT` 条目的真实顺序输出，每条标注 `kind / target / amount / detail`
- **交织时序视图**：将 ledger 作为一个时间线展示，`[msg]` 和 `[eff]` 交替出现，直观呈现 msg/eff 交织顺序（验证 do_attack 七步交织不变量）
- **状态快照**：该回合 apply effects 后的双方 CombatantSnapshot 关键字段（qi / eff_qi / max_qi / jingli / combat_exp 等）

### 2.2 副作用交织时序展示

这是 Replay Viewer 的核心差异化能力。ledger（`CombatRoundResult.ledger: list[LedgerEntry]`）记录了 `resolve_attack` 内部 `msg()` 和 `eff()` 调用的统一顺序（[result.py](../engine/src/xkx/combat/result.py)），是 do_attack 七步副作用交织不可分离这一不变量的直接物证。

展示格式（示例）：

```
Round 5 [HIT]  damage=42
  ── 交织时序 ──────────────────────────────────
  [0] msg  "张三一招「试探」，攻向李四胸口"
  [1] eff  damage  target=李四  amount=42  detail=击伤
  [2] eff  wound   target=李四  amount=42  detail=击伤
  [3] msg  "李四受到42点击伤。"
  [4] eff  exp     target=张三  amount=1
  [5] eff  exp     target=李四  amount=1
  [6] eff  potential target=李四  amount=1
  [7] eff  jingli  target=张三  amount=-1
  [8] eff  skill_improve  target=张三  amount=1  detail=unarmed
  ─────────────────────────────────────────────
  交织验证: PASS (msg 与 eff 非全分组)
```

对照 [ADR-0011](../docs/adr/ADR-0011-spec-conformance-checker.md) ConformanceChecker 的 8 项检查，回放时自动执行并显示结果：

| 检查项 | 显示 |
|---|---|
| result_code 合法 | PASS / FAIL |
| damage 非负 | PASS / FAIL |
| 非命中时 damage=0 | PASS / FAIL |
| effect target 合法 | PASS / FAIL |
| 命中时有 DAMAGE | PASS / FAIL |
| 闪避/招架无 DAMAGE | PASS / FAIL |
| 三层资源不变量 | PASS / FAIL |
| 交织顺序 | PASS / FAIL |

### 2.3 确定性验证（diff 模式）

输入两份战斗日志（同 seed + 同快照 + 同 input 的两次运行输出），逐回合 diff，定位首次分歧回合。

```
$ replay combat_run_a.json --diff combat_run_b.json

Determinism diff: run_a vs run_b
  Rounds compared: 20
  First divergence: Round 7
    run_a: result_code=HIT  damage=42  messages=3  effects=6
    run_b: result_code=HIT  damage=38  messages=3  effects=6
    Ledger diff:
      [1] eff damage: amount 42 vs 38  <<< DIVERGE
  Result: NON-DETERMINISTIC (diverges at round 7)
```

确定性验证依赖 [ADR-0012](../docs/adr/ADR-0012-performance-microbenchmark.md) 确立的 PYTHONHASHSEED=0 跨进程一致性基础。`resolve_attack` 内部使用 `random.Random(seed)`（非 hash），PYTHONHASHSEED 不应影响输出；diff 模式可跨进程验证此预期。

### 2.4 战报归档格式预览

M1 交付物要求"战报归档格式：CombatContext + input log + 输出帧"（[04](04-迁移路径与避坑清单.md) §二 M1）。Replay Viewer 定义并消费该格式，阶段 1 实现即为 M1 格式前身。

战报归档（CombatLog）结构：

```json
{
  "version": "1",
  "context": {                          // CombatContext 快照
    "attacker": { "entity_id": 1, "name": "张三", ... },
    "victim":   { "entity_id": 2, "name": "李四", ... },
    "seed": 42,
    "attack_type": 0,
    "limbs": ["头部", "胸口", ...]
  },
  "input_log": [                        // input log：逐回合 seed 偏移或 input 变更
    { "round": 1, "seed": 42 },
    { "round": 2, "seed": 43 }
  ],
  "output_frames": [                    // 输出帧：逐回合 CombatRoundResult
    {
      "round": 1,
      "result_code": 0,
      "damage": 42,
      "messages": ["张三一招...", "李四受到42点击伤。"],
      "effects": [ ... ],
      "ledger": [ ... ]
    }
  ]
}
```

Replay Viewer 可从 CombatLog 重放（消费已记录的 output_frames），也可从 CombatContext + input log 实时重放（调用 `resolve_attack` 纯函数重新生成 frames）。后者是确定性验证的核心路径。

---

## 三、接口设计

### 3.1 CLI 命令

```
Usage: python -m xkx.tools.replay <command> [options]

Commands:
  replay <log>                    快进回放所有回合
  replay <log> --step             逐回合回放（每回合暂停等待确认）
  replay <log> --round <N>        跳转到第 N 回合
  replay <log> --from <M> --to <N>  回放第 M 到 N 回合
  replay <log> --diff <other>     对比两份日志，定位首次分歧
  replay <log> --conformance      回放时自动执行 ConformanceChecker 8 项检查
  replay <log> --json             输出 JSON 格式（机器可读，供其他工具消费）

Options:
  --no-snapshot     不显示状态快照（仅消息 + 副作用）
  --ledger-only     仅显示交织时序视图
  --verbose         显示完整 CombatantSnapshot
```

### 3.2 程序化 API

```python
from xkx.tools.replay import ReplayViewer, CombatLog

# 加载战报
log = CombatLog.load("combat_run_a.json")

# 创建 viewer
viewer = ReplayViewer(log)

# 逐回合迭代
for frame in viewer.iter_frames():
    print(frame.render())             # 人类可读帧
    report = frame.check_conformance()  # ConformanceChecker 报告
    if not report.ok:
        print(report.violations)

# 跳转特定回合
frame = viewer.get_round(5)

# 确定性 diff
other = CombatLog.load("combat_run_b.json")
diff = viewer.diff(other)
print(diff.first_divergence)

# 从 CombatContext + input log 实时重放（调用 resolve_attack 纯函数）
from xkx.combat.context import CombatContext
ctx = CombatContext.load("context.json")
frames = viewer.replay_from_context(ctx, seeds=[42, 43, 44, ...])
```

### 3.3 输出格式

默认输出为终端文本（ANSI 着色）。`--json` 选项输出机器可读 JSON，供其他工具（如未来 TUI / Web 可视化）消费。

---

## 四、数据模型

### 4.1 输入

| 数据 | 类型 | 来源 | 说明 |
|---|---|---|---|
| CombatContext 快照 | `CombatContext` ([context.py](../engine/src/xkx/combat/context.py)) | 战斗开始边界一次性拷贝 | 双方 CombatantSnapshot + seed + attack_type + limbs |
| input log | `list[RoundInput]` | 逐回合 seed / input 变更 | 每回合的 seed 偏移或外部输入（attack_type 变更等） |
| CombatRoundResult ledger | `list[LedgerEntry]` ([result.py](../engine/src/xkx/combat/result.py)) | `resolve_attack` 输出 | msg/eff 统一调用顺序，含 `entry_type` / `text` / `effect` |

### 4.2 输出

| 数据 | 类型 | 说明 |
|---|---|---|
| 逐回合帧（Frame） | `ReplayFrame` | 回合编号 + 结果码 + 文本消息 + 副作用列表 + 交织时序 + 状态快照 |
| ConformanceReport | `ConformanceReport` ([conformance.py](../engine/src/xkx/combat/conformance.py)) | 8 项检查结果（passed / skipped / violations） |
| DiffReport | `DiffReport` | 两份日志的逐回合 diff 结果，含首次分歧回合 + 分歧详情 |

### 4.3 数据流

```
                    ┌─────────────────────────────────────┐
                    │         CombatLog (JSON)            │
                    │  ┌─────────┐  ┌────────┐  ┌──────┐ │
                    │  │ Context │  │ Input  │  │Output│ │
                    │  │ Snapshot│  │  Log   │  │Frames│ │
                    │  └────┬────┘  └───┬────┘  └──┬───┘ │
                    └───────┼───────────┼──────────┼─────┘
                            │           │          │
                     ┌──────▼───────────▼──┐       │
                     │  resolve_attack()   │       │
                     │  (纯函数重放)        │       │
                     │  -> CombatRoundResult│      │
                     └──────┬──────────────┘       │
                            │                      │
                     ┌──────▼──────────────────────▼──┐
                     │        ReplayViewer             │
                     │  ┌──────────────────────────┐  │
                     │  │ Frame 渲染（文本/JSON）    │  │
                     │  │ - 消息 + 副作用 + 交织时序  │  │
                     │  │ - 状态快照                │  │
                     │  └──────────────────────────┘  │
                     │  ┌──────────────────────────┐  │
                     │  │ ConformanceChecker (8项)  │  │
                     │  └──────────────────────────┘  │
                     │  ┌──────────────────────────┐  │
                     │  │ Diff (两份日志对比)       │  │
                     │  └──────────────────────────┘  │
                     └────────────────────────────────┘
```

关键数据流说明：

- **离线回放路径**：CombatLog 已含 output_frames -> 直接渲染，不调用 `resolve_attack`。用于回放已记录的战斗。
- **确定性验证路径**：CombatLog 仅含 context + input_log -> 调用 `resolve_attack(ctx)` 重新生成 frames -> 与原 output_frames diff。用于验证确定性。
- **两种路径共享 Frame 渲染 + ConformanceChecker 逻辑**，仅数据来源不同。

---

## 五、与引擎集成点

### 5.1 消费 resolve_attack 的 ledger（非侵入）

Replay Viewer 是 `CombatRoundResult.ledger` 的消费者，不修改 `resolve_attack` 内核。集成方式：

- `resolve_attack(ctx) -> CombatRoundResult`：纯函数，输出含 `ledger: list[LedgerEntry]`
- Replay Viewer 读取 ledger，按 `entry_type` 分发渲染（`LEDGER_MESSAGE` -> 文本 / `LEDGER_EFFECT` -> 副作用行）
- 不需要在 `resolve_attack` 中添加任何 hook / callback / event

### 5.2 可离线回放（脱离引擎运行）

Replay Viewer 可完全脱离引擎运行时运行：

- `resolve_attack` 是纯函数，只依赖 `CombatContext` 输入，不依赖 ECS / 事件循环 / 存储等运行时组件
- CombatLog 以 JSON 序列化，可文件加载
- ConformanceChecker 同样是纯函数（`check_conformance(ctx, result) -> ConformanceReport`），不依赖运行时
- 这使得 Replay Viewer 可作为 M1 开源仓库的独立组件分发，不需要完整引擎依赖

### 5.3 与 ConformanceChecker 联动

回放时自动执行 [ADR-0011](../docs/adr/ADR-0011-spec-conformance-checker.md) ConformanceChecker 的 8 项单次检查：

1. `result_code` 合法
2. `damage` 非负
3. 非命中时 `damage=0`
4. `effect target` 合法
5. 命中时有且仅有一条 `DAMAGE`
6. 闪避/招架无 `DAMAGE`
7. 三层资源不变量（apply effects 后 `0 <= qi <= eff_qi <= max_qi`）
8. 交织顺序（ledger 中 message 与 effect 非全分组）

联动方式：`ReplayFrame.check_conformance()` 内部调用 `check_conformance(ctx, result)`，返回 `ConformanceReport`。`--conformance` CLI 选项在每回合帧后显示检查结果摘要。

### 5.4 战斗日志采集（引擎侧 hook）

引擎运行时需提供日志采集能力（不在本 PRD 范围，但定义接口契约）：

```python
# 引擎侧：战斗开始时记录 context，每回合记录 result
class CombatLogger:
    def log_context(self, ctx: CombatContext) -> None: ...
    def log_round(self, round_num: int, result: CombatRoundResult) -> None: ...
    def dump(self, path: str) -> None: ...  # 写入 CombatLog JSON
```

阶段 1 最小实现可先用测试 fixture 生成 CombatLog（手动构造 `CombatContext` + 调用 `resolve_attack` + 序列化），不需要引擎运行时 hook。

---

## 六、最小实现范围（阶段 1）

| 能力 | 阶段 1 最小版 | 说明 |
|---|---|---|
| CombatLog 格式定义 + 序列化 | ✅ | JSON 格式，`CombatContext` / `CombatRoundResult` 均为 pydantic BaseModel，可直接序列化 |
| 逐回合回放 + 快进 | ✅ | CLI `replay <log>` / `replay <log> --step` |
| 跳转回合 N | ✅ | CLI `replay <log> --round <N>` |
| 交织时序展示 | ✅ | 渲染 ledger 为 `[msg]` / `[eff]` 交替时间线 |
| ConformanceChecker 集成 | ✅ | `--conformance` 选项，每回合显示 8 项检查结果 |
| 确定性 diff | ✅ | CLI `replay <log> --diff <other>`，定位首次分歧回合 |
| 从 context + input log 实时重放 | ✅ | 调用 `resolve_attack` 纯函数重新生成 frames |
| 程序化 API | ✅ | `ReplayViewer` / `CombatLog` / `ReplayFrame` 类 |
| JSON 输出 | ✅ | `--json` 选项 |
| TUI 交互式回放 | ❌ 后置 | 需 curses / textual 依赖，阶段 1 不引入 |
| Web 可视化 | ❌ 后置 | 需前端组件，阶段 1 不引入 |
| 与 tick profiler 集成 | ❌ 后置 | 需阶段 1 tick 框架就绪 |
| 引擎运行时日志采集 hook | ❌ 后置 | 阶段 1 用测试 fixture 生成 CombatLog |

**阶段 1 验收标准**：

- [ ] `CombatLog` JSON 格式定义，可序列化/反序列化 `CombatContext` + `CombatRoundResult`
- [ ] CLI `replay` 命令支持 `--step` / `--round` / `--diff` / `--conformance` / `--json`
- [ ] 交织时序视图正确渲染 ledger 的 msg/eff 交替顺序
- [ ] ConformanceChecker 8 项检查在回放时自动执行，结果正确
- [ ] 确定性 diff 能定位首次分歧回合 + 分歧详情
- [ ] 从 context + input log 实时重放（调用 `resolve_attack`）的结果与原 output_frames 一致
- [ ] 可脱离引擎运行时离线运行（仅依赖 `xkx.combat` 模块）
- [ ] ruff 全过

---

## 七、后置能力

| 能力 | 触发条件 | 说明 |
|---|---|---|
| TUI 交互式回放 | 阶段 1 回放能力验证通过后 | 基于 textual / curses，支持键盘控制逐回合前进/后退/跳转，交互式查看状态快照 |
| Web 可视化 | 需要非开发者用户（如 Agent 创作评审）查看战斗回放时 | 前端时间线 + 帧渲染，后端复用 ReplayViewer API |
| 与 tick profiler 集成 | 阶段 1 tick 框架就绪 | 将 combat 回放嵌入 tick 级时间线，定位特定 tick 的战斗帧 |
| M1 开源仓库对接 | M1 里程碑启动 | Replay Viewer 作为 M1 开源仓库核心组件，附带示例 / 集成指南 |
| 多方战斗回放 | `resolve_attack` 扩展为多方（阵法合击等）后 | 当前 S1 仅 1v1，多方战斗后置 |
| riposte 递归回放 | riposte 递归实现后（S2） | 当前 S1 仅标记 riposte 不递归，子回合交织回放后置 |
| 全仿真确定性回放 | M3 后全仿真确定性决策点 | combat-only -> 全 System seeded RNG + input log |

---

## 八、约束与不变量

| 约束 | 来源 | 说明 |
|---|---|---|
| combat 确定性范围 = combat-only | [04](04-迁移路径与避坑清单.md) §六不做 / [CLAUDE.md](../CLAUDE.md) | Replay Viewer 只覆盖 `resolve_attack` 回合级，不覆盖 tick 级全仿真 |
| do_attack 七步文本与副作用交织不可分离 | [CLAUDE.md](../CLAUDE.md) / [ADR-0011](../docs/adr/ADR-0011-spec-conformance-checker.md) | ledger 按真实调用顺序记录，Replay Viewer 必须按该顺序渲染，不得重排 |
| 不修改 resolve_attack 内核 | 本 PRD 约束 | Replay Viewer 是消费者，非侵入 |
| PYTHONHASHSEED=0 跨进程一致 | [ADR-0012](../docs/adr/ADR-0012-performance-microbenchmark.md) | 确定性 diff 的跨进程验证基础 |
| 收敛优先于完备 | [04](04-迁移路径与避坑清单.md) §一核心立场 7 | 阶段 1 不做 TUI / Web / tick 集成，只做最小回放 + diff + conformance |

---

## 九、文件组织（预期）

```
engine/src/xkx/tools/
  replay.py          # ReplayViewer / CombatLog / ReplayFrame / DiffReport
  __main__.py        # CLI 入口（python -m xkx.tools.replay）

engine/tests/
  test_replay.py     # 回放测试（加载 fixture CombatLog、验证帧渲染、diff、conformance）
```

不新增依赖：复用 pydantic（CombatLog 序列化）+ 标准库 json / argparse。CLI 入口复用 `xkx.tools` 模块组织（与 `tools/benchmark.py` / `tools/measure_revision.py` 同级）。
