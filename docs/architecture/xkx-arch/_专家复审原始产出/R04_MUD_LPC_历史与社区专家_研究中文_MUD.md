# 专家复审·MUD/LPC 历史与社区专家（研究中文 MUD 文化 20 年，深度理解侠客行在中国 MUD 史的地位、文本美学、wizard 传统、玩家社交生态；担忧现代化丢失 MUD 的"灵魂"）

## 裁定
risky -- 技术架构现代化（ECS/Actor/DSL）扎实且经对抗验证修正后工程上可行，但在文化保真维度存在系统性盲区：把 MUD 当"技术系统"迁移而非"文化现象"延续，多个承载社区记忆与文本美学的"灵魂系统"要么被简化（代词 10 变量降 4、emote 7 视角降 3、天雷降为限流）、要么完全缺席（阴间/武林大会/vote 自治/法院审判/intermud 跨服），且 greenfield 框架下残留了增量重构假设（差分测试录制源、双栈过渡）。距"业界标杆"差的是文化保真策略，不是技术选型。

## 业界标杆评估
当前方案距业界标杆差一个完整维度：文化保真。技术架构现代化是 A 级，但对 MUD 作为"文化现象"的理解是 C 级--它把侠客行当"技术系统"拆解迁移，而非当"活的社区文化"延续。方案 5 份文档对阴间/武林大会/vote/法院/intermud 零提及，对代词体系简化为 4 变量 3 视角，对 wizard 文化降为运维 ACL，这是"技术上升级但文化上降级"的典型。真正能让它成为标杆的差异化能力是：以"世界观语言表达系统治理"为范式（天雷是 themed 反作弊、阴间是 themed 死亡惩罚、法院是 themed 反外挂、vote 是 themed 自治），加上 intermud 联邦协议演进为"可联邦的 UGC 多世界互联"。这是任何图形 MMO 都无法复制的"想象力治理元宇宙"。业界标杆应定位于"最 MUD 的现代游戏"--保留 themed 治理灵魂用现代技术放大其表现力与触达，而非"最现代的 MUD"--抽空文化灵魂换一层现代皮。两者的张力：技术现代化应服务于放大文本表现力与社区文化（如前端把 7 视角渲染做成即时切换的叙事 UI、把代词求值做成可视化称谓编辑器让 UGC 作者调），而非用工程简化抹平文化细节。标杆标准应加一条"文化保真度"：themed 系统的文本/行为/社区记忆迁移完整率，与差分测试行为保真并列为一等指标。

## 缺口
- **[high]** 代词体系实测是 10 个变量（$N/$n/$P/$p/$C/$c/$R/$r/$S/$s）而非方案反复声称的 4 个（$N/$n/$P/$p）。其中 $C/$c 是尊称、$R/$r 是尊称/贱称、$S/$s 是自称/贱称自称，全部由 RANK_D 的 7 个 query_ 函数动态求值。query_respect 依赖年龄（含容颜术减龄）、性别、职业（bonze/taoist/lama/fighter/eunach/officer）、官职（dali/rank 1-5）、武功等级（pixie-jian>160=督公）、善恶值、鬼魂状态。这不是纯渲染函数，是业务逻辑求值。方案'代词替换纯函数下移前端'的承重论断（00 总纲 §4.8、02 子系统9）在代词维度上不成立。
  -> 修复：服务端必须为每个事件的 me/you 预先求值 RANK_D 7 函数，产出结构化 PronounContext{name, pronoun, respect, rude, self, self_rude, close, self_close} 作为事件 payload 下发，前端只做 $X 到字段的纯字符串替换。RANK_D 的 7 个函数本身就是高价值迁移对象，须单独列为'称谓系统迁移'子任务，且其规则要进 ThemeRegistry（不同题材称谓不同）。
