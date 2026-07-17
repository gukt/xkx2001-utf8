# 模式研究·Agent协作创作架构（XKX MUD 重构为 Python+WebSocket UGC 平台）

## 概述
基于 XKX 的声明式内容模式（房间 exits 出口图、NPC dbase 键值属性、武功 action 数组、inquiry 对话映射、condition 状态机、attack 战斗循环），构建以 DSL 为契约层、MCP 为共享验证基底的 Agent 协作创作架构。协作模式采用编排者-工作者分工 + 生成-评审-修订循环 + 红蓝对抗验证；UGC 设世界观设计师/编剧/NPC行为作者/平衡测试/连贯性审查五角色；人机协作设创意意图、世界圣经、发布前三道审批门；创作资产以内容寻址+不变量回归保证可验证性，DSL 生成->沙盒执行->结构化指标反馈闭环驱动持续精炼，将 LLM 非确定性收敛到可验证终态。

## 模式
- **Orchestrator-Worker 专业化分工**：以 DSL 为契约层，将创作请求分解为独立子任务分发给专业化 Agent。导演 Agent 负责意图解析、任务划分与结果聚合；工作者 Agent 各自拥有聚焦的 system prompt 与输出 DSL 子集。映射到 XKX 代码库的实际声明式模式：房间 DSL（short/long/exits 出口图、outdoors、valid_leave 守卫，见 d/shaolin/wuxing3.c）、NPC DSL（dbase 键值属性 str/int/con/dex、max_qi、attitude、chat_msg、inquiry 对话映射、vendor_goods，见 d/shaolin/npc/xiao-ku.c）、武功 DSL（action 数组：force/dodge/damage/lvl/skill_name/damage_type，见 kungfu/skill/yuenu-jian.c）、condition DSL（65+ 状态类型如 poisoned/drunk/blind/jail，见 kungfu/condition/）。导演产出任务卡（含约束、引用实体清单、质量阈值），工作者产出对应 DSL 片段，交接边界由 schema 强约束。
  - 适用性：适用于任意 UGC 创作请求的初始分解，如'设计一个大航海时代港口走私剧情线'会被拆为港口地理、走私者/海关 NPC、剧情分支、船战平衡四个子任务并行分发。
- **生成-评审-修订循环（Generate-Review-Revise）**：工作者产出 DSL 草稿后，由对应的评审 Agent（不同于生成者，避免自我确认偏误）依据检查清单批评：剧情逻辑漏洞、数值越界、引用悬空、风格一致性。评审输出结构化缺陷列表而非自由文本，工作者据此修订，循环直至缺陷数低于阈值或达到迭代上限。关键是评审 Agent 不直接改写内容，只产出机器可解析的缺陷项（severity/location/expected/actual），使循环可收敛、可度量。映射到 XKX：评审可调用 combat-sim 工具对武功 action 数组做伤害曲线检查，调用 world-graph 工具对房间 exits 做可达性检查，调用 coherence-check 工具对 inquiry 对话引用的 NPC/物品做存在性校验。
  - 适用性：对质量敏感的结构化内容（剧情分支、NPC 对话树、门派设定）必用；对低风险模板化内容（纯描述性房间）可降级为单次生成+轻量校验以省成本。
- **红蓝对抗验证（Adversarial Red-Blue）**：引入破坏者 Agent 作为红方，目标不是创作而是'打破'内容：寻找不可达房间、死循环战斗、可绕过的任务前置、数值溢出/堆叠的 OP 连招、剧情分支死锁、经济刷取漏洞。蓝方（生成+修订 Agent）必须修复红方找到的所有 break。这与评审循环的区别在于：评审检查'是否符合规范'（静态），对抗验证检查'是否可被利用'（动态，需实际执行）。映射到 XKX：破坏者可构造极端 build（max_neili 堆叠 + 特定武功 combo）跑 combat-sim 探测伤害溢出；可走 world-graph 路径搜索寻找'未完成任务即获奖励'的捷径；可触发 condition 堆叠测试状态机鲁棒性。对抗验证通过 = 内容具备反脆弱性。
  - 适用性：发布前强制执行；高价值剧情线/经济系统/竞技 PvP 场景必须过对抗验证。低风险日常内容可豁免以控成本。
