Status: ready-for-agent

# M2 — MVP 场景端到端可玩：战斗/技能/状态/死亡轮回 + 金钱/门派/坐骑交通 + 六类场景

> 依据：[CLAUDE.md 架构不变量](../../CLAUDE.md) 全 8 条，尤其第 4 条（子系统四档归类）、第 7 条（MVP 场景清单）；[ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)（不做行为等价）、[ADR-0002](../../docs/adr/0002-engine-workspace-greenfield-reset.md)（绿场重写）、[ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md)（战斗/效果引擎边界，"骨架固定 + 钩子策略注入"手法，本 spec 的核心技术输入）；[.scratch/mvp-scope/](../mvp-scope/) 全部 10 票，尤其 [07-governance-cost-tracking](../mvp-scope/issues/07-governance-cost-tracking.md)（M2 里程碑定义："一个 MVP 场景端到端可玩"）、[08](../mvp-scope/issues/08-subsystem-classification-research.md)/[09](../mvp-scope/issues/09-subsystem-classification-confirm.md)（子系统四档归类，本 spec 覆盖的 12 个 MVP 必做子系统均出自这里）、[10-mvp-scenes-selection](../mvp-scope/issues/10-mvp-scenes-selection.md)（场景清单定稿：华山村+扬州+少林寺+野外+官道+渡口+坐骑）。技术地基是 [M1 spec](../m1-core-engine-skeleton/spec.md) + [M1 spec-extension](../m1-core-engine-skeleton/spec-extension.md) 已落地的引擎骨架（ECS World、EventBus、TickLoop、条件求值器、transfer 原语、能力组件注册表、YAML 场景加载器），M2 在其上按同一套接缝手法（ADR-0004 三要素：声明式 policy 枚举 + Protocol 钩子 + 注册表注入）扩展，不重新设计已验证过的机制。LPC 源码与旧架构文档（`docs/archive/xkx-arch/`）仅作设计灵感与术语参考，不是规格源（ADR-0001）。
>
> **范围确认（写在此处供后续 `/to-tickets` 阶段核对，非阻塞）**：本 spec 覆盖 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 定稿的全部 MVP 场景清单与 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 列出的这批场景所需的全部 12 个 MVP 必做子系统（角色、金钱基础、门派武学框架、战斗、状态、技能、坐骑与交通、死亡与轮回、NPC-AI 扩展，另加已在 M1 落地的标准命令/房间继承/数据存储/命令调度）。这是 [07 号票](../mvp-scope/issues/07-governance-cost-tracking.md) 定义的完整 M2 里程碑范围，规模明显大于 M1（M1 骨架落地成 36 张实现票）；`/to-tickets` 阶段大概率需要按下文的 A~H 分块拆成数十张票，且 07 号票的"进度类止损线"（单票超预估 3 倍强制重估）在这个规模下更容易触发，实现阶段应按块（而非整体一次性）交付验收。

## Problem Statement