- **[high]** emote 系统实测是 7 视角变体（myself/others/target/myself_target/others_target/myself_self/others_self）而非方案假设的 3 视角（to_me/to_you/to_room）。例如 emote 'punish' 的 myself_self 是'$P的手背被胡子擦得酸痒'，others_target 是'$N拿起$n的手，在$p手背上连连亲吻'。7 视角覆盖了'发起者对自己''发起者对目标''旁观者看发起者对自己'等微妙叙事场景。方案 §4.8 的 render_message(template_key, actors)->{to_me,to_you,to_room} 丢了一半视角，等于阉割中文 MUD 文本表现力核心。
  -> 修复：渲染层契约扩展为 7 视角：render_emote(template, actors)->{myself, others, target, myself_target, others_target, myself_self, others_self}。message_vision 的 3 视角只是 emote 的子集。emote 数据迁移须保留全 7 字段，不可降级。
- **[medium]** emote 数据每条带 'updated' 作者署名字段（实测 20+ 位 wizard：fear/xbc/xuy/shan/sdong/marz/mongol/mantian/rover 等）。这是 wizard 创作文化的活化石--社区共创痕迹。方案的 provenance 体系（CPK author 字段）只考虑了 agent/人类作者，没把既有 8400 文件的 wizard 作者作为文化资产保留。UGC 平台继承了 wizard 创作传统却丢弃了其署名权。
  -> 修复：迁移时把 LPC 文件的 updated 字段、文件头注释的作者痕迹（如 //Cracked by Roath、// by Marz）作为 legacy provenance 回填到 CPK。provenance 模型支持 author.type='legacy_wizard'。这是文化保真而非技术需求。
- **[high]** 5 份文档对 5 个灵魂系统零提及（grep 验证）：① 阴间/轮回系统（d/death 13 房，鬼门关/地狱/死刑室，死亡 startroom 切换、clear_condition、block_cmd 屏蔽命令）；② 武林大会（d/bwdh 40+ 房，基于 localtime 墙钟触发的社区擂台竞技，sjsz 设施）；③ 玩家自治 vote 系统（cmds/std/vote + 2 子动作 chblk/unchblk，16 岁门槛、vote_suspension condition 剥权、滥用惩罚）；④ 法院审判反机器人（d/wizard/courthouse，审判官 NPC 三问极刑）；⑤ intermud 跨服网络（adm/daemons/network 41 文件，gchat/gwiz/gfinger/gtell/mail 跨 MUD 通信）。这些是 MUD 文化的骨架，不是边缘玩法。
  -> 修复：新增'灵魂系统盘点'前置环节：枚举所有 themed 社会治理/社区活动系统，逐一标注迁移方式。阴间系统是死亡流程的 themed 实现，必须作为 DeathSystem 的核心而非简化为'重生点'。武林大会是墙钟驱动的社区活动，TimeBasedEvent 系统必须覆盖。vote 自治是社区治理文化，SocialGovernance 子系统承载。intermud 需明确决策：保留联邦协议还是接受孤岛。
- **[high]** condition 系统的 72 个守护进程中，大量是非战斗的社会治理/生命周期状态机，方案将其统一归入 ConditionSystem（CombatSystem 同级的'玩法引擎'）是范畴错误。实测：killer（官府通缉，带 tell_object 文本'官府不再通缉你了'）、vote_suspension（剥夺投票权，'观察期已满，你又可以投票了'）、city_jail（监禁）、pregnant（怀孕）、biao/biaoju（镖师任务）、zuochan（坐禅）。这些 condition 携带社区可见的 themed 文本，是社会治理的体现，不是战斗 buff。
  -> 修复：condition 拆分为三类：CombatCondition（战斗状态：中毒/流血/眩晕）、SocialCondition（治理：通缉/监禁/剥权/通缉令）、LifecycleCondition（生命周期：怀孕/坐禅/睡眠）。各自的 on_tick 文本与社区可见性不同。ConditionHandler 组合返回值契约（§12）只解决了战斗维度的位聚合，治理 condition 的'期满解除并广播'语义需单独建模。
