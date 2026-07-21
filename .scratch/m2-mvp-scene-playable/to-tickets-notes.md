# M2 拆票分析笔记（/to-tickets 会话记录）

> 本文件记录本次 `/to-tickets` 会话对 [spec.md](spec.md) 的拆分逻辑、依据、以及为解决 spec 里未明确的实现歧义所做的具体决策。26 张票已发布在 [issues/](issues/) 下（`01`–`26`，编号即依赖顺序）。配套的执行计划见 [implement-plan.md](implement-plan.md)。
>
> **核心目标校准**：全程围绕 CLAUDE.md"项目一句话"——**题材无关的核心 MUD 引擎 + UGC 创作层 + 一个官方轻量武侠题材包（MVP）**。拆票时反复检查每一条机制是否遵循 ADR-0004"骨架固定 + 钩子策略注入"手法（声明式 policy 枚举 + Protocol 钩子 + 注册表注入），确保"机制归引擎、数值/文案/具体设定归题材包"边界在票据粒度上也保持清晰——这是本次拆票与单纯"把 spec 的用户故事挨个抄成票"的关键区别：**很多票的验收标准明确要求"机制"与"少林/扬州具体内容"分离**（如 08 号票只做门派通用框架，少林具体内容单独在 24 号票）。

## 勘察方法

在动手拆票前，完整读了以下材料，确保票据引用的文件名/函数名/组件名与代码库当前真实状态一致（不是凭 spec 文字脑补）：

- **spec 本身**：[spec.md](spec.md) 全文（Problem Statement / User Stories 全部 67 条 + 60a–60c / Implementation Decisions A1–H2 / Testing Decisions / Out of Scope / Further Notes / 范围修订记录）。
- **上游决策文档**：[CLAUDE.md](../../CLAUDE.md) 架构不变量全 8 条、[ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md)（战斗/效果引擎边界）、[M1 spec](../m1-core-engine-skeleton/spec.md)（对象模型/命令调度/存档的设计原则，M2 直接延续）、[mvp-scope 10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md)（场景清单定稿，本次场景内容票的验收清单直接引用它而不重复枚举）、[PROGRESS.md](../../PROGRESS.md)（当前状态、`_spawn_scan` 复核点）。
- **M1 票据precedent**：[.scratch/m1-core-engine-skeleton/issues/](../m1-core-engine-skeleton/issues/) 全部 36 张票的标题与至少 3 张代表性票的正文（`25-npc-behavior-aicontroller.md` 等），确认本仓库 issue tracker 的票据粒度惯例、`Blocked by`/`Status`/Acceptance Criteria 的写法风格。
- **代码库现状（逐文件读完，不是抽样）**：`engine/src/mud_engine/` 下 `components.py`、`capabilities.py`、`ai.py`、`matching.py`、`conditions.py`、`scene_loader.py`、`save.py`、`commands.py`、`events.py`、`transfer.py`、`world.py`、`intent.py`、`parsing.py`。这一步是本次拆票"深度细致严谨"的关键支撑——很多票的验收标准（如"复用 `attach_ai_system` 同构模式""走 `run_vetoable`/`Deny` 现有机制"）都是基于读到的真实实现细节写的，不是照抄 spec 字面描述。

## 拆分原则

1. **Tracer-bullet 纵向切片，但允许"纯算法层"独立成票**。to-tickets 骨架要求"每个切片是贯穿全部层的纵向切片"，但本 spec 的 Testing Decisions 自己明确划分了四层可独立验证的 seam（纯函数直测 / 命令层 / tick 层 / 端到端剧本），M1 票据 precedent 也确实把"纯算法"独立成票（如 M1 10 号票"条件表达式求值器"）。本次沿用同一惯例：`02`（战斗结算核心）、`03`（技能数据地基）、`06`（死亡状态机核心）都是"先做可独立单测的算法/数据层"，再由后续票把它们接入真实 ECS/命令层（`12`/`17` 等）。这不是违反纵向切片原则，而是"prefactor 优先"在这个代码库里的具体体现——这些票本身也是可独立验证、可演示（unit test 演示）的完整切片，只是"面向玩家可玩"这层是下一张票的责任。
2. **Prefactor 先行**：`01` 号票（房间级/NPC 级能力自描述注册表）被提到 Wave 0 最前面，即使 spec 把它写在"H1"（块 H，场景内容之前的收尾说明）。理由：spec 原文明确说"以便块 A~G 陆续落地时，每一块只需要往对应注册表追加一条，不产生新的 Shotgun Surgery"——这句话的动作时机就是"块 A~G 落地**之前**"，不是"落地之后回头整理"。若不提前做，块 B/C/E/F 会先各自手改 `scene_loader.py` 的 `_ROOM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS`（散改），之后再搬进注册表就是二次改动同一批代码——这正是 to-tickets 技能"look for opportunities to prefactor…make the change easy, then make the easy change"的字面场景。
3. **依据真实技术依赖排序，不是照抄 spec 的块字母顺序**。spec 自己在"Further Notes"里给的建议顺序（A→B→C→D→E/F→G→H）是内容主题分组，不是严格的技术依赖图。拆票时发现至少两处明显偏离：
   - **`learn` 命令跨块依赖**：spec 把 `learn` 写在块 B（角色成长），但 Implementation Decisions「E1」明确说"`learn <技能类型>` 命令解析流程：先查玩家 `Faction.faction_id` 对应的 `FactionDefinition.map_skill`"——`learn` 事实上依赖块 E（门派框架）才能完整工作。拆票时把 `learn`（`14` 号票）单独拆出、放在门派框架（`08` 号票）之后，而不依赖它的 `practice`（`13` 号票）则更早、与 `learn` 解耦并行。
   - **坐骑购买跨块依赖**：spec 用户故事 47"向马夫 NPC buy 一匹坐骑"字面上用的是 `buy` 这个块 D 的动词，意味着坐骑获取机制事实上依赖块 D（金钱与商店）。`10` 号票（坐骑与骑乘）因此排在 `07` 号票（货币与商店）之后，不是像 spec 字面顺序那样"块 F 独立于块 D"。