- **DSL 闭环反馈（Agent 生成 DSL → 执行 → 指标反馈 → 精炼）**：Agent 生成 DSL → schema 校验（快失败，结构错误零成本拦截）→ 沙盒实例编译为游戏对象（Python 后端实例化房间/NPC/skill）→ 执行模拟采集指标（可达率、平衡分布、完成率、连贯度）→ 指标结构化回传 Agent → Agent 据反馈精炼 DSL → 再校验执行，直至指标过阈值。闭环的核心是反馈必须是 Agent 可消费的结构化指标，而非人类评语。映射到 XKX：房间闭环指标=出口图连通性+无孤岛；NPC 闭环=由目标等级玩家战斗胜负比+掉落合理性；武功闭环=伤害分布曲线+无溢出；任务闭环=所有分支可达终态+无死锁。condition 闭环=状态可正常施加/解除/超时。这是把 LLM 的非确定性收敛到可验证终态的关键机制。
  - 适用性：所有可执行内容（房间/NPC/武功/任务/经济）必走闭环；纯叙事文案可仅做静态评审。
- **UGC 五角色矩阵**：(1) 世界观设计师 Agent：产出区域图、门派关系、历史时间线、经济设定（对应 REGIONS.h 区域映射与 d/ 目录组织）；(2) 编剧 Agent：产出剧情线、任务图、分支对话、inquiry 对话树（对应 set("inquiry",([...]))）；(3) NPC 行为作者 Agent：产出 attitude/chat_msg/random_move 调度/技能搭配/condition 触发，让 NPC 活而非静（对应 heart_beat 驱动的 chat/random_move/accept_fight）；(4) 平衡测试 Agent：跑 combat-sim/economy-sim，输出数值调参建议（对应 attack.c 的 enemy/killer 与 damage 计算）；(5) 剧情连贯性审查 Agent：跨实体交叉引用校验、时间线一致性、门派立场冲突检测。五角色通过 DSL 实体 ID 互相引用，审查 Agent 是横切的最后一道质量闸。
  - 适用性：新题材/新大区/核心系统设计时全角色参与；增量修补局部内容时仅唤醒相关角色，降低 token 成本。
- **多级人机审批门（Human-in-the-Loop Gates）**：三道审批门：(G1) 创意意图门——人类用自然语言描述题材/基调/规模，导演 Agent 据此产出创作蓝图，人类确认后解锁后续；(G2) 世界圣经门——世界观设计师产出区域/门派/经济/核心 NPC 骨架，人类签-off 后才允许编剧/NPC 作者在其上扩展（防止下游基于错误地基返工）；(G3) 发布前门——内容过完所有自动验证与对抗后，人类在沙盒中实际游玩走查，确认体验后发布到正式世界。门之间允许全自动化流水线高速运转，门本身是人工断点。映射到 XKX 的 wiz 分层（adm/arch/wiz/imm）权限模型：UGC 创作者对应 wiz 级，发布需 arch 级审批，形成人机协作的权限映射。
  - 适用性：创意意图/世界圣经/发布前为强制门；中间环节可设可选门（数量超阈值才唤醒人类），平衡自动化与可控性。
- **MCP 共享验证工具层**：将游戏世界操作封装为 MCP server，作为所有 Agent 共享的验证基底，避免各 Agent 各自硬编码校验逻辑。核心 server：world-graph MCP（查询/搜索房间出口图、找路径、检测孤岛与不可达）、combat-sim MCP（给定双方 build 跑 N 场模拟返回胜率/伤害分布/回合数，对应 attack.c 战斗循环）、npc-spawn MCP（沙盒实例化 NPC 跑脚本场景）、quest-runner MCP（执行任务走查所有分支终态）、schema-validate MCP（DSL 对 schema 校验）、coherence-check MCP（跨实体引用一致性：mentioned NPC/room/item 是否存在、时间线是否冲突）、economy-sim MCP（货币流通模拟）。Agent 通过工具调用获取结构化验证结果，而非靠 LLM 内省猜内容是否正确。这是把'听起来对'变成'可证明对'的关键。
  - 适用性：所有 Agent 共享此基底；新验证需求以新增 MCP server 形式横向扩展，不改 Agent 本身。MCP 使验证能力可组合、可复用。