- **[high]** 天雷惩罚（feature/alias.c）被 §31e 识别为'业务级反作弊子系统'，但只说'保留 themed 惩罚语义'一句话，没设计其文本美学保留机制。实测天雷有 message_vision 的文学化文本（'忽然一声惊雷在你头顶炸开，震得你两耳欲聋！一道闪电从天降下，正劈在$N身上'）、unconscious（昏迷）、last_damage_from（死因标记'被天雷劈死了'）、log_file 审计。这是'以世界观语言表达系统治理'的范式--反作弊不显示为'你被封禁'而显示为'天雷劈下'。降级为限流丢失的是社区记忆与沉浸感。
  -> 修复：天雷惩罚应作为'ThemedPunishment'范式范例：保留 message_vision 文本、unconscious/death 语义、死因标记。抽象为 PunishmentPolicy（限流阈值->themed 文本->状态效果->审计），让 UGC 作者能定义自己题材的 themed 惩罚（大航海题材=海怪袭击、书院题材=戒尺责罚）。这是 MUD 独有的'想象力治理'，是标杆差异化。
- **[medium]** message 系统的子类过滤（channel/outdoor/weather）和 blind condition 的随机消息丢弃是状态依赖的渲染门控，非纯前端函数。feature/message.c 实测：outdoor 子类消息只在 query('outdoors') 房间可见；blind condition 时 random(blind*2)>0 随机丢弃消息（盲人'看'不到战斗描述）；block_msg/all 临时旗标屏蔽消息类。方案把渲染当下沉前端的纯函数，但这些门控依赖游戏世界状态（当前房间是否户外、玩家是否致盲、是否屏蔽消息），前端必须有等价状态才能正确门控。
  -> 修复：渲染门控契约化：服务端在事件 payload 附 msgclass 与门控上下文（outdoors/weather/blind_level/block_classes），前端按上下文执行门控。或更激进：服务端在发送时就按接收者状态过滤（每个接收者一个事件变体），前端只渲染。blind 的随机丢弃必须在服务端用 seeded RNG 保证三端一致。
- **[medium]** day_phase 不只是'轻量广播服务扇出'（§40f）。natured.c 的 update_day_phase 触发 event_sunrise（自动保存所有玩家 link_ob+body 数据）和 event_common（遍历 livings() 检查位置、清理无环境对象、把无环境玩家 move 到 wumiao）。这是与持久化系统和世界一致性维护耦合的全局事件，不是纯表现层广播。时段切换消息带 ANSI 颜色与文学化文本（'东方的天空中开始出现一丝微曦'），是沉浸感核心。
  -> 修复：day_phase 拆分为：世界时钟服务（墙钟驱动，全分片同步时段）+ 时段事件钩子（event_sunrise/event_common 等业务逻辑迁移为 WorldClockEvent 系统）+ 表现层广播（消息扇出）。明确 event_sunrise 的自动保存语义在新持久化模型中的等价物。时段文本进 ThemeRegistry。
- **[low]** wizard 文化（天后/女神/仙女/玄女等称号、updated 作者署名、法院审判 themed 反外挂）在方案中被降级为'运维侧 wizard ACL'（§19）和'简单角色门'。但 wizardp 不仅决定命令权限，还嵌入 query_rank 称号系统、courthouse 审判流程、securityd 审计。巫师身份是社区文化身份，不只是运维角色。用现代 RBAC 替代会丢失'天后/女神'这种社区记忆。
  -> 修复：分离'运维权限'与'文化身份'：运维权限用现代 RBAC（admin/operator），但 wizard 称号作为 legacy 文化称号保留进 ThemeRegistry 的 wuxia 称谓族。UGC 平台的'创作者'身份应继承 wizard 文化的仪式感（如审批通过授予 themed 称号），而非冷冰冰的 role。
