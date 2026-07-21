# M3 拆票分析笔记（/to-tickets 会话记录）

> 本文件记录本次 `/to-tickets` 会话对 [spec.md](spec.md) 的拆分逻辑、依据，以及为解决 spec 里未钉死到可直接拆票程度的实现歧义所做的具体决策。5 张票已发布在 [issues/](issues/) 下（`01`–`05`，编号即依赖顺序）。配套的执行计划见 [implement-plan.md](implement-plan.md)。
>
> **核心目标校准**：全程围绕 [.scratch/mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md) 定义的 M3 里程碑——"UGC 创作闭环打通一次，哪怕只是一个非官方小场景，走完创作→加载→可玩全流程"。这句定义本身就是一条**反膨胀护栏**：M3 不是"设计一套 UGC 平台"或"定稿正式 DSL"，是"证明一次"。本次拆票花的心思，一半用在"怎么拆"，另一半刻意用在"怎么不拆"——即反复检查每一个看起来"顺手就能做"的扩展点（版本协商、多文件拼接、账本、脚本沙箱……）是否真的是本里程碑要交付的东西，绝大多数答案是"不是"，理由逐条记在下面「未纳入本次拆票范围」一节，不是漏拆，是刻意排除。

## 勘察方法

在动手拆票前，完整读了以下材料，确保票据引用的模块/函数/字段名与代码库当前真实状态一致（不是凭 spec 文字脑补），也确保理解"M3 到底该多小"这件事本身：

