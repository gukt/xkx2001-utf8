# 抽样校准实验 阶段 B（设计定稿）

## 背景与关键修正

阶段 A 已完成（[ADR-0046](docs/adr/ADR-0046-sampling-calibration-methodology.md) + 59270 调用点 + 分布 + 抽样方案 + 函数级建议）。本轮范围（用户已确认）：**设计定稿**——脚本扩展 + 函数级分布 + 已实现/待迁移分类 + 抽样设计 + 实测方法论定稿。**实测执行留后续**，基于本轮产出的确定样本清单启动。

**关键修正（greenfield 工时语义）**：项目是 greenfield 重写，新引擎已实现 C1-C6 系统级等价（对照 `engine/src/xkx/runtime/` + `combat/`：dbase_map+components / skill / combat / equipment / conditions / world）。报告 §三类别分布中 C1-C6 合计 ~82.4% 调用点的等价行为**已实现**，工时≈0 或为低工时内容填充。真正待迁移是 C7（7.0%）+ C8（10.5%）= ~17.5%。报告 §六"对全 59270 抽样"的方案在 greenfield 语境下会重复计已实现部分、严重高估工时，需修正。

## 工时三分法（阶段 B 估算基础）

1. **框架已实现**（C1-C6，~82.4%）：新引擎已有 System/组件，工时≈0（已完成）
2. **内容填充**（NPC/房间/物品数据定义，如 `create()` 里大量 `set()`）：低工时数据录入，可批量
3. **新逻辑实现**（C7/C8 长尾里新引擎尚无的等价行为）：代码实现，工时变异大——**实测主对象**

## 步骤 1：扩展脚本做函数级分布

- 改 [engine/tools/sampling/scan_callothers.py](engine/tools/sampling/scan_callothers.py)：新增函数解析模式
- LPC 函数定义正则：`^(?P<mods>(?:nomask|private|public|static|varargs|protected)\s+)*(?P<type>\w[\w\s]*?\*?)\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?P<end>[{;])`，兼容 `){` 紧贴（kungfu 实证）、数组类型 `string *`
- 花括号配对定 body 范围，把调用点归入所属函数；前向声明（`;` 结尾）不计
- 按函数聚合：每函数调用点数、主导方法类别、子系统、是否 create/setup 类数据函数
- 输出：`output/func_dist.json`（函数级分布）+ `callothers.jsonl` 增 `func` 字段
- 边角遗留：lambda `(: :)` / 匿名函数 / 宏 `##`（报告 §三已记风险，少量误分类可接受）

## 步骤 2：已实现/待迁移分类

- 建方法类别 -> 状态映射表（对照 runtime/ 模块）：
  - C1 dbase -> `components`+`dbase_map`（已实现）；C2 技能 -> `skill`（已实现）；C3 战斗 -> `combat`（已实现）；C4 装备 -> `equipment`（已实现）；C5 条件 -> `conditions`（已实现）；C6 移动 -> `world`（已实现）
  - C7 其他 top30 / C8 长尾 -> 待迁移（逐方法/逐函数判定）
- 待迁移再分：**内容填充**（`create`/`setup`/`skill_set*` 等数据函数）vs **新逻辑实现**（`ask_me`/`perform`/`second_hit`/长尾行为函数）
- 输出：`output/classification.json`（每函数：状态 + 子类 + 调用点数）

## 步骤 3：抽样设计

- C1-C6 欠采样（已实现，每子系统 1-2 个确认工时≈0/低工时）
- C7/C8 待迁移聚焦：按子系统 ×（内容填充/新逻辑实现）分层
- 新逻辑实现过采样（工时变异大，是估算主信息源）；内容填充少量确认规律
- 产出 `output/sample_candidates.json`：80 样本候选清单（每样本：函数路径、子系统、状态子类、调用点数、预估复杂度档）
- 样本量最终确认：基于步骤 1-2 分布，若待迁移面集中可减量到 40-60（收敛优先）

## 步骤 4：实测方法论定稿

- **实测操作定义**：给定 LPC 函数 + 新引擎已有上下文，实现等价行为（Python 代码 + 单元测试）的工时
- **工时记录字段**：读规格 / 写代码 / 写测试 / 调试 / 小计（分钟）
- **推算方法**：分层均值 × 层规模 + t 分布置信区间（非 59270 × 单点线性外推）
- **实测代码处置**：可集成优先（迁移到 `engine/src/xkx/content/` 对应模块，一举两得），标注一次性测量代码
- **样本量与置信区间目标**：步骤 1-2 分布确定后计算，写进方法论

## 交付物

| 交付物 | 路径 |
|---|---|
| 扩展脚本（函数级 + 分类） | [engine/tools/sampling/scan_callothers.py](engine/tools/sampling/scan_callothers.py) |
| 函数级分布 + 分类 JSON | `engine/tools/sampling/output/func_dist.json` / `classification.json` / `sample_candidates.json` |
| 报告增补 | [engine/tools/sampling/report.md](engine/tools/sampling/report.md)（阶段 B 设计定稿章节） |
| 方法论 ADR（greenfield 工时语义修正） | `docs/adr/ADR-0047-greenfield-effort-semantics.md`（关联 ADR-0046） |

## 决策点

- 迁移单位 = 函数（报告 §五建议，采纳）
- 已实现/待迁移分类（greenfield 本质，采纳，修正报告 §六抽样面）
- 本轮范围 = 设计定稿，实测留后续（用户已确认）

## 风险

- 函数解析边角误分类（遗留少量，报告记）
- "已实现"是框架级非完整级（如 dbase_map 67 key 非全 key），内容填充仍需补 key 映射——属低工时数据录入，不计入新逻辑实现工时
- 抽样代表性：分层配额 + 层内随机结合

## 不做（本轮边界）

- 不手工实测工时（留后续，基于确定样本清单）
- 不迁移代码到 src/xkx/（留后续）
- 不扫描 `call_other()` efun / `.h`（ADR-0046 后置）
- 本轮只写工具脚本（`engine/tools/sampling/`）+ 报告 + ADR，不改 `src/xkx/` 产品代码

## 验收

- 函数级分布可复现（`cd engine && uv run python -m tools.sampling.scan_callothers`）
- 已实现/待迁移分类覆盖全 59270 调用点（无遗漏大类）
- 80（或减量）样本候选清单 + 实测方法论定稿，下一轮可直接据此启动实测
- ADR-0047 记录 greenfield 工时语义修正，关联 ADR-0046 + 05 dissent