- **内容寻址与不变量回归（Asset Verifiability）**：每件创作资产携带不可变清单：创作者 ID、参与的 Agent 角色、prompt 与 DSL 版本哈希、schema 校验结果、闭环 sim 指标快照、对抗验证记录。资产内容寻址（哈希即 ID）实现去重、可追溯、可回滚。建立世界不变量回归集（如：所有区域出口双向可达、任何 NPC 可被合理 build 击败、核心任务线全分支可完成、无经济刷取漏洞），每次内容变更回归全集，任一不变量破坏则阻断发布。映射到 XKX：8400 LPC 文件迁移为 DSL 后即形成基线回归集，后续 UGC 增量必须不破坏存量不变量。这保证海量协作创作下的世界整体可验证性，而非单点质量。
  - 适用性：正式世界资产强制启用；UGC 草稿/实验内容可降级为弱版本（仅 schema+sim，省 provenance 存储）。

## 适用性
- UGC 内容生成：新区域/门派/剧情线/NPC 群落的快速生产，DSL 为 Agent 间唯一契约
- 多题材扩展：从武侠迁移到大航海/书院/穿越/现代时，仅替换 DSL schema family + 角色约束，协作骨架不变
- 存量 LPC 迁移：用 Agent 将 8400 个 LPC 文件解析为 DSL 并入仓，Coherence Auditor 做迁移正确性验证
- 平衡性迭代：武功/经济/掉落数值调优，Balance+Breaker 跑 Monte Carlo 模拟驱动数据驱动决策
- 分布式运营：多租户世界各自运行 Agent 协作流水线，发布前统一过不变量回归

## 权衡
- 自治度 vs 可控性：Agent 自治越高创作越快，但质量越不可预测；审批门与对抗验证以速度换确定性，需按内容风险分级调节门密度。
- LLM 成本 vs 质量：多轮评审与对抗验证显著提升质量但 token 成本线性增长；低风险内容应走轻量路径（单次生成+schema 校验），把预算集中到高价值剧情线与平衡性。
- 通用性 vs 题材契合：通用 DSL 跨题材易扩展但可能牺牲武侠特有表达力（如经脉/内力/门派师承）；建议基础 schema 通用 + 题材 schema family 扩展，而非一刀切。
- 确定性 vs 创造性：可验证性要求确定（同输入同输出），但创意需要方差；解法是结构层确定性（schema/不变量）+ 内容层创造性（描述文本/剧情走向），分而治之。
- 集中编排 vs 涌现协作：单一导演 Agent 易实现但成瓶颈与单点故障；多 Agent 对等辩论更鲁棒但难收敛；建议默认集中编排，仅主观分歧处用辩论+裁决。
- MCP 工具完备度 vs 开发成本：工具越全验证越强但每个 MCP server 都需开发维护；应按缺陷发现频率优先实现高频工具（world-graph、combat-sim），低频工具按需补。
- 存量迁移保真 vs UGC 灵活：严格保真迁移会束缚 DSL 设计（为迁就 LPC 怪癖）；应允许迁移时规范化（如把 LPC 的 valid_leave 逻辑抽象为声明式 guard DSL），但记录偏差供审查。

## 推荐
- 以 DSL 为唯一契约层启动：先从 XKX 现有声明式模式（房间 exits 图、NPC dbase、武功 action 数组、condition 状态机、inquiry 对话）抽象出 wuxia DSL schema family，作为所有 Agent 产出的统一出口，schema 强约束使多 Agent 交接零歧义。
- MVP 先实现 Orchestrator-Worker + 生成-评审-修订循环两条主干，暂缓红蓝对抗与辩论，待主干稳定后再叠加对抗验证作为质量放大器（避免一次性铺太多模式难以调试）。
- MCP 工具层优先实现 world-graph（出口可达性）与 combat-sim（伤害/胜率）两个高频验证 server，它们能覆盖绝大多数内容缺陷，性价比最高。
- 存量 8400 LPC 文件用 Agent 解析为 DSL 入仓形成基线回归集，既验证 DSL 表达力是否完备（不能表达即 schema 缺陷），又为后续 UGC 增量提供不变量保护网。
- Human-in-the-loop 先只设'创意意图'与'发布前'两道门，'世界圣经门'在创作规模扩大后再引入，避免早期门过多拖慢迭代。
- 多题材扩展时复用协作骨架与 MCP 工具，仅新增 DSL schema family（nautical/academy/modern）与角色约束，验证架构对题材的无关性。
- 对抗验证从'武功数值溢出'与'任务绕过'两类高频漏洞切入，这两类在 XKX 攻击/任务系统中天然存在，收益直接、可快速证明价值。
- 资产 provenance 早期就内建内容寻址与清单，不要后补——后期海量 UGC 资产再补溯源成本极高，且无法追溯已发布内容。