M1 骨架 + 扩展已经跑通"空场景 + 命令-移动-存档"与"物品/静态 NPC/Nature/事件钩子地基"，但还没有任何题材内容能撑起一次完整的武侠游玩体验：没有战斗、没有技能、没有角色成长、没有死亡代价、没有货币与买卖、没有门派归属、没有坐骑与跨区域交通。[10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 选定的六类场景（新手村、城镇、门派、野外、官道、水陆交通）目前只是"空房间图"的候选骨架，缺了驱动它们变得可玩的核心系统，玩家进去除了走路、看看、捡东西之外无事可做，也无法验证 [ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md) 拍板的战斗/效果引擎边界在真实内容压力下是否成立。M3（UGC 创作闭环）更是无从谈起——UGC 创作者需要一套"机制归引擎、内容归题材包"的接缝范式可参照，而目前这套范式只在非战斗系统（门/物品/NPC/Nature）验证过，战斗/技能/状态/死亡这条 ADR-0004 已定边界的路径还没有一行实现代码。

## Solution

在 M1 引擎骨架之上，按 ADR-0004 的接缝手法（骨架固定 + 钩子策略注入）落地八块相互咬合的能力，每块内容都遵循"机制/流程归引擎，数值/文案/具体设定归题材包（本 spec 同时也在写这份 MVP 武侠题材包的默认内容，两者在这次 spec 里一并交付）"：

- **块 A（战斗引擎地基）**：ADR-0004 已定的七步管线（`resolve_attack` 纯函数）+ AP/DP 概率判定结构 + `PowerModel` 策略注入口 + `SkillBehavior` Protocol 钩子，挂 tick 驱动的自动交战循环（`attack` 命令建立交战关系，后续回合由心跳自动结算，`flee` 可尝试脱离）。
- **块 B（角色成长）**：资源/属性/技能等级组件拆分（气血/内力/精力两层资源 current/max + 力量/根骨/敏捷/智力四维基础属性 + 技能等级/经验表）+ 技能声明式数据（`SkillData` 注册表，招式/等级需求/消耗）+ `practice`/`learn` 学习命令。
- **块 C（死亡与轮回）**：昏迷→死亡两段判定状态机 + 免死区域（`NoDeathZone`）豁免 + 死亡惩罚/复活流程（`DeathPolicy` 策略）+ 击杀奖励，且顺带修复 [PROGRESS.md](../../PROGRESS.md) 与 `ai.py` 已标注的 `_spawn_scan` 坑（模板全灭后扫描失效）。
- **块 D（金钱基础）**：单一货币组件 + NPC 商店 `buy`/`sell`（直接复用 M1 已埋的 `Valuable.value` 占位字段作价格）。
- **块 E（门派/阵营框架 + 少林题材内容）**：`Faction` 声明式注册表（技能池、`map_skill` 映射、加入条件）+ 房间级身份/装备门槏（`EntryGuard` 组件复用 M1 已有的 `on_before_enter_room` 事件点，不新增机制）+ 少林山门/武场/达摩院内容。
- **块 F（坐骑与交通）**：坐骑（`Mount`/`Riding` 组件，资源消耗从骑手转移到坐骑）+ 地形通行难度（`Terrain.cost` vs `Mount.ability`）+ 渡口渡船（复用 M1 已有的"运行时可增删出口"机制，本 spec 是它的第一个真实题材用例）。
- **块 G（NPC 战斗行为 + Spawn 修复）**：`Behaviors` 新增 `aggro` kind（复用块 A 的交战建立逻辑，不新起一套）+ 把低频 Spawn/Reset 扫描从"聚合存活实例"改为"模板注册表驱动"，修复模板全灭后扫描失效的坑 + **同名目标序号消歧**（对齐 LPC `present("id N")`，至少覆盖 `ask`/`attack`；见用户故事 60a–60c 与「范围修订记录」2026-07-20）。
- **块 H（六类场景内容落地）**：华山村（新手教程）+ 扬州丰富子集（商业/城镇）+ 少林寺（门派）+ 野外（遭遇）+ 官道（跨区域连接）+ 渡口（水陆交通）六类场景的具体 YAML 内容，以及为承载这些内容对场景 DSL 已知字段集的扩展（延续 M1 "能力自描述注册表" `CAPABILITIES` 的模式，不散改多处）。

## User Stories

### 块 A：战斗引擎地基（ADR-0004 落地）

1. 作为终端玩家，我想输入 `attack <目标>`（别名 `kill`）对同房间的 NPC 发起战斗，以便开始一场对抗。
2. 作为终端玩家，我想一旦双方进入交战状态，后续回合由引擎心跳自动结算（每条命令推进 1 tick 即触发一轮），不需要每回合重复输入 `attack`，以便体验持续对抗而不是每回合手动催促引擎。
3. 作为终端玩家，我想每一回合收到清晰的战斗播报（命中/闪避/招架/伤害数值/招式名/剩余气血提示），以便判断战斗走向决定是否撤退。
4. 作为终端玩家，我想输入 `flee` 尝试脱离交战（可能失败并挨一次攻击），以便在打不过时有主动撤退的选择。
5. 作为引擎开发者，我想战斗结算实现为 `resolve_attack(ctx: CombatContext) -> CombatRoundResult` 纯函数，严格按 ADR-0004 已定的七步顺序（选技能 -> 取招式 -> 算 AP/DP -> dodge 判定 `random(ap+dp)<dp` -> parry 判定 `random(ap+pp)<pp` -> 算伤害 `hit_ob`/`hit_by` 回调 -> inflict（扣减气血/触发昏迷判定） -> exp+riposte），以便能脱离 tick/command 调度独立构造 `CombatContext` 快照直接测试，不依赖整条命令管线。
6. 作为引擎开发者，我想 AP/DP 概率判定的**结构**（`random(ap+dp)<dp`、`random(ap+pp)<pp`）是引擎不变量，但 AP/DP 具体怎么从属性/技能/装备算出来的**求值公式**由 `PowerModel` 策略对象决定（Protocol，题材包可整体替换），以便非武侠题材未来替换掉这条近战公式而不用碰七步骨架。
7. 作为引擎开发者，我想默认 `PowerModel` 实现是一个自洽、可测试的武侠公式（基础属性 + 技能招式 `force`/`dodge` 字段组合），不追求还原 LPC 原始 `skill_power` 公式（ADR-0001 不做行为等价），以便这份公式本身就是 MVP 武侠题材包要交付的内容之一。
8. 作为引擎开发者，我想每个技能招式可选声明 `SkillBehavior` 钩子（`hit_ob`/`hit_by`/`post_action`，对应 ADR-0004 的 Protocol），多数招式只填 `SkillData` 数值不实现钩子，只有"命中后触发中毒""被击中后触发招式特效"这类需要额外副作用的招式才实现钩子，以便"数值型招式"与"带特殊效果的招式"共用同一套调度而不强制每个招式都写 Python 代码。
9. 作为引擎开发者，我想战斗结算按 `CombatContext` 快照（战斗开始时或每回合开始时对参战双方状态的一份只读快照）+ 可注入的 seeded RNG 求值，以便单回合结算是确定性、可独立断言的（不是"整场战斗行为对齐 LPC"，只是"给定同一份输入两次求值结果一致"，不违反 ADR-0001）。
10. 作为终端玩家，我想 MVP 阶段战斗是 1 对 1（一名玩家/NPC 同一时刻只与一个对手交战），以便战斗规则简单、易理解；多人混战/威胁列表（`ThreatTable`）留给后续里程碑（见 Out of Scope）。
11. 作为引擎开发者，我想战斗回合结算挂在 `on_tick` 上（复用 M1 已有的事件总线，不新起驱动机制），类似 `ai.py` 的 `AIController` 遍历模式：每次 tick 遍历所有处于交战状态的实体对，跳过已经因死亡/脱离而失效的交战关系，以便"随时间推进的世界演化"这条边界（M1 spec 用户故事 17）在战斗系统上保持一致——`attack`/`flee` 命令只负责"建立/尝试解除交战关系"这个一次性状态变更，不直接执行伤害结算。
12. 作为引擎开发者，我想战斗事件点（`on_before_combat_round` 可否决、`on_combat_round`、`on_combat_end`）挂在 `world.events` 上，空挂调用不影响 MVP 默认行为，以便未来"某状态下无法战斗""战斗结束时触发门派特殊奖励"这类规则有挂载点，不需要回头改战斗调度接口。
13. 作为引擎开发者，我想交战关系用一个组件表达（如 `Engaged(opponent: EntityId)`，双方各挂一份互相指向），而不是散落的临时变量或字典，以便存档能正确恢复"战斗进行中"这一状态（运行时可变进存档）。

### 块 B：角色成长（属性、资源、技能）

14. 作为终端玩家，我想输入 `status` 查看自己当前的气血/内力/精力（各自 当前值/上限）与四项基础属性（力量/根骨/敏捷/智力），以便掌握自己的战斗与体力状态。
15. 作为终端玩家，我想输入 `skills` 查看自己已学会的技能及各自等级/经验进度，以便规划下一步该练什么。
16. 作为终端玩家，我想向门派技能 NPC 输入 `learn <技能>` 学习一门新技能（需满足门派归属/前置属性等条件，条件不满足给出明确原因），以便加入门派后有实际收益。
17. 作为终端玩家，我想输入 `practice <技能>` 消耗内力/精力练习已学会的技能以换取经验，达到经验门槏后自动升级并收到提示，以便有目标感地提升角色实力。
18. 作为引擎开发者，我想把"资源"（气血/内力/精力，每种 当前值/上限 两层）与"基础属性"（力量/根骨/敏捷/智力）与"技能等级表"拆成三个独立组件（`Vitals`/`BaseAttributes`/`SkillLevels`），不做成一个跨领域字段大杂烩组件，直接对应 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 对"角色系统"的归类理由（"双层生命值这套具体属性维度要重新设计成题材包可配置的属性系统，而不是硬编码武侠数值"）与 M1 spec 已定的组件拆分标准（复用性，不是字段数）。
19. 作为引擎开发者，我想资源模型只做"当前值/上限"两层（不做 LPC 的三层 `current/eff/max`），状态系统需要"临时降低上限"这类效果时直接修饰 `max` 字段本身（Effect 生效时减、失效时还原），以便模型保持简单，不为 MVP 用不上的第三层预先增加复杂度（不过度设计）。
20. 作为引擎开发者，我想技能内容按 ADR-0004 定的三层组织：`SkillData`（YAML 声明式数据：技能名/类型/等级需求/招式列表，招式含 `force`/`dodge`/伤害类型/可选固定伤害值）是一个**全局技能注册表**（类似 M1 的 `CAPABILITIES` 注册表模式，不是挂在 entity 上的组件）+ 可选 `SkillBehavior`（Python 钩子，块 A 已定义）+ 战斗时动态派生的 `SkillEffect`（技能命中触发的状态，块 C/未来效果系统消费），以便 UGC 创作者未来只编辑 `SkillData` 就能新增技能，不用碰 Python。
21. 作为引擎开发者，我想技能学习条件（`valid_learn`：门派归属/前置技能等级/基础属性门槏）用块 A 地基（M1 扩展块 A）已有的条件求值器表达，不写散落的 if 比较，以便学习限制规则与门/物品/NPC 行为规则共用同一条件子语言。
22. 作为引擎开发者，我想练习消耗（内力/精力）与经验获取、升级门槏都是纯数据参数（技能声明的字段，不是硬编码常量），以便题材包/UGC 调整成长曲线不需要改引擎代码。

### 块 C：死亡与轮回

23. 作为终端玩家，我想气血耗尽时先进入"昏迷"状态（无法行动，等待自然恢复或被治疗，一定时间后自动醒来），而不是立刻死亡，以便有一次容错空间。
24. 作为终端玩家，我想昏迷状态下若继续受到攻击（且不在免死区域），会真正死亡：物品掉落在死亡地点、损失部分经验/技能等级/金钱作为惩罚，随后在指定复活点满状态复活，以便死亡有实质代价但游玩能继续。
25. 作为终端玩家，我想擂台/教学切磋等标记为"免死区域"的房间里，即使气血耗尽也只会昏迷不会真正死亡，以便在安全场景里放心切磋。
26. 作为终端玩家，我想击杀一个 NPC 后获得经验与掉落的金钱/物品奖励，以便战斗有正向反馈。
27. 作为引擎开发者，我想死亡状态机（存活 -> 昏迷 -> 死亡 -> 复活 -> 存活）是引擎机制，但惩罚比例、复活点房间、掉落规则是 `DeathPolicy` 声明式参数（题材包配置），对应 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 对"死亡与轮回系统"的归类理由与 [ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md) "流程归引擎、数值归题材包"的边界。
28. 作为引擎开发者，我想免死区域用一个独立的房间级 marker 组件（`NoDeathZone`）表达，不塞进已有的 `Description`/`Container` 等组件（这条能力与"户外/天气展示"是完全不同的语义关注点，不内聚，不应该塞进同一个组件），以便未来"某类特殊地形免死"的判定逻辑清晰、单一来源。
29. 作为引擎开发者，我想死亡/复活流程挂 `on_before_death`（可否决，供免死道具等未来规则用）/`on_death`/`on_revive` 事件点，空挂调用不影响 MVP 默认行为，以便未来引入复活道具、门派特色死亡增益（如 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 提到的丐帮特色）时不需要改死亡状态机接口。
30. 作为引擎开发者，我想修复 `ai.py` 的 `_spawn_scan` 已标注的已知缺口（"若某 template 实例全灭，template_key 从存活实例聚合的 metas 里消失，扫描无法发现缺口"）：把"该模板期望多少实例、如何重建一个新实例"从"聚合当前存活实例的 `NpcSpawnMeta`"改为"场景加载时注册的独立模板蓝图注册表"（`world.spawners: dict[str, SpawnerBlueprint]`，运行时态、不进存档，与 `world.nature`/`world.ai` 同构），以便单例 NPC（如某个门派的教学 NPC，`desired_count=1`）死亡后扫描仍能发现缺口并补齐，这是 [PROGRESS.md](../../PROGRESS.md) 明确点名的 M2 复核点。
31. 作为终端玩家，我想标记为 `respawn` 的 NPC 死亡后经过一段时间会在其出生房间重新出现（外观/对话与原实例一致，不带上一实例累积的任何状态），以便野外遭遇怪物、门派守卫等可持续刷新的 NPC 类型能长期支撑游玩。

### 块 D：金钱基础

32. 作为终端玩家，我想持有一种货币（银两），可以通过击杀 NPC、完成交易获得，也可以通过购买物品消费，以便有一个贯穿游玩的资源目标。
33. 作为终端玩家，我想向城镇里的商店 NPC 输入 `buy <物品>` 花钱购买一件物品到我的物品栏（余额不足时明确提示），以便获取装备/消耗品。
34. 作为终端玩家，我想向商店 NPC 输入 `sell <物品>` 卖出我物品栏里的物品换取银两（商店按折扣价收购），以便处理不需要的物品换取资源。
35. 作为引擎开发者，我想货币是一个最小的 `Currency` 组件（单一货币，整数余额），不做多币种/订阅/账本抽象（那是 [06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md) 的商业化支撑点，明确"MVP 不要求实现"），对应 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 对"金钱系统"拆分的结论（基础持有/交易归 MVP，完整商业化设计归后续）。
36. 作为引擎开发者，我想 `buy`/`sell` 直接复用 M1 已经埋好的 `Valuable.value` 字段作为物品的基准价格（`buy` 按 `value` 收费，`sell` 按 `value` 乘以商店折扣率收购），不新增一个平行的"价格"字段，以便验证 M1 "先埋钩子、按需消费"的设计确实在 M2 兑现了。
37. 作为引擎开发者，我想商店的售卖清单是 NPC 声明式配置（一组物品模板引用 + 可选独立折扣率），`buy` 从清单模板按需实例化物品（而不是商店库存被买空后就没了——MVP 商店库存不设上限，这是刻意简化），以便商店内容可以直接在 YAML 里配置，不需要额外的库存管理机制。

### 块 E：门派/阵营框架 + 少林题材内容

38. 作为终端玩家，我想走到少林寺山门时，若我的身份（性别/是否已属其他门派/所持武器类型等场景声明的具体条件）不满足要求，会被明确告知原因并无法进入寺内，以便体验到"门派对身份有讲究"这一武侠世界观特色。
39. 作为终端玩家，我想在满足条件时向知客僧 NPC 表示要拜师（`join 少林` 或对应命令），成功后我的门派归属变为少林，以便获得学习少林专属技能的资格。
40. 作为终端玩家，我想在少林武场向武僧 NPC `learn` 少林专属技能（如罗汉拳），以便体验门派技能池与门派身份绑定这一机制。
41. 作为终端玩家，我想能探索达摩院、藏经阁这类剧情向房间（有描述、有展示型 NPC，但没有特殊交互机制），以便少林寺场景有叙事纵深，不只是"学技能的地方"。
42. 作为引擎开发者，我想门派/阵营是一个声明式全局注册表（`FactionDefinition`：门派 id、展示名、加入条件、技能池、`map_skill` 映射表），角色身上只挂一个轻量 `Faction(faction_id: str | None)` 组件引用它，对应 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 对"门派武学系统"的归类结论（"引擎层要做成阵营/流派通用框架，21 门派的具体内容仍由 MVP 题材包层直接落地"）——本 spec 落地这个通用框架，同时也落地少林这一个具体门派的内容。
43. 作为引擎开发者，我想房间级身份/装备门槏用一个新组件 `EntryGuard`（挂在需要校验的目标房间上：条件表达式 + 拒绝文案）表达，由一个内置的 `on_before_enter_room` 订阅者统一检查 `to_room` 是否挂了 `EntryGuard`（复用 M1 已有的可否决事件点，不新增移动/进入机制），以便"进入某个房间需要满足身份条件"这条能力天然可以被其他场景（密室、试炼关卡）复用，不专属于少林山门。
44. 作为引擎开发者，我想条件求值器（块 A 地基）在校验 `EntryGuard` 时构造一个 `EntityGateContext`（对发起移动的玩家实体动态计算出场景需要查询的属性：如 `faction_id`/`gender`/`is_wielding_edged_weapon`），复用已有的 `Predicate`/`Equals` 条件节点，不扩展条件语言语法（依赖倒置：`evaluate()` 只认协议不认具体类型，`EntityGateContext` 与 `NatureState` 实现 `ConditionContext` 协议同构），以便"进入门槏"这类实体级校验与"时辰/天气"这类世界环境校验共用同一套条件求值机制。
45. 作为引擎开发者，我想 `gender`（性别）作为一个独立的最小组件（`Gender(value: str)`，题材包决定取值集合，引擎不做枚举校验），可选挂在玩家/NPC 身上，以便未来技能学习限制、门派限制等多处场景都能复用这一个字段，不用各自专属建模。
46. 作为引擎开发者，我想 `map_skill`（门派把通用技能类型映射到具体招式集，如"内功"->少林"混元一气功"）是 `FactionDefinition` 的声明式数据字段，供 `learn`/`practice` 在解析"玩家所属门派下这个技能类型对应哪个具体技能"时查询，以便同一句 `learn 内功` 在不同门派归属的玩家身上落地到不同的具体技能，不需要每个门派各写一套学习命令分支。

### 块 F：坐骑与交通

47. 作为终端玩家，我想在扬州城的马厩向马夫 NPC `buy` 一匹坐骑（消耗银两，成为该坐骑的主人），以便获得骑乘能力。
48. 作为终端玩家，我想输入 `ride <坐骑>` 骑上我拥有的坐骑、`unride` 下来，骑乘状态下移动描述与移动效率都会体现"骑着走"，以便体验坐骑带来的机动性收益。
49. 作为终端玩家，我想骑乘时移动主要消耗坐骑自身的精力而不是我的精力，坐骑精力耗尽会昏迷、把我摔下来（自动解除骑乘关系），以便"骑马代步"这条机制有清晰的代价（坐骑需要休整/喂养，不是无限资源）。
50. 作为终端玩家，我想某些路况较差的地形（如野外/需要更高通行能力的路段）我的坐骑通行能力不够时无法骑着通过，需要下马步行，以便体验"不是所有坐骑都能走遍天下"这条设计。
51. 作为终端玩家，我想官道与野外沿途一条河流处有渡口，需要等渡船到岸才能过河（渡船按固定周期往返两岸），以便体验水陆交通这一 MVP 场景清单明确要求的内容。
52. 作为引擎开发者，我想坐骑是一个挂了 `Mount`（通行能力 `ability` + 自身精力 `current`/`max`）组件的实体，复用现有 `Identity`/`Description`/`Position`/`Container`（坐骑也能"背东西"）组件模型，不新起一套平行的坐骑对象类型，对应 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 里"坐骑与交通系统"改判为 MVP 必做但仍要求"坐骑种类等题材内容留给题材包配置"的结论。
53. 作为引擎开发者，我想骑乘关系用双向可选引用表达（骑手身上的 `Riding(mount_id)` + 坐骑身上 `Mount.ridden_by` 字段），移动时坐骑跟随骑手同步换房间（不需要坐骑自己走一遍出口判定），以便骑乘期间"人和马一起移动"这件事的实现足够直接。
54. 作为引擎开发者，我想房间通行难度是一个新的房间级组件 `Terrain(cost: int, 默认 1)`，`go` 命令在玩家处于骑乘状态时额外校验 `Terrain.cost <= Mount.ability`（不满足时拒绝进入并提示"这地方骑不过去"，玩家可以先 `unride` 再走），不满足条件本身不是错误、是正常的地形限制，以便这条通行校验可以直接对照 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 里"官道/野外可骑乘通行"的场景要求实现。
55. 作为引擎开发者，我想渡口渡船机制直接复用 M1 已经落地的"出口表运行时可增删"能力（04 号票），不新增一套连接机制：渡口房间挂一个 `Ferry`（对岸房间引用 + 往返周期 tick 数）组件，一个挂在 `on_tick` 上的系统按周期在两岸房间的出口表里增删"过河"这一条 `Exit`（渡船不在时该方向没有出口，尝试过河会得到"渡船不在对岸"的提示；渡船到岸时出口出现，可以正常 `go` 过河），以便验证这条 M1 阶段就设计好的机制在真实题材内容里确实成立（这是它的第一个真实用例）。
56. 作为终端玩家，我想在渡口房间 `look` 时能看到渡船当前在哪一岸/还有多久到达的提示文案，而不是无声地等出口出现或消失，以便理解"为什么这个方向现在没有路"。

### 块 G：NPC 战斗行为 + Spawn 修复

57. 作为终端玩家，我想在野外（扬州郊外森林）遭遇到会主动攻击我的 NPC（如山贼/野兽），进入房间后一定条件下自动被攻击进入战斗，而不需要我先手 `attack`，以便体验"野外不安全"这一 MVP 场景清单要求的遭遇验证内容。
58. 作为引擎开发者，我想主动攻击行为是 `Behaviors` 组件新增的一种 `BehaviorSpec.kind`（`"aggro"`），复用块 A 已经定义的"建立交战关系"逻辑（不是攻击行为自己另起一套伤害结算入口），触发条件（如"房间内有未处于交战状态的玩家"）用已有的条件求值器表达，以便 Chatter 与 Aggro 这两种行为共用同一个 `AIController` 遍历骨架，新增行为类型不需要改 tick 调度框架。
59. 作为终端玩家，我想被野外 NPC 击败（NPC 获胜）后按块 C 的死亡流程处理（昏迷/死亡，非免死区域），而不是有任何特殊的"野外死亡"分支，以便死亡规则在整个世界里保持一致。
60. 作为引擎开发者，我想 NPC 死亡（气血耗尽）不走玩家的"昏迷->等待复活"流程，而是直接消失并掉落战利品（金钱/物品），复活/重生走块 C 已修复的 spawner 注册表机制（如果该模板声明了 `respawn`），以便"玩家死亡有代价可复活"与"NPC 死亡是一次性事件、由独立的重生机制负责补齐"这两条不同语义的流程不混在一起。
60a. 作为终端玩家，我想在同房间有多名同名 NPC（如城门两名「官兵」、`count: 2` 的巡逻兵）时，用 **`ask <名> <序号> about <话题>`** / **`attack <名> <序号>`** 指到第 N 个实例（1-based，空格分隔，对齐 MudOS/FluffOS `present("id N")`），以便扬州城门等多实例守卫场景可玩，而不必给每个克隆起不同显示名。
60b. 作为引擎开发者，我想目标匹配结果落到**具体实体**（`EntityId`），而不是仅规范名字符串：M1 的 `Intent.target: str` + `_find_npc_in_room` 按名取第一个无法区分同名实例；实现时需扩展 `match_target`（或 NPC/战斗专用匹配）支持 token 末尾序号，并让 `ask`/`attack`（及后续 `give` 等）的 Intent/执行层携带实体引用。
60c. 作为引擎开发者，我想 `/to-tickets` 时评估两档范围并拆票：（1）**最小**：仅 `ask` + `attack` 的同名序号；（2）**全命令 present 等价**：物品 `get`/`look`/`drop` 等同名非堆叠也走同一套（注意与 Stackable「同名合并」语义并存）。默认推荐先做（1）；无序号且多命中时**保留** M1「不确定你指的是哪个」提示（比 LPC 静默取第 1 个更友好），有序号则消歧。灵感出处：LPC `cmds/std/ask.c` 的 `present(dest, env)` + driver `object_present2`；房间例 `d/city/nanmen.c` 的 `npc/bing : 2`。不做行为等价（ADR-0001），只借机制形状。

### 块 H：六类场景内容落地

61. 作为终端玩家，我想在新手出生点（华山村）遇到一位教程向导 NPC，通过 `ask` 对话了解基础命令（移动/查看/拾取/战斗）与去向指引（去扬州闯荡还是投奔某个门派），以便新手玩家有明确的上手路径。
62. 作为终端玩家，我想华山村里能进行一次简单的战斗教学（如一个不会反杀的稻草人/教学木桩 NPC，`attack` 后能看到完整的战斗播报流程），以便在低风险环境里理解战斗系统怎么玩。
63. 作为终端玩家，我想扬州城有中央广场（枢纽）、四条大街、四座城门、客栈、钱庄、打铁铺、镖局、武庙、茶馆这些 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 定稿的地标房间，每个房间有符合其功能的 NPC/商店/描述，以便老玩家能找到记忆中的地标、新玩家能感受到城镇的商业氛围。
64. 作为终端玩家，我想扬州的钱庄/打铁铺能实际 `buy`/`sell` 东西（不是纯装饰房间），以便验证块 D 的金钱系统确实落地在场景里而不是抽象存在。
65. 作为终端玩家，我想少林寺场景包含山门（身份门槏）+ 广场 + 达摩院/藏经阁（剧情向）+ 武场（技能学习）+ 武僧/知客僧 NPC，覆盖 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 定稿的少林场景要求，以便门派归属/学技能这条主线完整可玩。
66. 作为终端玩家，我想扬州与少林之间有一段野外（森林遭遇区）与一条官道相连，官道与野外允许骑乘，中途有渡口，以便体验"从新手村到城镇到门派"这条地理路径是连贯、可跨区域探索的，而不是几个互不相连的孤岛场景。
67. 作为引擎开发者，我想为承载以上内容对场景 YAML 已知字段集做的每一处扩展（房间的 `cost`/`no_death`/`entry_guard`/`ferry`，NPC 的 `faction`/`gender`/`vitals`/`attributes`/`skills`/`shop`/`mount`，新的 `factions:`/`skills:` 顶层段），都遵循 M1 已经验证过的模式：新增一条自描述规格（对照 `CAPABILITIES` 注册表 `CapabilitySpec` 的形状：YAML 解析 + 已知字段集 + 存档序列化/反序列化）,不散改 `scene_loader`/`save.py` 好几处,以便块 A~G 陆续落地时,每一块只需要往对应注册表追加一条,不产生新的 Shotgun Surgery。

## Implementation Decisions

**七步管线与 `CombatContext`（A1，最核心）**

- `resolve_attack(ctx: CombatContext, rng: Random) -> CombatRoundResult` 是一个纯函数，输入战斗双方的只读快照（气血/内力/属性/当前招式候选）与一个可注入的随机数源，输出本回合的结构化结果（命中/闪避/招架/伤害数值/是否致命/招式名/文案片段），不直接读写 `World`。调用方（tick 系统）负责把结果 apply 回真实组件状态（扣血、触发死亡判定、生成播报消息）。这个纯函数边界让"给定同一份 `CombatContext` 快照两次求值结果一致"这条测试可以完全脱离 tick/命令管线独立断言，与 M1 扩展的条件求值器、M1 骨架的 `match_target` 属于同一类"核心算法直测" seam。
- `CombatContext` 只是一份快照（不是活引用），战斗系统在每回合开始时从 `World` 现读现算构造，不缓存跨回合的快照（避免快照与实时状态不同步）。
- AP/DP 判定结构（`random(ap+dp)<dp` 闪避、`random(ap+pp)<pp` 招架）是引擎不变量，直接照抄 ADR-0004 已拍板的形状，不重新论证。

**`PowerModel` 策略与默认武侠公式（A2）**

- `PowerModel` 是一个 Protocol：给定攻击者的 `BaseAttributes` + 招式的 `force` 字段 + 装备加成，返回 AP；给定防御者的 `BaseAttributes` + 招式的 `dodge` 字段，返回 DP/PP。挂在 `World`（或全局注册表）上，MVP 提供一个默认实现（`DefaultWuxiaPowerModel`）：AP = 招式 `force` 值 × (1 + 力量修正系数)，DP = 防御方敏捷 × 系数 + 招式 `dodge` 值。具体系数是纯数据常量，不追求任何还原度（ADR-0001），只要求"确定性、可测试、数值上打得动"。
- `PowerModel` 通过 `register_power_model(power_model)` 挂到 World 运行时态（与 `attach_ai_system`/`attach_nature` 同构：一个 `attach_xxx` 函数，纯内存不进存档，场景加载时按需 attach，缺省用默认实现）。

**`SkillBehavior` 钩子与技能三层（A3/B1）**

- `SkillData` 是一个**全局注册表**（`SKILLS: dict[str, SkillData]`），从 YAML 顶层新段 `skills:` 加载（不是挂在 entity 上的组件），每条含：技能类型（如 `martial`，对照 LPC 术语参考，不强制枚举）、等级需求、招式列表（每招 `force`/`dodge`/`damage_type`/可选固定 `damage`/`lvl` 门槏/招式展示文案）。这与 M1 的 `CAPABILITIES` 注册表是同一种"自描述规格列表"模式，供 `scene_loader`（已知字段集）与战斗系统（结算时查表）共用。
- `SkillBehavior` 是可选的 Protocol 实现，按技能 id 注册（`register_skill_behavior(skill_id, behavior)`，与 `commands.register`/M1 扩展的 `register_condition` 同构），暴露 `hit_ob(ctx, damage) -> int | str | None`（命中后，可修改伤害数值或追加文案）/`hit_by(ctx) -> None`（被击中后触发副作用，如反击）/`post_action(ctx) -> None`（招式结算完成后的收尾）。MVP 少林技能池里的普通招式（罗汉拳基础招式）不实现钩子，只有需要额外效果的招式才实现。
- 角色身上的 `SkillLevels` 组件只存"这个角色学会了哪些技能、各自等级/经验"，具体招式内容永远从全局 `SKILLS` 注册表按 id 查，不复制到角色组件上（避免技能内容更新后要逐个角色同步）。

**资源/属性组件拆分（B2）**

- `Vitals(qi_current, qi_max, neili_current, neili_max, jingli_current, jingli_max)`：三种资源，两层（当前/上限）。气血耗尽触发块 C 昏迷判定；内力不足时无法使用需要内力的招式/练习；精力不足时无法 `practice`、也是坐骑消耗的资源类型参照（坐骑自己的 `Mount` 组件另开字段，不共用玩家的 `Vitals`）。
- `BaseAttributes(str_, con, dex, int_)`（力量/根骨/敏捷/智力，字段名避开 Python 关键字加下划线，展示文案用中文）：影响 `PowerModel` 默认公式与负重上限（可选：负重上限计算复用 `con`，MVP 若时间紧可以先跳过负重与属性联动，只联动 `PowerModel`，这条留给实现阶段按块 A 优先级决定）。
- `SkillLevels(levels: dict[str, SkillProgress])`，`SkillProgress(level: int, exp: int)`。升级门槏（"这个等级需要多少 exp"）是 `SkillData` 声明的一个字段（如分级门槏表或简单公式参数），不是硬编码在 `practice` 命令里。

**死亡状态机与免死区域（C1，最重要的新状态机）**

- 新增 marker 组件 `Unconscious`（挂即"昏迷中，无法执行会触发交战/移动的命令"，运行时可变进存档）与 `Dead`（挂即"死亡，等待复活流程处理"，同样进存档，这是"崩溃后重启仍处于死亡待复活"这一边界情况要求的）。存活状态用"两个组件都不挂"表达，不新增一个 `Alive` marker（避免三态用两个独立布尔表达产生非法组合，"两者都不挂"天然就是唯一的"存活"态）。
- 判定流程：气血耗尽时，检查当前房间是否挂 `NoDeathZone`——挂了则只进入 `Unconscious`（不管是否已经昏迷过，免死区域反复昏迷是允许的）；没挂则检查是否已经处于 `Unconscious`（这是"昏迷中又被击中"这一条件，对应两段式判定的第二段）——是则转 `Dead` 并触发死亡流程，不是则先转 `Unconscious`（第一段，给一次容错机会，此时不掉落东西不惩罚）。
- 死亡流程（转 `Dead` 时立即执行，不等待额外命令）：分发可否决的 `on_before_death`（M1 默认无 handler 即放行）；按 `DeathPolicy` declarative 参数把玩家当前物品栏物品转移到死亡房间的地面容器（`transfer` 原语，复用 M1 已有机制，不新写一套物品转移）；按惩罚比例扣减金钱/技能经验（不扣到负数，下限截断）；移除 `Dead`/`Unconscious`，把 `Position` 设为复活点房间，把 `Vitals` 恢复满值；分发 `on_revive`。玩家侧死亡到复活是同一次流程内直接完成（MVP 不做"停留在死亡状态等待玩家操作"这一步，也不做完整阴间世界叙事，见 Out of Scope）。
- `DeathPolicy` 是纯数据参数（惩罚比例、复活点房间 key、是否掉落金钱），场景加载时可声明，缺省给一份 MVP 默认值（复活点默认华山村）。

**Spawner 注册表修复（C2，PROGRESS.md 点名的复核项）**

- 新增 `SpawnerBlueprint`（重建一个 NPC 实例所需的全部数据：`Identity`/`Description` 字段、`startroom`、可选 `Inquiry`/`Behaviors`/`tick_interval`/`Faction`/`Vitals` 等，本质是"NPC 模板"的完整快照）与 `world.spawners: dict[str, SpawnerBlueprint]`（运行时态，纯内存不进存档，与 `world.nature`/`world.ai` 同构，由 `scene_loader` 在建 NPC 时顺带注册，重启后由 `load_scene` 重新填充）。
- `_spawn_scan` 改为遍历 `world.spawners`（不再从 `entities_with(NpcSpawnMeta)` 反向聚合）：对每个 `template_key`，统计当前存活实例数（仍然是查 `NpcSpawnMeta.template_key` 匹配的实体，只是"期望值"来自独立注册表而非从存活实例本身推断），不足且 `respawn=True` 时按 `SpawnerBlueprint` 重建缺口数量的新实例。这样即使某模板（如 `desired_count=1` 的单例门派 NPC）实例全灭，`world.spawners` 里的记录依然存在，扫描能正确发现缺口——这正是 `ai.py` 现有代码注释点名的坑。

**货币与商店（D1）**

- `Currency(amount: int)`，挂在需要持有货币的实体上（玩家、掉落金钱的 NPC 死亡时的战利品来源、商店 NPC 若要表达"钱庄本身也有余额"可选挂，MVP 商店 `sell` 不做"钱庄钱不够收不了"的限制，简化为商店余额无限）。
- `ShopInventory(entries: tuple[ShopEntry, ...])`，`ShopEntry(item_template_key: str, resell_discount: float = 1.0)`：NPC 声明式配置，`item_template_key` 引用场景 `items:` 段里的一个物品模板（`buy` 时按模板实例化一份新物品，不是从某个共享池子里搬运已存在的物品实体）。价格直接读被实例化物品的 `Valuable.value`（未声明 `Valuable` 的物品不能被 `buy`/`sell`，视为配置错误在加载期报错，不是运行时静默失败）。

**门派/阵营框架（E1）**

- `FactionDefinition(faction_id, display_name, join_condition: Condition | None, skill_pool: frozenset[str], map_skill: dict[str, str])` 是全局注册表（`FACTIONS: dict[str, FactionDefinition]`，从 YAML 新顶层段 `factions:` 加载），角色只挂 `Faction(faction_id: str | None)`。`join_condition` 复用块 A 地基条件求值器（M1 扩展块 A），求值时用 `EntityGateContext`（见下）。
- `learn <技能类型>` 命令解析流程：先查玩家 `Faction.faction_id` 对应的 `FactionDefinition.map_skill`，把技能类型映射为具体技能 id（映射不到则提示"你的门派不会这个"），再查该技能 id 是否在该门派 `skill_pool` 内、`SkillData` 的等级/属性门槏是否满足（不满足给出具体缺什么），全部通过才学会并写入 `SkillLevels`。

**房间级门槏与 `EntityGateContext`（E2，条件求值器的新用法，不改语法）**

- `EntryGuard(condition: Condition, deny_message: str)` 挂在需要身份/装备校验的目标房间上（如少林山门内侧房间）。内置一个 `on_before_enter_room` 订阅者（引擎自带，非空挂占位——这是块 A 地基事件点在 M2 的第一个真实消费者）：检查 `to_room` 是否有 `EntryGuard`，有则构造 `EntityGateContext(faction_id=..., gender=..., is_wielding_edged_weapon=...)`（从发起移动的玩家实体读取 `Faction`/`Gender`/物品栏物品类型现算出来的**只读快照**，不是活引用），调 `conditions.evaluate`，不满足则 `Deny(deny_message)`。
- 这条设计的关键是**不扩展条件求值器语法**：`EntityGateContext` 与 `NatureState` 一样，只是新实现一份 `ConditionContext`（或其扩展协议）的具体类，`Predicate`/`Equals`/`And`/`Or`/`Not` 五种节点原样复用，`evaluate()` 函数不需要改一行。`EntityGateContext` 暴露哪些属性由场景实际需要的校验维度决定（MVP 少林山门用到 `faction_id`/`gender`/`is_wielding_edged_weapon` 就只暴露这三个），不追求"一份大而全协议覆盖所有可能校验"——这是刻意的不过度设计，未来新场景需要新的校验维度时再加属性（同 `ConditionContext` docstring 已经声明的增量扩展精神）。
- `Gender(value: str)` 是一个独立最小组件（题材包决定取值集合，引擎不校验枚举），可选挂在玩家/NPC 身上；"是否持有某类武器"通过物品的一个新最小标签组件 `ItemTags(tags: frozenset[str])`（如 `{"weapon", "edged"}`）现算得出，不新建专属的"武器类型"枚举字段。

**坐骑与骑乘（F1）**

- 坐骑本质是一个挂了 `Mount(ability: int, jingli_current: int, jingli_max: int, ridden_by: EntityId | None = None)` 组件的普通实体，复用 `Identity`/`Description`/`Position`/`Container`（坐骑能驮东西）。场景 YAML 的 `npcs:` 段新增 `mount:` 字段声明这些参数（复用现有 NPC 建造管线，不新起一个 `mounts:` 顶层段——坐骑在对象模型上就是"一种特殊的 NPC 展示物"，这与旧 LPC `NPC_TRAINEE` 继承坐骑的设计思路一致，见 [10-坐骑与交通系统](../../docs/archive/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/10-坐骑与交通系统.md)，仅作术语/设计灵感参考，不做行为等价）。
- `Riding(mount_id: EntityId)` 挂在骑手身上；`ride`/`unride` 命令互相设置/清除 `Riding.mount_id` 与对应 `Mount.ridden_by`，双向保持一致。`go` 命令处理骑乘玩家的移动时，若玩家有 `Riding`，额外同步把对应坐骑实体的 `Position` 也改到同一个新房间（"人马一起移动"，坐骑不单独走出口判定）。
- 移动消耗：骑乘状态下移动，扣减坐骑的 `jingli_current`（扣减量 = 目标房间 `Terrain.cost` 的一个数据驱动系数），不扣玩家自己的 `jingli_current`。坐骑 `jingli_current` 归零时转入类似块 C 的"昏迷"态（复用 `Unconscious` marker，不新建平行的"坐骑昏迷"状态类型），同时强制解除骑乘关系（骑手被"摔下来"，双向 `Riding`/`Mount.ridden_by` 清空），移动结算正常完成（玩家步行完成本次移动，只是失去了坐骑的加速收益，这与"摔下来"的直觉一致）。
- 地形限制：`Terrain(cost: int = 1)` 挂房间；`go` 命令在玩家处于骑乘状态、且目标房间 `Terrain.cost > Mount.ability` 时拒绝移动并提示，不处于骑乘状态则不受此限制（步行永远不受地形通行能力限制，只是可能慢——MVP 不做"步行也有速度差异"，移动始终是"一步到位"的单次操作，速度差异只体现在坐骑消耗与是否能通行上）。

**渡口渡船（F2，动态出口机制的首个真实用例）**

- `Ferry(far_bank: EntityId, cross_interval: int, direction: str)`：挂在渡口房间上（两岸各挂一份，`far_bank` 互相指向对方），声明"过河"这个方向名与渡船往返周期（tick 数）。场景加载时不预先建立这条 `Exit`（两岸初始互不连通）。
- 一个挂 `on_tick` 的系统（与 `nature.py`/`ai.py` 同构：`FerryState` 运行时态列表挂 `world.ferries`，不进存档，由 `attach_ferries` 在场景加载后挂载）按周期翻转"渡船在哪一岸"：渡船到达 A 岸时，往 A 岸房间的 `Exits` 增加一条指向 B 岸的 `Exit`（`direction` 字段声明的方向名，如 `"across"`），移除 B 岸对应的那条（渡船不能同时停靠两岸）；到达 B 岸时反过来。
- 渡口房间的 `look` 输出追加一行渡船状态提示（复用 `Description` 追加机制的思路，但渡船状态是运行时衍生值不是静态文案，因此在 `_cmd_look` 里对挂了 `Ferry` 的房间额外查 `FerryState` 现算一行文案，不塞进 `Description` 组件本身——遵循"启动固定数据 vs 运行时派生值不混进同一组件"的三态标注精神）。

**NPC 主动攻击行为（G1）**

- `BehaviorSpec` 新增 `kind="aggro"` 一支：字段复用 `when`（触发条件，条件求值器表达，如"房间内存在未处于交战状态的玩家"这一判断本身由 handler 内部现算，不是 `Predicate` 能直接表达的"存在量词"，因此 `when` 这里校验的是更简单的场景级开关条件，如"仅白天""仅野外"，"是否已有可攻击目标"由 handler 逻辑本身负责扫描，不硬塞进条件语言）。触发时调用块 A 已经定义的"建立交战关系"共享函数（与 `attack` 命令共用同一个底层函数，类似 `room_say` 被 `say` 命令与 Chatter 行为共用的模式），不是 NPC 自己发起一个新的攻击判定路径。
- 触发目标选择 MVP 简化为"房间内第一个符合条件（未在交战状态）的玩家"，不做威胁值/仇恨列表（`ThreatTable`，见 Out of Scope）。

**场景 DSL 扩展的注册方式（H1，防止 Shotgun Surgery 重演）**

- 延续 M1 `capabilities.CAPABILITIES` 的模式：块 B~G 每新增一个需要 YAML 声明的能力（`Vitals`/`BaseAttributes`/`SkillLevels`/`Currency`/`ShopInventory`/`Faction`/`Gender`/`ItemTags`/`Mount`/`Riding`/`Terrain`/`Ferry`/`NoDeathZone`/`EntryGuard`），都在对应的能力注册表里追加一条自描述规格（YAML 解析 + 已知字段集 + 存档序列化/反序列化三元组），不再各自散改 `scene_loader.py`/`save.py` 的多处已知字段集合与 codec 字典。房间级能力（`Terrain`/`NoDeathZone`/`EntryGuard`/`Ferry`）与 NPC 级能力（`Vitals`/`Faction`/`Mount`/`ShopInventory`）分别对照 M1 已有的 `_ROOM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS` 扩展方式，物品级新增（`ItemTags`）走已有的 `CAPABILITIES` 列表本身（它已经是这套模式）。
- `factions:`/`skills:` 是两个新的顶层段（与 `rooms:`/`items:`/`npcs:`/`player:` 平级），需要加进 `_TOP_LEVEL_KNOWN_SECTIONS`；这两段本身不建实体，只填充全局注册表（`FACTIONS`/`SKILLS`），供后续 `npcs:`/`player:` 段的 `faction:`/`skills:` 字段按 id 引用校验（引用不存在的门派/技能 id 在加载期报 `SceneLoadError`，不是运行时静默失败——延续 M1 已定的"加载期数据校验，不是运行时崩溃恢复"边界）。

**六类场景内容组织（H2）**

- 六类场景（华山村/扬州/少林寺/野外/官道/渡口）落地为**同一份场景 YAML 文件**里的房间集合（沿用 M1 单文件场景格式，不引入"多文件场景拼接"这个额外机制——MVP 阶段一份不算太大的 YAML 完全够用，多文件拼接留给 M3 UGC 需要多个题材包并存时再设计），房间键按场景分区命名前缀（如 `huashan_*`/`yangzhou_*`/`shaolin_*`/`wild_*`/`road_*`/`ferry_*`）避免键冲突，出口把六个分区连成一张连通图（华山村<->扬州东门一段官道<->野外<->渡口<->少林方向官道<->少林山门）。
- 具体地标房间数量与摆设（扬州"丰富子集"具体到哪几段街、少林具体几间厢房）由实现阶段按 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) Answer 里已经拍板的清单逐条落地（中央广场+四条大街各至少一段+四座城门+客栈+钱庄+打铁铺+镖局+武庙+茶馆；山门+广场+达摩院/藏经阁+武场+武僧/知客僧），不在本 spec 重复枚举，直接以该票文本为验收清单。

