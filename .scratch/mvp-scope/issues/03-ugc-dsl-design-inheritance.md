Type: grilling
Status: resolved

## Question

UGC/DSL 创作层的 MVP 设计,要不要直接继承旧方案的"DSL 四层 + Agent 协作创作"设计(见 [docs/archive/xkx-arch/03-DSL-UGC与Agent协作.md](../../../docs/archive/xkx-arch/03-DSL-UGC与Agent协作.md)),还是完全从零重新设计?

## Answer

不直接沿用旧方案的四层结构。基于新目的地(题材无关引擎 + 轻量题材包 MVP)重新设计,但旧方案与 [01-关键修正与避坑清单.md](../../../docs/archive/xkx-arch/_archive/01-关键修正与避坑清单.md) 中 UGC 相关的教训(例如"§23 UGC 脚本用受限 Python 非 WASM"、"§H WASM 定位为无状态计算单元"、"§21 inquiry 是交易状态机非对话树")作为重要参考输入,不能忽略这些已经用真实代码验证过的坑。

## Refinement（2026-07-21，M3 前核对）

本节省是对上方 Answer 的**可实施细化**（不是改判"不沿用四层"）。对齐 [07](07-governance-cost-tracking.md) 的 M3 定义："UGC 创作闭环打通一次（哪怕只是一个非官方小场景，走完创作→加载→可玩）"。编辑器归类核对结论见本节末，并写回 [08](08-subsystem-classification-research.md) / [09](09-subsystem-classification-confirm.md)；决策摘要见 [ADR-0005](../../../docs/adr/0005-m3-ugc-loop-creation-surface.md)。

### M3 创作闭环最小切片（新设计，非旧四层缩水版）

1. **内容载体**：可独立加载的**非官方内容包**（目录或单文件均可起步）= manifest（至少 id / 版本 / 可选创作者字段，对齐 [06](06-scaling-commercialization-support-points.md) 题材包元数据支撑点的简化版）+ 声明式场景数据。现有 `scene_loader` YAML 是 M1 内部过渡格式（模块文档已写明），M3 在其上演进为"包可被指向加载"，不要求一次定稿正式 DSL 语法。
2. **表达力边界**：M3 以**声明式数据**覆盖闭环（房间 / 物品 / NPC / 出口等，对齐引擎已加载能力面）。**不交付**旧方案层 2（Ink 对话树）与层 3（RestrictedPython 逃生舱）；复杂逻辑继续用引擎已有钩子 / 组件字段，不够则标 GAP，不借机扩脚本层。
3. **创作界面**：包外创作（手写或 Agent 生成声明式数据 → 加载校验 → 进世界可玩）。**不做**游戏内编辑器，**不做** Web 评审工作台。Agent / Orchestrator 全套是加速手段，不是 M3 闭环定义的一部分——人工写包也算打通。
4. **从旧方案继承、M3 即生效的约束**（教训，不是层结构）：
   - §23：若未来加脚本层，用受限 Python，非 WASM 作为 UGC 作者主路径。
   - §H：脚本 / WASM 定位为无状态计算；有状态多 actor 协调走引擎 Effect / 规则，不塞进沙箱状态。
   - §21：inquiry 是交易状态机非对话树——M3 继续静态 inquiry，不引入对话树层。
   - §19：wizard ACL 与 UGC 沙箱分离——M3 若尚无沙箱，也不要把运维权限模型塞进内容包。
   - 逃生舱使用率 KPI / 层 1 原语蠕变：M3 用"先不引入脚本层"直接回避；日后引入时再设 KPI。

### 明确不做（相对旧方案 / 旧 ADR-0053）

- 不重建 L0–L3 四层栈作为 M3 架构。
- 不把 LPC `editord.c`（文选 / 文库投稿归档）当创作主路径模板。
- 不把"生成→校验→修订"的 LLM Orchestrator 定为 M3 必达（可后置到 M3 加分或独立 wave）。

### 编辑器系统（子系统 9）归类核对

**2026-07-21 初核**：曾维持「现代化改造」。

**同日改判（用户确认 + [ADR-0006](../../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)）**：**改判为「丢弃」**。

| 选项 | 结论 |
|---|---|
| 升为 MVP 必做 | **否**。 |
| 维持现代化改造 | **否（已撤销）**。引擎不做 LPC 文选/`F_EDIT`；未来创作 UX 是独立 Web 平台，不落在引擎内「现代化改造」。 |
| 降为丢弃 | **是**。对引擎无设计参考价值。创作者一站式平台与留言板机制见 [post-mvp-backlog.md](../post-mvp-backlog.md)。 |

跨票遗留"03 细化后核对编辑器"关闭；档位分布见 [08](08-subsystem-classification-research.md) 最新版。