- **[medium]** intermud 跨服网络（gchat 跨 MUD 闲聊、gwiz 跨服巫师频道、gfinger 跨服查询、跨服邮件 mail_serv/netmail）是 MUD 联邦文化的体现。新引擎作为 UGC 平台支持多题材世界，天然需要跨世界通信，却完全丢弃了 intermud 范式。这等于从'联邦公民'退化为'孤岛居民'。
  -> 修复：评估 intermud 协议现代化：新引擎的 EntityAddr（world://...）天然支持跨世界寻址。可设计 FederatedMessage 协议让不同 CPK 世界、甚至不同 MUD 实例互联。这是 UGC 平台的差异化能力（多世界联邦），不应在 0-1 就放弃。至少保留协议设计预留。

## 遗漏步骤
- 阶段 0 之前缺失'规格源实例搭建'步骤：差分测试需录制 LPC golden trace，但 0-1 全新项目无运行中的 LPC 系统。必须显式立项搭建可运行的 MudOS + XKX 实例（含修复 GBK/Big5 编码、加载 8412 文件、能承载录制脚本），作为规格源/录制源/对照基准。这一步工作量不小（MudOS 老旧、依赖古老工具链），未列入工时估算。
- 缺失'灵魂系统盘点'环节：迁移前必须枚举所有 themed 社会治理与社区活动系统（阴间/武林大会/vote/法院/intermud/emote 7 视角/RANK_D 7 函数/day_phase 事件钩子/condition 社会治理类），逐一标注迁移方式与文本保真要求。当前迁移面统计（68771 调用点）只数了技术调用面，没数文化系统面。
- 缺失'代词与称谓系统全量迁移'子任务：RANK_D 7 函数 + emote 10 变量 7 视角 + message_vision 3 视角是一整套文本表现力基础设施，应单独列为迁移子系统，而非散落在 ConditionSystem/CombatSystem。需建'称谓规则表'（性别×职业×门派×官职×年龄段×善恶->称谓）作为可配置数据。
- 缺失'intermud 跨服协议决策点'：是保留联邦能力（作为 UGC 多世界互联基础）还是接受孤岛，是有文化后果的架构决策，需在阶段 0-1 明确。
- 缺失'condition 社会治理语义分类'：72 个 condition 须先分类（战斗/治理/生命周期），分别设计 on_tick 文本与社区可见性，而非统一套用 ConditionHandler 组合返回值。
- 缺失'墙钟世界事件全量盘点'：day_phase 的 event_sunrise/event_common/event_dawn 等不只是广播，是耦合持久化与世界一致性的全局事件，需单独迁移设计。
- 缺失'emote/social 文本资产化'步骤：8400 文件中的文学性文本（winner_msg 武侠礼仪、emote 7 视角、condition 期满文案）是文化资产，需建文本资产库与 themed 文本包机制，而非当'模板池 backlog'渐进丢弃。
- 缺失'文化保真度'验收指标：成功指标只有差分测试通过率/性能/延迟/可用性，没有'灵魂系统迁移完整率''themed 文本保留率''社区共创痕迹保留率'等文化维度指标。

## 更优方案
- **[代词渲染分层]** 代词替换纯函数下移前端（§4.8/§29），假定 4 变量 $N/$n/$P/$p 是纯渲染 -> **服务端求值层 + 前端替换层分离：服务端对每条事件的 me/you 调 RANK_D 7 函数产出 PronounContext{name,pronoun,respect,rude,self,self_rude,close,self_close}，作为事件 payload 的结构化字段下发；前端只做 $X->context[X] 的机械替换。称谓规则随门派/职业/官职进 ThemeRegistry，UGC 可定义新称谓族。**
  理由：证据：rankd.c 的 6 称谓函数依赖年龄/性别/职业/门派/官职/PK 记录/鬼魂状态，是不可下沉的业务规则；但 $X 替换本身是纯字符串操作可下沉。分层后两端各归其位。