## Testing Decisions

- 延续 M1 确立的测试 seam 分层，不新增测试基础设施：
  - **纯函数直测**：`resolve_attack`（给定构造好的 `CombatContext` + seeded RNG，断言 `CombatRoundResult` 的命中/伤害/是否致命）、`PowerModel` 默认实现（给定属性/招式数值，断言 AP/DP 计算结果）、死亡判定的两段式状态转移函数（给定当前状态 + 是否免死区域 + 是否已昏迷，断言下一状态）——这些是"给定输入两次求值结果一致"的确定性算法，不依赖 `World`/tick/命令管线，直接构造参数调用。
  - **命令层 seam**（`execute_line` / `commands.execute`）：`attack`/`flee`/`ride`/`unride`/`buy`/`sell`/`learn`/`practice`/`join`/`status`/`skills` 等新命令的输入输出断言（给定一行命令，断言返回消息与状态变更），与 M1 现有 11 个命令的测试模式一致。
  - **tick 层 seam**（`TickLoop.advance` / `world.events.dispatch(ON_TICK, ...)`）：战斗自动回合结算、坐骑精力消耗与昏迷、渡船周期翻转出口、Spawn/Reset 扫描补齐、NPC aggro 触发，这些"随时间推进"的行为都通过反复调用 `advance()`/直接 `dispatch` 若干次 tick 断言状态变化，不通过命令间接触发。
  - **条件求值器契约测试延伸**：`EntityGateContext` 补一份类似 `NatureState`/`StubContext` 的契约测试（`isinstance(ctx, ConditionContext)` 或其扩展协议成立），确保新 Context 实现与已有协议形状兼容，不需要新写一套断言方式。
