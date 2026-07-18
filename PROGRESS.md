# 项目进度

> 本文件是跨 session 的"活的状态"——每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> **2026-07-17 项目重设，2026-07-18 新目标定稿+CLAUDE.md 重写完成**：原目标与取舍战略已放弃，新目标已用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 9/10 票决策（[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 用户主动标"暂定"未拍板，不阻塞其他票）并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"章节。重设前的完整进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)（含更早的按阶段归档 [docs/archive/progress-archive/](docs/archive/progress-archive/)），仅作背景参考。

**最后更新**：2026-07-18（M1 spec 范围修订：加 YAML 场景 DSL，补 06 号票；`ecs.py`→`world.py` 改名 + 补方法级注释）

## 当前状态速览

- **阶段**：M0 完成；M1 spec 已产出，`/to-tickets` 已拆出 5 张票（[.scratch/m1-core-engine-skeleton/issues/01~05](.scratch/m1-core-engine-skeleton/issues/)）；**01 号票（引擎骨架 ECS+命令调度+CLI+静态移动）已 resolved**。下一步：`/implement` 02 号票（解析执行解耦 + 别名机制）。
- **分支**：见当前 git 分支。
- **engine/ 现状**：`src/mud_engine/` 下已有 `world.py`/`components.py`/`commands.py`/`scenes.py`/`cli.py`/`__main__.py`，`python -m mud_engine` 可跑通真实终端最小闭环（`go`/`look`/`help`/`h`/`quit`）。38 条测试，`just gate` 全绿。

## Done

- **M1 spec 范围修订 + 补 06 号票**：用户要求 M1 阶段加 YAML 场景数据 DSL(房间/物品/静态展示型 NPC),与 spec 原有"格式设计留给 M3""NPC 与 NPC AI 推到 M2"两条冲突,已跟用户确认收窄范围(YAML 是 M1 内部过渡格式,不是 M3 正式 UGC DSL;NPC 只开放"无行为的静态展示型")并更新 [M1 spec](.scratch/m1-core-engine-skeleton/spec.md)(「场景数据与引擎能力的边界」「Out of Scope」「范围修订记录」三处),补了 [06-yaml-scene-dsl](.scratch/m1-core-engine-skeleton/issues/06-yaml-scene-dsl.md)(阻塞:03,可与 05 并行)。**06 号票尚未 `/implement`**。
- **M1 `/to-tickets` 拆票**：6 张票发布到 [.scratch/m1-core-engine-skeleton/issues/01~06](.scratch/m1-core-engine-skeleton/issues/)（01 骨架→02 解析别名→03 物品/04 门可并行→05 存档、06 YAML DSL 可与 05 并行），阻塞关系已与用户确认。
- **M1 01 号票：引擎骨架落地**（[01-engine-skeleton-ecs-dispatch-cli](.scratch/m1-core-engine-skeleton/issues/01-engine-skeleton-ecs-dispatch-cli.md)，resolved）：ECS 最小存储（6 种操作）+ 命令注册表（`go`/`look`/`help`/`h`/`quit`）+ 静态三房间场景数据 + 真实终端 CLI 循环；`/code-review` 双轴过一遍后补了 `World.require_component`（收口重复的 `assert is not None` 场景数据完整性检查，避免 `python -O` 下失效）。
- **测试命名约定改为 BDD 嵌套类风格**（用户决定，记在 [engine/README.md](engine/README.md)「测试约定」）：Given/When 分组成嵌套类，方法名只写 Then；**踩坑**：这些嵌套类不带 `Test` 前缀，pytest 默认配置会静默跳过，已在 `engine/pyproject.toml` 把 `python_classes` 扩到 `["Test*", "When*", "Given*"]`，后续新增分组类名前缀要同步扩展这个列表。
- **Python 包 rename**（[ADR-0003](docs/adr/0003-python-package-mud-engine.md)）：`src/xkx/` → `src/mud_engine/`（`import mud_engine`）；发行名 `mud-engine`；archive tag 内旧路径不变。
- **M1 第 0 步：engine 工作区绿场重置**（[.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md](.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md)）：tag `archive/engine-pre-m1-rewrite`；移除旧 `src/tests/scenes/tools`；路径仍为 `engine/`；[ADR-0002](docs/adr/0002-engine-workspace-greenfield-reset.md)；CLAUDE/justfile/M1 spec 已同步。
- **`/to-spec` 产出 M1 spec**：[.scratch/m1-core-engine-skeleton/spec.md](.scratch/m1-core-engine-skeleton/spec.md)（Status: ready-for-agent）。范围=移动/查看/拾取丢弃/门与动态出口/存档骨架；CLI 真终端；ECS 组件按复用性拆分；解析/执行两阶段 + 别名。
- **`/wayfinder` mvp-scope 地图 9/10 票解决**（[.scratch/mvp-scope/map.md](.scratch/mvp-scope/map.md)，[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 暂定挂起）。结论摘要见 [CLAUDE.md](CLAUDE.md)「架构不变量」；[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)。
- **重写 [CLAUDE.md](CLAUDE.md)** 项目一句话 + 架构不变量 8 条。

## In Progress

- **`/prototype` ECS×UGC 手感**（可选收尾）：`just proto-ecs-ugc`（`engine/prototypes/ecs_ugc/`）。结论已部分吸收进 M1 spec；若不再跑可标完成。

## Blocked

**当前无阻塞项。**

## Next Up

1. 新 session：读本文件 + [CLAUDE.md](CLAUDE.md) + [M1 spec](.scratch/m1-core-engine-skeleton/spec.md)（注意文末「范围修订记录」，07-18 加了 YAML DSL 范围）。
2. `/implement` [02-parse-execute-decoupling-aliases](.scratch/m1-core-engine-skeleton/issues/02-parse-execute-decoupling-aliases.md)：把 01 号票"读一行直接查表"的路径重构成"解析（文本->意图）"+"执行（意图->效果）"两阶段，加命令别名（`i`/`l`/`n`/`s`/`e`/`w`）与通用目标别名匹配工具。完成后 03、04 号票可并行认领。
3. 03 完成后可 `/implement` [06-yaml-scene-dsl](.scratch/m1-core-engine-skeleton/issues/06-yaml-scene-dsl.md)（与 05 号票并行不冲突）：房间/物品/静态展示型 NPC 改成 YAML 加载。
4. [02-engine-boundary-combat-effects](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md)（mvp-scope 里的票，不要跟上面 M1 的 02 号票搞混）建议在 M2 `/to-spec` 前用 `/prototype` 或 `/design-an-interface` 补上——不阻塞 M1。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR（[docs/adr/](docs/adr/)，重设后从头编号）。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