- **[emote 与社交文本资产化]** message_vision 1626 文件当多年 backlog 渐进替换（§30），emote 未单独建模 -> **把 emote/social 文本建成一等资产：(1) 数据模型保留 7 视角全字段；(2) updated 字段升格为 provenance 的一部分（author=wizard_id），既保留社区共创记忆又自然接入 CPK provenance 体系；(3) 代词变量扩到 10 个；(4) 提供 themed 文本包机制，不同题材注册自己的 emote 库。前端做'称谓编辑器'让 UGC 作者可视化调 RANK_D 规则。**
  理由：证据：data/emoted.o 含 7 视角 + 20+ wizard 署名 + 10 代词变量。简化即丢文本表现力与社区记忆。资产化反而让 UGC 创作者能复用这套武侠文本美学。
- **[灵魂系统独立子系统]** 天雷降为业务反作弊（§31e），condition 社会治理归入 ConditionSystem，阴间/bwdh/vote/法院/intermud 未出现 -> **新建'世界观治理层'子系统，归集所有 themed 治理：天雷（反作弊惩罚）、阴间（死亡流程）、法院（反机器人审判）、vote（玩家自治）、bwdh（社区竞技活动）、condition 中的 killer/city_jail/vote_suspension/pregnant。与战斗引擎平级。设计原则：系统治理行为必须用世界观语言表达文本，惩罚带 themed 文案与社区可见反馈。保留天雷的 message_vision 文本与 unconcious 语义作为'想象力治理'范式范例。**
  理由：这是 MUD 区别于图形游戏的核心：治理内嵌于虚构世界。独立子系统才能保留 themed 文本美学，混入 ConditionSystem 会被当战斗 buff 平掉。
- **[intermud 联邦演进]** 完全丢弃 intermud（41 网络服务文件），新引擎成孤岛 -> **评估'联邦协议'作为 UGC 平台多世界互联的差异化能力：定义跨世界通信协议（gchat/gfinger/gtell/mail 的现代等价），让不同 CPK 世界、甚至不同 MUD 实例互联。短期可降级为'未来选项'，但协议设计要预留（如 EntityAddr 已是 world:// 可扩展为 federated://）。**
  理由：intermud 是 MUD 联邦文化基因。UGC 平台多题材世界天然需要互联。丢弃即放弃差异化。
- **[message 渲染门控的状态契约]** 渲染下沉前端纯函数（§4.8），outdoor/weather/blind 门控未建模 -> **显式建模'渲染门控契约'：服务端在事件 payload 附 RenderGating{outdoors,weather,blind_level,block_msg_classes}，前端按门控决定可见性/变形。blind 的随机丢弃由服务端用 CombatRNG 预计算结果下发（哪些消息被丢），而非前端随机，保证三端一致与可回放。**
  理由：门控是状态依赖的，非纯前端。预计算保证一致性与差分可回放。