- 场景 YAML 内容（六类场景的具体房间/NPC/物品）用一份端到端"剧本式"测试覆盖关键路径（新手教程对话 -> 前往扬州 -> 买卖 -> 前往野外遭遇战斗 -> 前往少林拜师学技能 -> 骑马走官道 -> 过渡口），断言玩家在这条路径上每一步的可观察输出（消息/状态查询结果），不断言场景 YAML 文件本身的内部结构（内容正确性交给这条端到端剧本，不是逐字段快照测试）。
- `SpawnerBlueprint`/Spawn 扫描修复需要一条专门测试复现 [PROGRESS.md](../../PROGRESS.md) 点名的坑：`desired_count=1` 的 NPC 死亡后（该模板存活实例归零），断言下一次 `_spawn_scan` 仍能发现缺口并补齐（旧实现在这个场景下会因为 `template_key` 从聚合结果里消失而静默跳过，这条测试专门锁死这个回归）。

## Out of Scope

- **完整阴间世界叙事**（黑白无常剧情、隐藏还阳路径、鬼门关物品销毁等完整流程）：死亡与轮回只落地"昏迷/死亡两段判定 + 惩罚 + 复活点满状态复活"这一引擎机制层，不做完整阴间世界内容——阴间叙事本身属于 [08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 判为"themed 治理/题材化叙事细节"的部分，MVP 不需要它才能验证死亡机制成立。
- **PvP 相关内容**：击杀玩家的惩罚/奖励差异化、通缉机制、路口冲撞 PK、反刷死亡安全机制（`death_count` 强制移监）——MVP 全部场景按 PvE（对 NPC）设计，PvP 涉及的额外治理层（fail-closed 惩罚系统）留给后续里程碑。
- **武林大会与竞技系统**：[08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 判"现代化改造"，非 MVP 必做。
- **婚姻系统**：非 MVP 必做，未在 [10 号票](../mvp-scope/issues/10-mvp-scenes-selection.md) 场景清单里出现。
- **完整 21 门派内容**：本 spec 只落地少林一个门派 + 通用门派框架；框架落地后新增其他门派应该是"纯数据配置"工作量，不需要改引擎代码（这正是验证框架设计是否合格的标准）。
- **多币种/订阅/账本抽象/消费埋点/世界实例隔离**：[06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md) 明确"架构支撑点，MVP 不要求实现"，本 spec 只做单一货币最小闭环。
- **完整护甲/武器槏位继承系统**（9 种槏位、专属击中特效）：[08 号票](../mvp-scope/issues/08-subsystem-classification-research.md) 判"可选"，非 MVP 必做；本 spec 的 `ItemTags` 只满足"门槏校验需要识别武器类型"这一最小需求，不是完整装备系统。
- **多人混战/威胁列表（`ThreatTable`）**：MVP 战斗简化为 1 对 1，`MAX_OPPONENT`/仇恨值排序等留给后续需要真实群怪场景时再引入。
- **尸体四阶段腐烂、坐骑驯服（`train`/`tame` 野外驯服机制）、坐骑被抢/被盗**：MVP 坐骑只做"向马夫购买"这一条获取路径，驯服与坐骑归属纠纷留给后续。
- **受限 Python 技能钩子沙箱、UGC 可编辑 `SkillData`/`FactionDefinition` 的创作工具**：`SkillBehavior`/`FactionDefinition` 本 spec 是**受信任题材包开发者**写的 Python/YAML（对齐 CLAUDE.md 架构不变量第 3 层"题材包"权限级别），不是 UGC 沙箱层，UGC 创作闭环整体是 M3 范围（ADR-0001/架构不变量第 5 条）。
- **`resolve_attack` 七步中 riposte（反击）步骤的具体机制**：ADR-0004 骨架保留这个调用点，但 MVP 默认技能池不实现任何反击效果（该步骤对 MVP 招式是 no-op），避免为用不上的机制预先设计具体规则。

## Further Notes

- 本 spec 规模明显大于 M1（M1 骨架 36 张实现票覆盖的范围小于本 spec 任意两个块相加），`/to-tickets` 阶段建议按 A~H 块顺序分批拆票、分批验收，而不是一次性拆完全部再开始实现——这与 [07 号票](../mvp-scope/issues/07-governance-cost-tracking.md) 的进度类止损线（单票超预估 3 倍强制重估范围）配合，块与块之间是天然的重估检查点。建议实现顺序：块 A（战斗地基）→ 块 B（角色成长，战斗需要属性才能打）→ 块 C（死亡，战斗需要终局）→ 块 D（金钱，门派/坐骑都要花钱）→ 块 E/F（门派、坐骑交通，内容层）→ 块 G（NPC 主动攻击 + Spawn 修复 + **同名序号消歧 60a–60c**，需要战斗+死亡都先就位；消歧可与 aggro 并行拆票）→ 块 H（场景内容，最后把所有机制串成一条可玩路径）。
- 块 A~G 的每一处新机制都刻意对照 ADR-0004 三要素（声明式 policy 枚举 + Protocol 钩子 + 注册表注入）与 M1 已验证的具体模式（`CAPABILITIES` 自描述注册表、`register_xxx` 注册函数、`attach_xxx` 运行时态挂载、`ConditionContext` 协议扩展、事件点 `on_xxx` 命名），本 spec 没有引入任何一种新的"接缝形状"——这是刻意的：M1 spec-extension 已经验证过这套手法能从战斗系统（ADR-0004 原始范围）推广到非战斗系统（门/物品/NPC/Nature），本 spec 反过来验证它能撑起真正的战斗/技能/死亡内容，形成闭环。
- `EntityGateContext`（块 E）是本 spec 唯一"新增一种 Context 实现类型"而不是"复用已有具体类型"的地方，值得在实现阶段格外注意契约测试覆盖，防止未来第三种、第四种 Context 类型各自发明不兼容的协议形状。
- **同名目标消歧（60a–60c）**：扬州城门等多实例同名 NPC 是场景内容硬需求；M1 验证夹具已暴露缺口。优先做 ask/attack 最小档，全命令 present 等价作可选加码票，避免与 Stackable 合并语义纠缠。
- PROGRESS.md 的另一条 Next Up（"M3 前核对 [03-ugc-dsl-design-inheritance](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确"）不属于本 spec 范围——那是一个 M3 启动前的核对检查点，不是需要现在落地的实现内容，留在 PROGRESS.md 里按原计划推进。

## 范围修订记录

（本 spec 为一次性 `/to-spec` 综合会话产出，未经过多轮用户交互调整；若后续核对 seam/范围时有调整，记录在此。）

- **2026-07-20（M1 NPC 手测带回）**：默认场景 `count: 2` 巡逻兵暴露 M1 同名只能 `Ambiguous`、无法 `巡逻兵 2` 指代。用户确认：M1 只把手感 Chatter 概率降到约 5%；**同名序号消歧 / 全命令 present 等价推迟到本 M2**，挂块 G（用户故事 60a–60c），`/to-tickets` 时与 aggro/spawn 同批评估拆票。卡点备忘：`matching.Candidate` 现为 `(规范名, 别名)`；`Intent.target` 为规范名；执行层按名查找——必须升级到实体引用才能真正问到不同实例。
