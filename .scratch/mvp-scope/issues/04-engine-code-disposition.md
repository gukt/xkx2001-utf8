Type: grilling
Status: resolved

## Question

`engine/` 现有约 45k 行代码(runtime + combat + tests 等),在"不做行为等价验证"([ADR-0001](../../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md))这一前提下,应该如何处理?

已知会受影响的部分:专门服务"精确对齐 LPC 行为"的基建大概率没用了——golden trace 录制/回放工具(`engine/tools/golden_trace/`)、逐条对齐 LPC 随机数公式的战斗结算逻辑(如 `resolve_attack.py` 里按 LPC wound 概率分 4 支的逻辑)。但引擎骨架部分(房间/对象模型、命令分发、数据存储、tick 调度)可能仍有工程价值。

候选姿态:
- **逐子系统评估复用**:能用的段落(房间/对象模型/命令分发等)留着,专门为等价验证服务的部分直接删
- **整体重写**:新目标下引擎架构形态可能和"忠实复制 LPC"差别很大,干脆彻底重写,旧代码只当参考
- 其他

## Answer

整体重写。新目标(题材无关引擎 + UGC + 轻量题材包)下引擎的架构形态,预期和"忠实复制 LPC 行为"的旧形态差别太大——旧代码里大量结构(战斗结算的公式对齐、golden trace 基建、围绕 6414 房间全量迁移设计的层次)都是为已被推翻的旧目标服务的,delta 太大,逐段评估复用的性价比不如推倒重来。

旧代码(`engine/`)只作参考,不作为重写的起点或复用对象。具体哪些设计思路值得参考(例如房间/对象模型的骨架形状、ECS 相关的取舍教训),留给后续 `/to-spec` 阶段按需查阅,不在本 ticket 展开。