4. **每张票都在正文里点名验收会消费哪些真实文件/函数/组件**（如"复用 `run_vetoable`/`Deny`""与 `attach_ai_system` 同构"），而不是泛泛复述 spec 段落——这是应用户"深度细致严谨"要求做的选择：牺牲一点"票据的时效稳定性"（未来重命名会让票据里的引用过时），换取"下一个 /implement session 不需要重新读一遍 spec 就能定位到具体该改哪里"的可执行性。这与 to-tickets 骨架"避免具体文件路径，因为会过时"的一般建议有意冲突——冲突的理由是：本仓库的架构模式高度稳定且反复被 M1 票据引用（`attach_xxx`/`register_xxx`/`CAPABILITIES` 这套命名法已经用了 30+ 张 M1 票没有改名），过时风险低，而"票据本身要独立可执行、下一 session 不需要重新探索代码库"的收益更高。

## 关键设计决策 / 已解决的歧义

spec 里有几处没有把"怎么实现"钉死到能直接拆票的程度，本次拆票时做出以下具体决策（供 `/implement` 阶段直接采纳，不需要重新讨论；如后续实现时发现行不通，按各票 Comments 记录变更）：

1. **H1 房间级/NPC 级能力注册表的模块组织**：spec 没规定新注册表放哪个文件。决策：允许实现阶段自由选择"扩展现有 `capabilities.py`"还是"新增 `room_capabilities.py`/`npc_capabilities.py`"，只要求 `CapabilitySpec` 形状与物品能力保持一致（见 `01` 号票）。不强制拆文件，避免过早引入"三个几乎一样的模块"这种形式主义分割。
2. **全局声明式注册表（`SKILLS`/`FACTIONS`）不强制共享 helper**：`03` 号票（SkillData）与 `08` 号票（FactionDefinition）都是"顶层 YAML 段 -> 全局字典"模式，但只有两个消费者，按 Fowler "Duplicated Code" 的经验法则，两次重复通常可接受、不必为此拆共享抽象（三次才是强烈信号）。两张票都建议"复用同一种写法"但不强制提取公共函数，留给实现者按手感决定——如果 M3 UGC 层还会新增第三个"顶层全局注册表"（如效果/物品模板），那时再回头抽取才是合适的时机（YAGNI）。
3. **坐骑购买机制**：spec 用户故事 47 说"buy 一匹坐骑…成为该坐骑的主人"，但 Implementation Decisions「F1」定义的 `Mount` 组件没有 owner 字段，只有 `ridden_by`。这是 spec 内部叙事文案与机制设计之间的一处未言明张力。决策（记在 `10` 号票）：**不实现真正的所有权校验**，"成为主人"在 MVP 只是叙事措辞；机制上坐骑购买后出现在玩家当前房间、立即可 `ride`，`ride` 命令不检查"是不是你买的"（对齐 spec Out of Scope 明确排除的"坐骑被抢/被盗"——如果不校验所有权，被抢被盗这个概念本来就不存在，两处结论互相印证，说明这个决策符合 spec 精神而非绕开它）。`10` 号票要求实现阶段把最终选定的具体命令形状（是否复用 `buy` 还是新增专属命令）写进 Comments，供 `23` 号票（马厩场景内容）对齐，不留歧义到内容票再现场发明。
4. **昏迷态下的行为限制不提前实现**：spec 用户故事 23"昏迷状态下无法行动"，但 `06` 号票（死亡状态机核心）刻意**不**要求接入 `attack`/`go` 等命令的行为限制检查——因为在 `06` 号票落地的阶段，`Unconscious` marker 还没有任何真实触发源（战斗要到 `12`/`17` 号票才能让气血归零）。提前给命令加"检查 Unconscious"的分支会是没有真实调用者的死代码，且 `17` 号票（死亡流程 wiring）本就需要重新审视这条限制该加在哪些命令上——决策是把这条行为限制明确放进 `17` 号票的隐含范围（本 notes 记录，`17` 号票正文虽未逐字重复，但 `/implement` 时应视为其"死亡流程执行"验收的自然延伸：昏迷中的玩家至少不能再发起新的 `attack`/`flee`）。**如果 `/implement` 到 `17` 号票时发现这条还没被覆盖，应在该票内补，不要另开新票**。
5. **60a–60c 同名消歧范围**：spec 60c 自己列了两档并"推荐先做最小档"。决策：`20` 号票严格只做 `ask`+`attack` 两个命令的序号消歧，明确排除"全命令 present 等价"（`get`/`look`/`drop` 等）——因为后者要与 `Stackable` "同名合并"语义并存的复杂度评估还没做，强行现在做会让 `20` 号票膨胀成一个需要先做设计探索的票，不符合"tracer bullet 单票可在一个新 context window 完成"的尺寸要求。若未来需要，应该是 M2 之后一张独立的、有自己设计前提的新票，不追加进 `20` 号票。
6. **场景内容按"分区"而非"单一大票"拆分，且刻意让扬州拆成两张**：[10 号票](../../mvp-scope/issues/10-mvp-scenes-selection.md) 定稿的扬州"丰富子集"多达 15 个房间（1 广场 + 4 街 + 4 门 + 6 商业地标），一张票覆盖不完（违反"单票可在一个新 context window 完成"）。拆成 `22`（枢纽+城门，纯导航+消歧验收）与 `23`（商业地标+马厩，交易+坐骑购买验收）两张，两者共用 `yangzhou_*` 房间键命名空间，票据正文互相提醒协调，避免键冲突。少林寺（5 个房间）与野外+官道+渡口（概念上是一条"沿途"而非"独立城市"）体量较小，各自一张票即可。
7. **场景内容票的"批次分组"早于其严格技术依赖**：`21`/`23`/`24` 严格意义上部分依赖只到 Wave 2 就已解除（如 `23` 只需 `07`/`10`），比 `22`/`25` 的依赖闭合得早。但 [implement-plan.md](implement-plan.md) 仍把全部场景内容票统一分进 Wave 4，理由：(a) 内容作者写场景时即使某个机制不是硬依赖，也经常想引用"隔壁机制"让内容更真实（如少林场景作者可能想顺手引用 `practice` 展示成长曲线）；(b) spec 自己的治理止损线（[07 号票](../../mvp-scope/issues/07-governance-cost-tracking.md)）建议"块与块之间是天然的重估检查点"，场景内容统一批次审查比零散穿插审查更符合这条治理精神；(c) 六个分区最终要拼成一张连通图（`26` 号票），提前统一批次能减少房间键协调的往返成本。**如果用户希望最大化并行度**，`23` 可以提前到 Wave 2 结束就开工，不必等 Wave 3 全部收尾——[implement-plan.md](implement-plan.md) 里对此有单独标注。

