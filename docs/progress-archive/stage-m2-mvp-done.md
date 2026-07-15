# Done 归档 - M3 收尾 + M2/UGC MVP

> 从 [PROGRESS.md](../../PROGRESS.md) 归档于 2026-07-15。M3 Wave 2 收尾 / Wave 3 / Wave 4
> 收官 + M2/UGC 创作闭环 MVP 已完成条目历史记录。

- [x] M3-1 子任务 4 完整内容扩展（[ADR-0032](../../docs/adr/ADR-0032-family-core-loop-design.md) / [ADR-0036](../../docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)）- 3 师傅 + 8 武学 + 3 任务链 + ~12 房间 + 测试 bug 修复收尾 - 1744 tests
- [x] kill criteria 5 达标（第 4 轮 semantic_ratio 30.3% < 40% 走弱线）- 方向 A：rooms 注入 known ids（20 房间+11 NPC）消除幻觉引用 + quests 改人工；第 3 轮 prompt 强化 4 点使结构错误 70->0；累积 4 轮 37.0%/56.9%/44.6%/30.3% - 1744 tests
- [x] M3-3 内容审核 pipeline MVP（[ADR-0033](../../docs/adr/ADR-0033-content-review-pipeline-mvp.md)）- content_review 模块（4 类词表 + 递归扫描 + license 校验 + 状态推导 + `_review.json` + checklist MVP）+ CpkManifest review_status 字段；雪山派 4 金庸角色命中验证 - 1768 tests
- [x] M3-5 全仿真确定性评估收官（[ADR-0035](../../docs/adr/ADR-0035-full-simulation-determinism-decision-point.md)）- **否决全仿真实施，保持 combat-only**；实测 tick 驱动 System 几乎无 random，范围外随机源仅 command 路径 5 文件 8 处一次性随机；扩展成本主要是全量快照 + dissent 7 审计统一 + PYTHONHASHSEED 全局化；保留逐 System 按需纳入演进路径 - 1768 tests
- [x] M3 收官后技术债补缺口（[ADR-0039](../../docs/adr/ADR-0039-combat-path-unification.md)）- E 3 处过时注释 + B 战斗路径统一 + C1 CLI shlex 引号 tokenizer + C2 drop 命令 + C6 kneel message PronounContext 渲染 - 1771 tests
- [x] 技术债补缺口第 2 轮（[ADR-0040](../../docs/adr/ADR-0040-layer1-ask-clearflag-spawnitems.md) / [ADR-0041](../../docs/adr/ADR-0041-auto-fight-aggressive-wiring.md) / [ADR-0042](../../docs/adr/ADR-0042-door-state-machine.md)）- C4 xlama2 交互闭环 + B-2 auto_fight 接入 + C5 门状态机 - 1782 tests
- [x] 技术债补缺口第 3 轮（[ADR-0043](../../docs/adr/ADR-0043-drink-command-initial-items-tea-block.md) / [ADR-0044](../../docs/adr/ADR-0044-door-open-close-locked.md) / [ADR-0045](../../docs/adr/ADR-0045-hatred-vendetta-triggers.md)）- C4 drink 命令+厨房初始物品+持茶挡路闭环 + C5 open/close 命令+LOCKED 位 + B-2 hatred+vendetta - 1795 tests
- [x] CLI 试玩三 bug 修复 - 战斗节奏 / 死亡还阳 / demo 潜能 +4 回归测试 - 1799 tests
- [x] 抽样校准实验阶段 A（[ADR-0046](../../docs/adr/ADR-0046-sampling-calibration-methodology.md)）- 59270 调用点枚举 + 分布 + 抽样方案 80 样本 - 1799 tests
- [x] 抽样校准实验阶段 B 设计定稿（[ADR-0047](../../docs/adr/ADR-0047-greenfield-effort-semantics.md)）- 函数级分布 + greenfield 工时语义 + 80 样本候选清单 - 1799 tests
- [x] 抽样校准阶段 B 方案修正（[ADR-0048](../../docs/adr/ADR-0048-stage-b-degraded-interval-pilot.md)）- 13+类比基准区间承诺 + 误分类纠偏 + pilot 脚手架 - 1799 tests
- [x] 技术债补缺口第 4 轮（[ADR-0049](../../docs/adr/ADR-0049-multi-opponent-select-and-key-system.md)）- B-2 多对手 select_opponent + C5 钥匙系统 - 1807 tests
- [x] Demo 打磨（产品化收尾窗口，9 项）- fight 提示 / 起始 dshanlu / quest 只列进行中 / NPC 中文 alias / combat_exp 便利 / du 研读 / 藏经阁取经 / 密室雪莲丹 / kill 野狼 quest - 1812 tests
- [x] berserk 语义裁决=忠实 LPC flavor（[ADR-0051](../../docs/adr/ADR-0051-berserk-semantic-flavor-only.md)）- look NPC 详情 + 邪派 NPC flavor 不战斗；NpcDef.shen 字段 - 1814 tests
- [x] C5 残留裁决关闭（[ADR-0052](../../docs/adr/ADR-0052-c5-residual-smashed-skip-dynamic-exit-postpone.md)）- SMASHED 跳过 + 动态 exit 后置交通系统 - 1814 tests
- [x] M2/UGC 创作闭环 MVP（[ADR-0053](../../docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md)）- 自定义 Orchestrator + 4 个 MCP 校验器 + 最小 RAG + 自动修订闭环 + CLI workbench；`content_gen` 扩展 rule 生成与修订 prompt；新增 `scenes/bibles/xueshan.yaml` 与 `just orchestrate` recipe - 1833 tests