- **spec 本身**：[spec.md](spec.md) 全文（Problem Statement / User Stories 全部 16 条 / Implementation Decisions A1–D1 / Testing Decisions / Out of Scope / Further Notes）。
- **上游决策文档**：[CLAUDE.md](../../CLAUDE.md) 架构不变量第 5 条（UGC/DSL 创作层）与第 6 条（商业化支撑点，本次用来判断"哪些支撑点不该在 M3 抢跑"）；[ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md)（M3 创作面边界）；[ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)（编辑器丢弃、Web 平台是独立 post-MVP 产品——这条决定了"校验模式"该做成什么形状：CLI 契约，不是评审 UI）；[.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 的 Refinement 节（M3 最小切片的四条明确决定，逐条对照本次拆票的每一张票都能追溯到其中一条）；[07 号票](../mvp-scope/issues/07-governance-cost-tracking.md)（M3 里程碑定义原文）；[06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md)（支撑点 #2 题材包资产元数据——manifest 简化版的直接依据；支撑点 #4 世界实例隔离——用来确认"一次进程一个包"这条约束不需要额外做什么，见下）。
- **M2 precedent（两个层面都要对齐）**：[M2 spec](../m2-mvp-scene-playable/spec.md)（尤其 H1/H2 两节——场景 YAML 已知字段集的扩展方式、"单文件场景够用，多文件拼接留给需要时再设计"这条决定，本次 A1 决策直接续用同一条理由，不重新论证）与 [M2 to-tickets-notes.md](../m2-mvp-scene-playable/to-tickets-notes.md)（票据粒度惯例、Blocked-by 写法、"纯函数直测层先行"的拆分手法）+ [M2 issues/](../m2-mvp-scene-playable/issues/) 里 `03`/`04` 两张"数据地基"票的正文（票据措辞 precedent，尤其"本票不涉及 X，X 是后续票的范围"这种明确切割写法）。
- **代码库现状（逐文件读完，不是抽样）**：`engine/src/mud_engine/` 下 `scene_loader.py`（769 行，全文——确认 `load_scene` 的签名、`_TOP_LEVEL_KNOWN_SECTIONS`、透传手法、`SceneLoadError` 报错风格）、`scenes.py`（确认 `DEFAULT_SCENE_PATH`/`MVP_SCENE_PATH` 目前都硬编码在 `engine/data/` 之下，`build_world()`/`load_mvp_scene()` 没有任何"指向外部路径"的入口）、`__main__.py`（确认 `main()` 不接受任何命令行参数，`_load_or_restore` 的 restore 分支逐一重挂 `nature`/`ai`/`ferries`/`combat`/`entry_guards` 五个运行时态子系统——这是本次 B2/C1 决策抄的"作业模板"）、`cli.py`（确认 `run_repl` 已经是"不需要真实 subprocess/stdin 就能测"的设计，本次 03 号票的 `_main(argv)` 拆分是同一原则在参数解析层的第二次应用）、`errors.py`（15 行全文——确认 `SceneLoadError` 独立成模块的理由，本次 `PackManifestError` 原样抄这条理由）、`world.py`（217 行全文——确认全部"运行时态、不进存档"字段的注释写法与惯例，`pack_manifest` 字段严格照抄这个模式）、`save.py`（重点读 `world_meta.json` 的写/读函数，确认 `scene_path` 是**唯一**已经被持久化的 world 级 meta——这条读到之后才推出了 B2 的关键简化，见下）。
- **justfile + `engine/scripts/verify_m2_*.py` 一份代表性脚本**（`verify_m2_combat.py` 开头 40 行）：确认 `verify_m3_pack_loop.py`/`just verify-m3` 该长什么样、复用哪个 harness 模块（`verify_harness.py`）。
- **`engine/data/m2_mvp_scene.yaml` 与 `m1_default_scene.yaml` 的真实字段语法**（`exits`/`door`/`key`/`valuable`/`inquiry`/`shop`/`resell_discount`/`currency` 等）：确认 04 号票的示例包能不能只用这些已验证过的字段写出一个可玩通的最小场景，不需要发明任何新语法——读完之后确认可以（门锁+钥匙+问答+商店+货币这一套字段完全够撑起 04 号票设想的三房间闭环）。

## 拆分原则

1. **算法/数据层先行，组合层跟进，接口层收口，内容与证据最后**——这是 M2 precedent（"纯函数直测"先于"接入真实调度"）在一个规模小得多的里程碑上的同一次应用，只是这里的"链条"短到只有四环：`01`（manifest 纯函数）→ `02`（组合 `load_scene` + `World` 挂载 + restore 重挂）→ `03`（CLI 接口）→ `05` 的一半（端到端证据）。`04`（示例包内容）在时间上可以和 `03` 并行，因为写 YAML 内容不需要 CLI 存在，只需要 `load_pack`（`02` 的产出）存在才能验证"写的这份东西真能被加载"。
2. **manifest 与场景内容严格分文件、分错误类型、分校验阶段**，这是本次拆票里"分寸感"最重要的一处判断，值得单独说明理由（也写进了 spec A1，这里补充"为什么值得单独开一张票 `01`，不和 `02` 合并"）：manifest 校验是一个完全独立于 `World`/ECS 的纯数据问题（给一个路径，读出一个校验过的对象或者抛错），如果和 `02` 的"组合 + World 挂载 + restore"合并成一张票，会把"可以脱离全部引擎基础设施单测的纯函数"与"必须有 `World`/`scene_loader`/`save.py` 才能测的集成逻辑"这两种完全不同的测试 seam 挤进同一张票的验收标准里——这正是 M2 `to-tickets-notes.md` 拆分原则 1 说的"prefactor 优先"的反面教材（如果不分开，`01` 的内容会变成 `02` 票里一段"顺便也把 manifest 解析写一下"的隐藏子任务，容易在验收时被跳过测试细节）。分开后 `01` 票可以在完全不理解 `World`/ECS 是什么的情况下被独立实现、独立验收，这是"票据可在一个新 context window 内完成"这条尺寸要求的加分项，不是过度拆分。
3. **依据真实存档持久化现状决定 B2，不是照抄 spec 字面的"可能需要扩展存档格式"**——这是本次拆票里唯一一处"读代码之后改变了原本设想"的地方，值得完整记录（下面「关键设计决策」第 1 条）。
4. **`04`（示例包内容）与 `01`/`02`/`03` 严格解耦成"内容票"与"机制票"**，对齐 M2 precedent（`08` 门派框架机制 vs `24` 少林具体内容分离）的同一条原则——`04` 号票不允许要求任何引擎代码改动，这条约束本身写进了 `04` 号票的 What to build 首句（"不改 `engine/src/mud_engine/` 下任何一个模块"），是一条**验收阶段可以直接拿代码 diff 核对的硬约束**，不是一句空洞的原则宣言。这条约束也是给 spec Implementation Decisions「D1」"若撞上表达力缺口记 GAP、不借机扩表达力"这条精神上一道机制性的锁——如果实现者在写 `04` 号票时发现"不改引擎代码就是写不出我想要的效果"，这个信号本身就应该触发"记 GAP、简化场景设计"而不是"顺手加个字段"，因为改了引擎代码这一步会直接违反本票的验收标准，逼着实现者走 spec 期望的那条路径。
5. **`05` 号票同时承担"端到端证据"与"里程碑收口文档更新"两个职责，不拆成两张票**——理由与 M2 `26` 号票（六分区互联 + e2e 剧本 + 更新 PROGRESS.md）完全一致：M3 只有一个里程碑收口点，不像 M2 有五个 wave 各自需要收口，没有必要为"测试"和"改 PROGRESS.md/ADR"这两个动作强行分成两张需要互相协调时序的票——它们本来就是同一次"确认里程碑达成"动作的两个自然产出。

## 关键设计决策 / 已解决的歧义

spec 里有一处明确留给 `/to-tickets` 阶段核对的"假设待验证"决策，以及几处 spec 文字本身没有钉死到可直接拆票程度的具体选择，记在这里供 `/implement` 阶段直接采纳：

1. **B2「`pack_manifest` 是否需要扩展 `save.py` 持久化格式」——读代码后推翻了"大概需要扩展"的初始直觉，改判为"完全不需要"**：spec 撰写时的直觉（写在 Further Notes 里）是"这处决策值得在 `/to-tickets` 时反复确认"。读完 `save.py` 后发现：`world_meta.json` 目前**只**持久化 `scene_path` 一个 world 级字段，而 `__main__.py` 的 restore 分支已经确立了一个稳定模式——"运行时态子系统（`nature`/`ai`/`ferries`/`combat`/`entry_guards`）都不进存档，restore 后从 `world.scene_path` 反推配置来源、重新 `attach_xxx` 一遍"。`pack_manifest` 完全可以套进同一个模式：它本质上是"从 `scene_path` 的同级目录能反推出来的一份配置"（`scene_path.parent / "manifest.yaml"`），不需要变成存档里的一等数据。这次核对的结论是**维持 spec 原判**（不扩展 `save.py`），但把"为什么维持"的依据从"spec 撰写时的推测"升级成了"读完 `save.py` 实际持久化范围后的确认"——`02` 号票的验收标准里专门加了一条"`save.py` 未被本票改动"的检查项，把这个核对结论钉成可验证的硬约束，防止实现阶段因为"顺手"又滑回扩展存档格式这条更重的路径。
2. **manifest 与 scene 的错误类型是否要合并成一种**：spec A3 已经给了结论（不合并），这里补充拆票时确认过的一个边界情况——`load_pack` 内部调用顺序是"先 `load_manifest`，再 `load_scene`"，因此 manifest 坏的包永远不会触发 `load_scene`（不会因为场景内容也可能有问题而产生两条报错、需要决定先报哪个）。`02` 号票验收标准第 3 条专门要求验证这条调用顺序（用消息内容或调用是否发生来判断），避免实现时颠倒顺序或改成"两者都跑、合并报错"这种更复杂但没有必要的设计。
3. **CLI 参数解析要不要支持 `--pack` 缺省走某个约定路径（如当前目录）**：spec 没有提这个选项，本次拆票明确不引入——`--pack` 缺省即"不使用这条新机制，走原有默认场景"，不做"缺省猜测当前目录是不是一个包"这类隐式行为，隐式路径推断是没有请求过的复杂度，容易在用户忘记加参数、只是想跑默认场景时误判。这条决策已经体现在 `03` 号票"不传 `--pack` 行为与本票开工前完全一致"的验收标准里，不需要额外记录，这里说明一下"为什么没有第三种模式"以防实现者觉得漏了什么。
4. **`--validate` 是否要支持不带 `--pack`、改为校验默认官方场景**：明确不做（spec C1 已写"单独出现报参数错误"）。理由：官方场景（`m1_default_scene.yaml`/`m2_mvp_scene.yaml`）已经有一整套 `engine/tests/` 与 `just verify-m2-*` 在持续验证，"校验默认场景"不是一个真实存在的未满足需求，`--validate` 存在的唯一理由是给**外部**内容包一个不启动 REPL 的反馈通道（spec Problem Statement 的第二段）。
5. **示例包（`04`）的题材与具体场景设计不是 spec 强制的唯一答案，但"非武侠"这条约束是硬性的**：spec D1 给了一个具体设计（废弃探测站/机器人/通行卡），`04` 号票原样采纳而不是留白让实现者自己发明——理由是这类"选一个具体故事"的决策没有多个候选方案需要权衡（不像 M2 的坐骑所有权语义那样存在真实的设计张力），事先钦定能省掉 `/implement` 阶段一次不必要的创作决策往返。如果实现者觉得这个具体故事不好写/不好玩，可以在 `04` 号票 Comments 里换一个**同样非武侠**的故事，但换故事本身不需要回来改这份 notes 或 spec。

## 与 spec 决策块的映射（供回溯）

| spec 块 | 覆盖票据 | 备注 |
|---|---|---|
| A（内容包外壳：manifest） | `01` | 纯数据/纯函数层，独立于 `World` |
| B（指向加载：`load_pack` + `World` 挂载 + restore 重挂） | `02` | 组合现有 `load_scene`，不修改它一行；B2 的"不扩展存档格式"是读代码后确认的关键简化 |
| C（校验模式，不玩） | `03` | 与"指向加载"共用同一 CLI 入口/同一 `load_pack` 调用，未单独拆票（同一 argparse 表面，拆开协调成本大于收益） |
| D（非武侠示例包 + 端到端证明） | `04`, `05` | 内容票（`04`）与证据/收口票（`05`）分离，对齐 M2 precedent 的"内容 vs 集成收口"分层 |

## 未纳入本次拆票范围（明确排除，对齐 spec Out of Scope）

以下不对应任何票据，理由已在 spec Out of Scope 逐条说明，本次拆票不重复展开，只做清单式确认，避免遗漏后续被误当作"漏拆的票"：正式 UGC DSL 的版本协商/向后兼容承诺、游戏内编辑器与 Web 评审工作台（ADR-0006 已丢弃/列入独立 post-MVP 产品）、Ink 对话树、RestrictedPython 逃生舱或任何脚本层、针对"内容包来自外部/不受信"这一假设专门新增的沙箱/运行时护栏（现有 `yaml.safe_load` + 结构性校验的风险面与加载官方场景完全相同，没有新增攻击面需要专门堵）、LLM Orchestrator/Agent 生成编排流水线、多文件场景拼接、单进程同时加载多个内容包、manifest 之外的完整题材包资产元数据方案（账本/埋点/分成计算）、把 `python -m mud_engine` 的默认场景从 M1 极简场景切换成 M2 官方 MVP 场景（与本里程碑目标无关的独立既有缺口，见 spec Out of Scope 最后一条）。

## 一个值得记录的"零成本副产品"

[06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md) 支撑点 #4"世界实例隔离：每个题材包独立进程运行"在本次拆票范围里**不需要任何一张票**去实现——"一次 `python -m mud_engine --pack <目录>` 进程只加载这一个包"本身就是 `03` 号票交付的默认行为（`load_pack`/`_main` 从设计上就没有"一个进程内切换/叠加多个包"这种能力），这条支撑点是这几张票的自然副产品，不是刻意去满足它而多写的代码。记在这里是为了在未来 M4/post-MVP 回看商业化支撑点清单时，能直接引用到这批 M3 票据作为"这一条已经免费满足"的证据，不需要到时候重新论证一遍。
