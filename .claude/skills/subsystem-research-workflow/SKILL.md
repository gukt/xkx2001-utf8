---
name: subsystem-research-workflow
description: 当用户要求对游戏/MUD 项目中的某个子系统进行全面研究调研、源码分析、设计评审时，强制使用本 skill。触发词包括"调研 X 系统""全面分析 X""组织团队评审 X""对 X 做深度研究""帮我理解 X 子系统""提取 X 的设计思想"等。本 skill 会先通过 grilling 对齐范围、团队、产出与约束，然后组织多 Agent 虚拟调研团队，并行产出原始素材、三层 User Stories、引擎设计灵感、红队对抗与最终汇总报告，保存到 .scratch/research/NN-topic-name/ 下。默认不自动 commit。
---

# 子系统深度调研工作流

## 何时使用

本 skill 用于对游戏/MUD 项目中的单一子系统（如任务系统、战斗系统、社交系统、经济系统、门派系统、交通系统等）进行深度源码调研与设计批判。它通过组织虚拟多角色团队，强制对齐目标后并行产出结构化文档。

当用户提到以下任意意图时触发：

- "帮我调研一下 X 系统"
- "全面分析源码中的 X"
- "组织团队评审 X"
- "对 X 做深度研究"
- "X 系统的设计思想/原始细节"
- "为新的 engine 提取 X 的机制"

## 执行流程

### 阶段 0：Grilling 对齐（强制，不可跳过）

使用 `grilling` skill 或等效连续提问，逐一向用户确认以下决策点，直到达成共享理解。每个问题等待用户回答后再继续。

必须覆盖的决策点：

1. **调研范围**：子系统的边界（核心机制、代表性实例、与周边系统交互）。
2. **调研目标**：是为了 engine 抽象、存档考古、现代设计批判，还是三者兼有。
3. **团队角色**：使用默认角色模板还是调整（见 `references/team-roles.md`）。
4. **产出结构**：是否使用默认目录，是否增加/删减层级。
5. **保存位置**：默认 `.scratch/research/NN-topic-name/`，NN 自动递增。
6. **对抗与评审机制**：模式 A（成对挑战）或模式 B（评审委员会 + 红队）。
7. **执行方式**：默认 Workflow 多 Agent 并行。
8. **是否自动 commit**：默认否。

详细问题清单见 `references/grilling-questions.md`。

### 阶段 1：初始化目录与总则

1. 扫描 `.scratch/research/` 下已有主题目录，确定下一个序号 NN。
2. 创建 `NN-topic-name/` 目录。
3. 在该目录下创建：
   - `00-brief/brief.md`：总则文件
   - `01-raw-findings/`、`02-user-stories/`、`03-engine-insights/`、`04-redteam-review/`、`05-synthesis/`
4. 可以使用 `scripts/create_research_skeleton.py` 自动创建骨架。

### 阶段 2：多 Agent 并行 Workflow

使用 Workflow 工具启动三阶段调研。Workflow 脚本模板见 `references/workflow-template.md`。

Phase 1：并行初稿

- 一手考古组：源码清单、玩法切片、机制抽象。
- 机制抽象组：引擎核心抽象、题材包扩展表面、创作者视角。
- 现代评审组：现代设计对照、玩家心理、商业化评估。

Phase 2：红队对抗

- 横向对比验证：找出共同模式与特例，验证抽象覆盖度。
- 现代玩法挑战：对 LPC 机制与抽象方案提出尖锐质疑。
- 体验风险挑战：识别玩家流失点与必须的保护机制。
- 商业化风险挑战：识别经济风险与 pay-to-win 陷阱。

Phase 3：评审委员会汇总

- 5 人评审委员会审阅所有初稿与红队报告，统一文风、消除矛盾、裁决分歧，生成最终报告。

### 阶段 3：补全失败产出

Workflow 完成后，检查是否有 agent 失败。如有：

1. 单独使用 Agent 工具重新运行失败角色。
2. 如果最终报告已在失败前生成，在报告中补充说明或增加附录引用补全文件。

### 阶段 4：最终检查与汇报

1. 检查所有预期文件是否存在且非空。
2. 检查最终报告是否引用所有关键产出。
3. 向用户汇报：产出结构、文件清单、核心摘要、执行过程中的问题。
4. **仅在用户明确要求时才执行 commit & push**。

## 默认目录结构

```bash
.scratch/research/NN-topic-name/
├── 00-brief/
│   └── brief.md                    # 总则、范围、团队、方法
├── 01-raw-findings/                # 一手源码素材
├── 02-user-stories/                # 三层 User Stories
├── 03-engine-insights/             # 设计灵感、可选方向、风险警示
├── 04-redteam-review/              # 红队对抗记录
└── 05-synthesis/                   # 评审委员会最终汇总
```

## 约束与原则

- **只基于一手资料**：所有结论必须能从当前仓库源码中找到证据。
- **不做行为等价验证**：不追求逐字复刻原始系统行为。
- **全局与细节兼顾**：既要有宏观脉络，也要有代表性实例细节。
- **现代视角批判**：对过时、不符合当代玩家习惯或商业化潜力的设计显式标注。
- **可复用目录结构**：`.scratch/research/` 按主题编号，方便后续扩展。
- **默认不自动 commit**：由用户决定是否提交。

## 团队角色

默认团队角色与职责见 `references/team-roles.md`。

## Workflow 模板

`references/workflow-template.md` 提供可直接改编的 JavaScript Workflow 脚本模板。

## 示例

用户："帮我组织团队深度调研一下战斗系统。"

Skill 行为：

1. 进入 grilling，确认战斗系统范围、团队、产出、保存位置。
2. 创建 `.scratch/research/02-combat-system/` 与默认子目录。
3. 启动 Workflow，组织 10+ 个虚拟研究员并行工作。
4. 产出源码清单、战斗机制抽象、三层 User Stories、现代设计批判、红队报告、最终汇总。
5. 汇报产出结构，不自动 commit。