## greenfield 重审
- 差分测试 golden trace 录制（阶段 0 核心安全网）假设有运行中的 LPC 系统可录制命令流。0-1 全新项目无此运行时。需显式立项搭建可运行的 MudOS + XKX 实例作为规格源（MudOS 老旧工具链依赖是实打实工作量），或改为从 LPC 源码静态抽取输入输出契约（go/move/combat/channel 的命令前置条件+状态读集+输出消息集+状态写集）作为静态 golden contract。阶段 0 当前未把'搭建规格源实例'列为前置步骤，工时估算遗漏。
- '双栈过渡一致性测试'（§31d：每条 Telnet 输出 = render(某条语义事件)）假设 LPC 运行时与 Python 运行时并存双栈。0-1 全新项目不保留 LPC 运行时，无双栈。该测试前提不成立，应改为'静态契约一致性'：从 LPC 源码静态抽取 message_vision 调用点的模板+代词+门控，与 Python 渲染层输出做字符串契约比对。
- '迁移适配层'（02 子系统3：单进程 asyncio actor 内逐步将 LPC feature 行为迁入 Python System）的'逐步迁入'暗示 LPC 与 Python 并存运行。0-1 是重写不是迁移，无并存期。应去除'逐步迁入'话术，改为'按子系统重写并对照静态契约验证'。
- TelnetAdapter'过渡期兼容'（02 子系统1）假设有 LPC 端可过渡。0-1 项目无 LPC 端，Telnet 适配器是新引擎的单向输出端，非'双栈过渡缝'。应明确 Telnet 是为保留 telnet 老玩家接入能力的长期一等公民，而非'过渡期'产物，否则会低估其长期维护成本。
- '先迁移 go/move/combat/channel 四主线'（阶段 0/1）的渐进性假设有运行时对照源。0-1 项目中这四主线是'首批重写+对照静态契约验证'，不是'从 LPC 迁移'。语义偏差率度量的对照基准是静态抽取的契约，不是运行时 diff。
- Louvain 分片基于'现有 6414 房间出口图'（00 §4.2）。0-1 项目初期只重写 d/city 约 90 房（阶段 0 试点），全图分片是远期事项。但 UGC 动态加房后出口图持续变（§X 已识别），需明确'初始分片基于迁移完成的全图，后续增量分片基于 UGC 增长'，避免在 90 房试点期就预构分片框架。
- '32 守护进程全量分类表'（§G）是增量重构视角（迁移现有 daemon）。0-1 视角应改为'32 守护进程的职责重新设计'：哪些职责在新架构中被 ECS System 取代（如 natured->WorldClockSystem）、哪些保留为无状态服务（如 chinesed）、哪些演进为新能力（如 channeld->FederatedMessageService 承载 intermud）。不是 1:1 迁移而是职责重组。

## 承重论断（供质证）
- **[high]** 代词体系实测是 10 个变量（$N/$n/$P/$p/$C/$c/$R/$r/$S/$s），其中 6 个由 RANK_D 的 7 个动态业务函数求值（依赖年龄/性别/职业/门派/官职/武功等级/善恶/鬼魂状态），'代词替换纯函数下移前端'的承重论断不成立--rank 求值必须留服务端，前端只做 $X 到预求值字段的替换。
  依据：代码证据：adm/simul_efun/message.c + adm/daemons/emoted.c 注释列出 10 变量；adm/daemons/rankd.c 7 个 query_ 函数（query_rank/query_respect/query_rude/query_self/query_self_rude/query_close/query_self_close）每个都调用 ob->query_skill/ob->query('class')/ob->query('dali/rank')/ob->is_ghost() 等业务查询。方案 00 总纲 §4.8 与 02 子系统9 反复称'代词替换纯函数下移前端'。
- **[high]** emote 系统实测是 7 视角变体（myself/others/target/myself_target/others_target/myself_self/others_self）含 wizard 作者署名（updated 字段，20+ 位 wizard），方案简化为 3 视角 4 变量会丢失一半叙事视角与全部社区共创痕迹。
  依据：data/emoted.o 结构验证：每条 emote 含 7 视角键 + updated 作者字段；adm/daemons/emoted.c 注释定义 10 代词变量。方案 02 子系统9 的 render_message 契约只有 3 视角。
- **[high]** 5 份架构文档完全遗漏至少 5 个灵魂系统：阴间/轮回（d/death 13 房）、武林大会（d/bwdh 40+ 房墙钟触发）、vote 玩家自治（16 岁门槛+剥权 condition）、法院审判反机器人（themed 反外挂）、intermud 跨服网络（41 网络服务文件）。这些是 MUD 文化骨架，不是边缘玩法。
  依据：grep 5 份文档对 vote/courthouse/bwdh/阴间/intermud 零命中；源码验证：d/death 13 房、d/bwdh 40+ 房、cmds/std/vote + 2 子动作、d/wizard/courthouse、adm/daemons/network 41 文件。