## 与 spec 块字母的映射（供回溯）

| spec 块 | 覆盖票据 | 备注 |
|---|---|---|
| A（战斗引擎地基） | `02`, `12`, `16` | 纯函数核心 / 真实接线 / 钩子实际生效，拆成三层 |
| B（角色成长） | `03`, `05`, `13` | SkillData 地基 / 组件+status/skills / practice；`learn` 因跨块依赖挪到块 E 之后（见上表决策 3） |
| C（死亡与轮回） | `04`, `06`, `17`, `18` | Spawner 修复 / 状态机核心 / 玩家死亡流程 / NPC 死亡流程，四层拆分 |
| D（金钱基础） | `07` | 单票覆盖，体量适中 |
| E（门派/阵营框架） | `08`, `11`, `14` | 框架+join / EntryGuard+GateContext / learn 完整实现 |
| F（坐骑与交通） | `09`, `10`, `15` | 渡船 / 坐骑与购买 / 地形限制，注意 `09` 渡船其实不依赖坐骑，先做 |
| G（NPC 战斗行为+Spawn 修复+消歧） | `04`（spawn 部分提到 Wave 0）, `18`, `19`, `20` | 消歧（60a–60c）与 aggro 按 spec 60c 建议保持相对独立 |
| H（六类场景内容落地） | `01`（H1 提前到 Wave 0）, `21`–`26` | 注册表基础设施提前；六分区+互联收口 |

## 未纳入本次拆票范围（明确排除，与 spec Out of Scope 对齐）

以下项目**不**对应任何票据，理由已在各自 spec 段落说明，本次拆票不重复展开，只做清单式确认，避免遗漏后续被误当作"漏拆的票"：完整阴间世界叙事、PvP 相关内容、武林大会与竞技系统、婚姻系统、完整 21 门派内容（框架之外）、多币种/订阅/账本抽象、完整护甲/武器槏位继承系统、多人混战/威胁列表、尸体腐烂/坐骑驯服/坐骑被抢被盗、受限 Python 沙箱与 UGC 创作工具、`resolve_attack` riposte 步骤的具体机制（骨架保留调用点，`02` 号票已确认为 no-op）。