- **[high]** condition 的 72 个守护进程中大量是社会治理状态机（killer 通缉/vote_suspension 剥权/city_jail 监禁/pregnant 怀孕），携带社区可见 themed 文本，归入 ConditionSystem（战斗引擎同级）是范畴错误，应拆为 CombatCondition + SocialCondition + LifecycleCondition 三类。
  依据：kungfu/condition/ 目录实测：killer.c（通缉+文本'官府不再通缉你了'）、vote_suspension.c（剥权+文本'观察期已满'）、city_jail.c、pregnant.c、biao.c。方案 02 子系统5 把 72 condition 统一归 ConditionSystem。
- **[medium]** greenfield 0-1 框架下，'录制 LPC golden trace 做差分测试'（阶段 0）和'双栈过渡一致性测试'（§31d）是增量重构假设的残留：0-1 项目没有运行中的 LPC 系统可录制，也没有 LPC 运行时可双栈并存。需改为'静态契约抽取'或显式立项搭建 LPC 规格源实例。
  依据：04 迁移路径阶段 0 写'录制 LPC 命令流为 golden trace'；01 §31d 写'双栈过渡须一致性测试'；02 子系统3 写'迁移适配层逐步将 LPC feature 行为迁入 Python System'。用户已澄清是 0-1 全新项目非增量重构。
- **[medium]** 业界标杆应定位于'最 MUD 的现代游戏'而非'最现代的 MUD'：前者保留 themed 治理范式（天雷是 themed 反作弊、阴间是 themed 死亡惩罚、法院是 themed 反外挂、vote 是 themed 自治）并用现代技术放大其文本表现力与触达，后者抽空文化灵魂换现代工程皮。差异化能力是 intermud 联邦 + themed 治理 + 想象力渲染，这是图形 MMO 无法复制的。
  依据：价值判断+证据支撑：themed 治理范式（天雷/阴间/法院/vote）在图形 MMO 无对标；intermud 联邦是 MUD 独有；想象力治理（盲人随机丢消息、天雷 themed 文本）无法图形化复制。方案未提出文化保真维度。

## 优先建议
- 立即做'灵魂系统盘点'：枚举阴间/武林大会/vote/法院/intermud/emote 7 视角/RANK_D 7 函数/day_phase 事件/condition 社会治理类，逐一标注迁移方式与文本保真要求，补入迁移面统计（当前只数了技术调用面 68771，没数文化系统面）
- 修正代词渲染分层契约：服务端求值 RANK_D 7 函数产出 PronounContext 下发，前端做 $X 替换；emote 渲染契约从 3 视角扩为 7 视角、代词从 4 变量扩为 10 变量。这是中文武侠文本表现力核心，不可简化
- 新增'世界观治理层'子系统：把天雷/阴间/法院/vote/bwdh 及 condition 中的 killer/city_jail/vote_suspension/pregnant 归集，与战斗引擎平级。设计原则：系统治理行为必须用世界观语言表达文本。天雷作为 themed 惩罚范式范例保留完整
- greenfield 0-1 框架下重做差分测试基建：阶段 0 前立项搭建可运行的 LPC MudOS+XKX 实例作为规格源；把'双栈过渡一致性测试'改为'静态契约抽取+LPC 实例回归'；移除'迁移适配层逐步迁入'的并存假设
- 保留 emote/social 文本的 wizard 作者署名作为 legacy provenance 回填 CPK；把 wizard 称号（天后/女神）作为文化身份而非运维权限保留进 ThemeRegistry；UGC 创作者身份继承 wizard 文化的仪式感
- 新增'文化保真度'验收指标，与差分测试行为保真并列为一等：灵魂系统迁移完整率、themed 文本保留率、社区共创痕迹保留率。业界标杆定位为'最 MUD 的现代游戏'，技术现代化服务于放大文本表现力与社区文化而非抹平文化细节
- 评估 intermud 联邦协议现代化作为 UGC 多世界互联的差异化能力，至少在 EntityAddr 设计中预留 federated:// 扩展，不轻易放弃跨世界通信基因
