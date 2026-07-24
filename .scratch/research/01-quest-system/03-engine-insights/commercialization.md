# 商业化与增长视角：LPC 任务系统的商业潜力评估

## 0. 评估前提

本报告以当前仓库《侠客行》LPC 源码为**一手证据**，从付费设计、UGC 创作者经济、题材包消费、用户增长四个维度，评估任务系统对新引擎的商业价值。所有结论均标注具体 LPC 文件路径与函数/对象名。报告不做最终商业定稿，只输出原则性设计建议，供后续引擎抽象参考。

> 注：项目 `CLAUDE.md` 已明确商业化架构支撑点属于"要留位置但不强制 MVP 实现"（支撑点 6）：玩家侧双货币 + 订阅 + 不 pay-to-win、创作者侧按题材包消费分成、承载扩展靠题材包数量横向扩展。本报告在相应章节会简要说明这些约束。

---

## 1. LPC 任务系统中已蕴含的商业化元素

### 1.1 社交绑定：帮派/师门作为身份与消费分层的锚点

LPC 任务系统几乎完全围绕"门派/帮派归属"展开，这种归属天然具备社交分层与付费分层潜力：

- **帮派加入即绑定**：`/d/huanghe/npc/bangzhu_duty.h` 的 `ask_join()` 中，帮主会检查玩家正邪门派（丐帮、大理段家、武当、峨嵋、华山、少林均被拒绝加入），并发放绑定帮令 `bang ling`（`/d/huanghe/obj/bangling.c`）。帮令记录 `owner`、`fam`、`score`，成为玩家在该组织内的身份凭证。
- **师门日常绑定**：`/kungfu/class/gaibang/lu.c` 的 `ask_job()` 仅对 `family/family_name == "丐帮"` 玩家开放；`/kungfu/class/xingxiu/ding.c` 的 `ask_job()` 仅对 `family/family_name == "星宿派"` 开放。任务成为玩家维持门派身份的每日行为。
- **推荐与担保链**：`/d/shaolin/npc/xuanci.c` 的 `ask_job()` 要求玩家先获得方丈推荐信 `/d/shaolin/obj/letter-job.c`，再前往龙门镖局找都大锦；`/d/hangzhou/npc/du.c` 则校验该信件 `owner` 与玩家一致。这种"推荐信 → 雇主"的链式任务，是社交背书与信任层的前身，可演化为付费会员/邀请码体系。

> 商业化映射：门派/帮派可作为"订阅身份"或"战令身份"的载体；不同身份解锁不同任务池、奖励倍率与社交权限，天然支持分层付费。

### 1.2 限时与稀缺：时间窗口制造 FOMO

- **限时任务窗口**：`/d/hangzhou/npc/kumu.c` 的 `ask_job()` 要求 `day_event() == "event_dawn"`，且 `buddhism` 技能 >= 120，过期不候；`/kungfu/condition/ypjob.c` 在 `duration == 1` 时提示"青铁令时限已到"并累计失败计数。
- **冷却与节奏控制**：`/d/huanghe/npc/bangzhu_duty.h` 的 `ask_job()` 使用 `time() < me->query("bangs/asktime") + 180` 控制 180 秒冷却；`/d/huanghe/npc/guanjia.h` 更是压缩到 60 秒。`/d/city/npc/ftb_zhu.c` 的 `ask_job()` 用 `last_ask_time` 防 10 秒内的频繁刷屏。
- **稀缺物品奖励**：`/kungfu/class/xingxiu/ding.c` 中，丁春秋对弟子发放的 `sanxiao`（逍遥三笑散）、`blzhen`（碧磷针）、`rousi-suo`（柔丝索）、`wuxing`（无形散）均带 `*_count` 库存限制（`san_count`、`zhen_count`、`suo_count`、`wxs_count`），发完即止。这已具备"限量道具/宝箱"雏形。

> 商业化映射：限时任务、每日刷新、限量奖励是现代战令（Battle Pass）、赛季活动与抽卡稀缺性的核心杠杆。LPC 的 `condition` 与 `count` 机制可直接映射为"每日任务次数""每周限量兑换"。

### 1.3 排行榜/贡献与长期成就资产

- **帮贡/功劳点**：`/d/huanghe/obj/bangling.c` 的 `do_find("score")` 可查询"功劳点"，`do_collect()`、`do_sign()`、`do_bargain()`、`do_visit()` 都会增加 `score`。该分数在 `/d/huanghe/npc/bangzhu_duty.h` 的 `ask_skills()` 中用于兑换帮主传授武功（10 分以上才可请教，100 分封顶消费）。这是最早的"贡献货币 + 兑换商店"模型。
- **门派贡献**：`/kungfu/class/xingxiu/ding.c` 中，完成抓毒虫任务增加 `xingxiu/contribution`，可用于"更名"（消耗 50 点）并影响帮主对弟子的态度（`<100` 被骂，`>500` 可请教）。
- **全局统计与排行榜**：`/clone/obj/job_server.c` 的 `reward_func()` 维护 `"stat/"+job` 记录每个玩家"任务次数、耗时、pot、exp、rate"，并提供 `do_job_stat()` 按 `exp/hour`、`pot/hour`、`name`、`number` 排序输出。`print_hist_func()` 进一步输出奖励直方图。这已是运营级排行榜与平衡性看板。
- **累计成就**：`/kungfu/class/gaibang/lu.c` 的 `check_job()` 在完成任务后 `ob->add("gb/job_comp", 1)`，记录累计完成次数；失败则累计 `gb/job_fail`。`/kungfu/condition/ypjob.c` 也累计 `yipin/failure`。

> 商业化映射：贡献点、功劳点是双货币体系中"绑定货币/声望货币"的雏形；全局统计是赛季排行榜、段位、成就徽章的数据基础。

### 1.4 动态供需调节：奖励随参与度浮动

`/d/city/npc/ftb_zhu.c` 的 `adjust_rate()` 是关键运营机制：

- 当 20 分钟无人完成该任务时，`exp_limit` 与 `pot_limit` 自动上涨（最高 cap 10000/1000）；
- 每次完成任务后，`exp_limit` 衰减 `exp_limit/1000`，但有下限 3000；
- 通过 `ask_cike()` 与 `ask_freq()` 将当前奖励热度反馈给玩家（"刺客猖獗" → "一统天下"）。

> 商业化映射：这是动态激励/再激活系统（re-engagement）的早期形态，可直接用于召回流失玩家或引导新玩家进入低参与度玩法。

### 1.5 失败惩罚与沉没成本

- `/kungfu/class/gaibang/lu.c` 的 `gb_job` condition 会在 duration 归零时随机掉落密函（`gb_job.c` 的 `let_know()`），导致任务失败；失败累计 `gb/job_fail`。
- `/kungfu/condition/ypjob.c` 在时限到达时累计 `yipin/failure`。
- `/d/huanghe/obj/caili.c` 的 `do_check()` 会在玩家被跟随/诅咒时直接销毁彩礼，强制失败。

> 商业化映射：失败惩罚会放大"再来一次"与"购买保险/加速道具"的付费冲动，但需严格控制以避免挫败感。

---

## 2. 双货币与订阅制的可能接入点

### 2.1 LPC 已存在的"货币"分层

源码中至少存在三种不同性质的"货币"，为双货币设计提供了天然分层：

1. **硬通货（铜钱/银子/金子）**：`/d/city/npc/publisher.c` 的 `do_buy()` 使用 `MONEY_D->player_pay()` 进行交易；`/d/hangzhou/npc/du.c` 在 `lmjob` 完成后发放 `silver` 红包。
2. **角色成长货币**：`combat_exp`（经验）、`potential`（潜能）是任务核心产出，`/clone/obj/job_server.c` 的 `reward_func()` 直接操作二者。
3. **绑定声望/贡献货币**：`/d/huanghe/obj/bangling.c` 的 `score`（功劳点）、`/kungfu/class/xingxiu/ding.c` 的 `xingxiu/contribution` 只能在特定 NPC 处兑换技能或称号。

> 商业化映射：可抽象为"付费货币（Cash）+ 绑定货币（Bound）+ 声望货币（Reputation）"三层。`combat_exp`/`potential` 是玩家时间投入的"劳动货币"，不应直接售卖；`score`/`contribution` 是组织忠诚度货币，可绑定订阅；银子/金子可用于交易税或外观付费。

### 2.2 订阅制的接入点

- **身份订阅**：门派/帮派任务池可设计为"免费基础池 + 订阅高级池"。例如，基础帮众只能接"寻""杀"任务，订阅玩家可接"截镖""护驾"等高收益/高社交冲突任务（参考 `/d/huanghe/npc/bangzhu_duty.h` 的任务类型分级）。
- **收益倍率订阅**：`/clone/obj/job_server.c` 的 `exp_limit`/`pot_limit` 是任务每小时收益上限。订阅玩家可获得更高的个人上限或更低的衰减系数，但需遵守 CLAUDE.md 中"不 pay-to-win"的约束——倍率优势应限定在"节省时间"而非"突破服务器上限"。
- **额外任务次数订阅**：当前 LPC 各任务独立冷却（如 180 秒、60 秒），但没有每日总次数限制。新引擎可由 engine 统一维护"每日任务配额"，订阅用户获得额外配额，免费用户通过观看广告/邀请好友补充。
- **创作者订阅（可选）**：`publisher.c` 的书贾允许玩家出版书籍并获取利润（`ask_book()` 提取 `money_made`）。可演化为"创作者通行证"，降低平台抽成或提升作品曝光。

> 约束说明：依据 CLAUDE.md 支撑点 6，"玩家侧双货币 + 订阅 + 不 pay-to-win"是方向但非 MVP 强制实现。设计时应将订阅收益锚定在"便利、外观、社交标识、内容访问"，而非直接购买战力。

---

## 3. 题材包消费与创作者分成：任务系统如何成为题材包的核心卖点

### 3.1 任务系统是题材包内容密度的主要载体

LPC 的每个区域/门派都依赖任务串联：

- **武侠 MVP**：`/d/huanghe/npc/bangzhu_duty.h` 的 9 种任务类型（寻、杀、截镖、送礼、护驾、示威、摊费、买卖、伙计）覆盖了江湖叙事的原子动作；`/kungfu/class/gaibang/lu.c` 的送信任务让玩家遍历全地图 NPC；`/d/city/npc/ftb_zhu.c` 的刺客追捕任务动态利用地图房间。
- **扩展题材**：参考 `creator-perspective.md` 的分析，仙侠需要"护送仙舟、秘境探索"，科幻需要"骇入终端、派系声望"，校园需要"好感度事件链"。这些差异主要体现在任务目标、奖励类型与叙事包装上，而非底层生命周期。

> 商业化映射：任务系统的可配置性决定了题材包的上限。一个题材包能否卖出，很大程度上取决于它提供了多少"有新鲜感但机制统一"的任务链。引擎应让创作者专注于"写什么"而非"怎么写"。

### 3.2 创作者分成与题材包资产元数据

`/d/city/npc/publisher.c` 是 LPC 中罕见的 UGC 经济原型：

- 玩家通过 `do_publish()` 将手稿 `this_book` 提交给书贾，系统保存 `arthur_id`、出版时间、销量、收入；
- 其他玩家购买时，一半书款通过 `save_book_sold()` 计入作者账户；
- 作者通过 `ask_book()` 提取 `money_made`。

这已具备"创作者 → 平台 → 消费者"三方分成的雏形，但存在缺陷：

- 作者 ID 仅作为字符串保存，没有创作者资产元数据（如版本、题材包归属、分成比例）；
- 收入以硬通货结算，没有与题材包消费记录关联；
- 平台抽成比例硬编码（`/d/city/npc/publisher.c` 第 239 行 `ob->query("value")/2`）。

> 商业化映射：依据 CLAUDE.md 支撑点 6，新引擎应预留"题材包资产元数据（创作者归属 + 版本溯源）"与"消费/参与度埋点（可打点到题材包 ID）"。任务系统作为高频消费场景，是埋点的核心位置——每个任务的开始、完成、失败、奖励领取都应记录 `pack_id` 与 `creator_id`，为后续分成提供审计依据。

### 3.3 任务作为题材包的"试玩入口"

- LPC 中多数任务对玩家经验有门槛（`/d/city/npc/ftb_zhu.c` 要求 1 万–1100 万 combat_exp，`/d/huanghe/npc/bangzhu_duty.h` 的 `levels` 从 3000 到 500000 分级）。
- 新引擎可反向利用这一点：将低等级任务链作为题材包的"免费试玩章节"，高等级/高收益任务链作为"完整解锁"内容，引导玩家为完整题材包付费。

> 商业化映射：任务链天然是内容分章的边界。官方武侠包可以"新手村 → 城镇 → 门派 → 野外"任务链作为免费内容，仙侠/科幻包以专属任务链作为付费 DLC。

---

## 4. 用户增长：任务系统对新玩家 onboarding、老玩家留存、病毒传播的作用

### 4.1 新玩家 onboarding：师门/新手村任务是核心引导

- `/d/shaolin/npc/xuanci.c` 的 `ask_job()` 向低辈分少林弟子发放推荐信，引导其前往 `/d/hangzhou/biaoju.c` 找都大锦；`/d/hangzhou/npc/du.c` 则要求少林弟子进入镖局后院传授武功。这一链条将"门派 → 城镇 → 副本/特殊场景"串联，是典型的新手引导。
- `/kungfu/class/xingxiu/ding.c` 的抓毒虫任务（`ask_job()` 设置 `xx_job` 状态，`/d/xingxiu/xx_job.h` 的 `do_search()` 实现搜索逻辑）引导玩家熟悉后山地图、物品使用与 NPC 交互。
- `/d/huanghe/bangjob/bangjob3000.c` 的低级任务目标多为扬州城、华山村等新手区域，经验门槛 3000。

> 增长映射：任务系统是新玩家理解世界规则、建立目标感的第一触点。引擎应提供"新手任务模板"，自动根据玩家等级/位置推送下一个目标，降低流失。

### 4.2 老玩家留存：每日/循环任务 + 赛季重置

- `/kungfu/class/gaibang/lu.c` 的 `assign_job()` 每次从全地图 `livings()` 中随机选择目标 NPC，任务内容具有随机复玩性；`/d/huanghe/npc/bangzhu_duty.h` 的 `ask_job()` 每次随机抽取 bangjob 配置表中的条目。
- `/d/city/npc/ftb_zhu.c` 的 `adjust_rate()` 通过动态奖励调节任务热度，是召回老玩家的机制。
- `/clone/obj/job_server.c` 的统计与直方图为运营提供了调整依据。

> 增长映射：循环任务的随机性与动态奖励是维持 DAU 的基础。新引擎应内建"每日任务池 + 周常任务 + 赛季排行榜"，并通过数据反馈自动调节奖励率。

### 4.3 病毒传播：社交冲突任务与帮派对抗

- `/d/huanghe/npc/bangzhu_duty.h` 的"示威"任务要求玩家击杀其他帮派成员；"截镖"任务会动态生成 `BIAOTOU` NPC（`/d/huanghe/npc/biaotou.c`）并在其死亡时掉落 `BIAOHUO`（`/d/huanghe/obj/biaohuo.c`），可被非任务玩家截获。
- `/d/huanghe/npc/bangzhu.c` 的 `accept_kill()` 会在帮主被攻击时召唤随从反击，形成小团体 PvP。
- `/d/huanghe/obj/caili.c` 的送礼任务在途中会遭遇其他帮派 NPC 劫杀（`do_go()` 中生成 `BANGZHONG2`），制造冲突与互助需求。

> 增长映射：对抗性任务与帮派归属会催生"拉朋友入帮""组队护镖"等社交行为，是病毒传播的自然杠杆。但需注意 PvP 挫败感与付费公平的平衡。

---

## 5. 需警惕的 pay-to-win 风险与公平性问题

### 5.1 直接购买战力的风险

- LPC 任务奖励大量产出 `combat_exp` 与 `potential`（`/clone/obj/job_server.c` `reward_func()` 第 585–586 行），并可能直接提升 `max_neili`/`eff_jingli`（`/d/city/npc/ftb_zhu.c` 第 382–385 行）。
- `/kungfu/class/xingxiu/ding.c` 的任务奖励门派专属毒物与秘籍，若这些物品可交易或可通过付费直接获取，将破坏门派平衡。

> 风险：若付费货币可直接兑换任务奖励或跳过任务，将形成明确的 pay-to-win，违反 CLAUDE.md 中"不 pay-to-win"约束。

### 5.2 贡献/功劳点的不可交易性缺失

- `/d/huanghe/obj/bangling.c` 的 `score` 是记录在物品上的，物品绑定玩家但机制上未明确不可交易；`/kungfu/class/xingxiu/ding.c` 的 `contribution` 记录在玩家身上，但未做账号级别隔离。

> 风险：若贡献货币可代刷、可交易，将产生工作室经济与 RMT（现实货币交易）问题。

### 5.3 任务可被脚本/工作室刷取

- `/d/huanghe/npc/bangzhu_duty.h` 的 180 秒冷却仅针对单个 NPC，不同任务/不同 NPC 之间无共享冷却；`/d/city/npc/ftb_zhu.c` 的 `adjust_rate()` 反而会在低参与度时提高奖励，吸引脚本刷取。
- `/d/huanghe/obj/caili.c` 的 `do_check()` 试图检测跟随/诅咒等作弊，但依赖运行时对象检查，容易被绕过。

> 风险：UGC 环境下，创作者可能设计高奖励低难度的任务吸引流量，破坏全服经济平衡。引擎必须从架构层统一任务配额、奖励上限与审计。

### 5.4 动态 NPC/物品泄漏与奖励异常

- `/d/city/npc/ftb_zhu.c` 的 `put_objects()` 将刺客对象写入 `player->set(JOB_NAME+"/obj_list", obj_list)`，若任务异常中断或玩家下线，对象可能残留；`bangzhu_duty.h` 的"截镖"任务通过 `children(BIAOTOU)` 限制全局最多 10 个镖头，但这是手写配额。

> 风险：任务对象泄漏会导致奖励异常或服务器负载异常，在商业化环境中直接影响经济安全。

### 5.5 全服广播与信息噪音

- `/d/wizard/center.c` 中的系统开关会触发 `CHANNEL_D->do_channel(..., "sys", ...)` 全服广播。若 UGC 任务获得此能力，将造成信息噪音。

> 风险：商业化运营中，频道资源是稀缺广告位，不应向普通创作者开放。

---

## 6. 新引擎任务系统的商业化设计建议（原则性，不定稿）

### 6.1 原则一：任务核心机制题材无关，奖励类型可配置

- 生命周期（开始/放弃/完成/失败/超时）、目标生成、条件检查、统计直方图应作为 engine 层原子能力；
- 奖励表应支持经验、潜能、金钱、物品、技能熟练度、声望、贡献、称号、外观等可配置条目，而非硬编码 `combat_exp`/`potential`；
- 参考 `/clone/obj/job_server.c` 的 `exp_limit`/`pot_limit` 设计，保留题材包级别的每小时奖励上限，但应抽象为通用"奖励速率上限"概念。

### 6.2 原则二：贡献/声望货币与付费货币严格分离

- 玩家时间投入产出的 `combat_exp`/`potential`/贡献点应绑定账号/角色，不可交易；
- 付费货币主要用于外观、便利、额外内容访问、社交标识，不应直接购买战力或核心成长货币；
- 订阅收益应体现在"节省时间""解锁任务池""专属称号/外观"，而非突破服务器级奖励上限。

### 6.3 原则三：UGC 任务必须内建安全护栏

- rate 强制 clamp 到题材包声明区间，负奖励与超上限奖励需要二次确认/白名单（参考 `/clone/obj/job_server.c` 第 119–124 行注释）；
- 创作者不能直接调用 `player->add("combat_exp", ...)` 等核心属性写操作，必须走 engine 审计通道；
- 任务生成的动态对象必须注册到任务作用域，任务结束/放弃/超时时自动清理；
- 提供全局配额管理，替代手写 `children()` 过滤。

### 6.4 原则四：运营观测与创作者分成内建

- 每个任务事件（开始、完成、失败、奖励领取）记录 `pack_id`、`creator_id`、`quest_id`，支撑 CLAUDE.md 要求的"消费/参与度埋点"；
- 保留 `/clone/obj/job_server.c` 的 per-user 统计与 per-job 直方图，并扩展为按题材包聚合的 dashboards；
- 创作者收益按题材包消费数据结算，平台抽成比例由 engine 配置而非硬编码。

### 6.5 原则五：世界实例隔离支撑横向扩展

- 依据 CLAUDE.md 支撑点 6，未来每个题材包可运行独立世界实例。任务系统的状态、配额、经济应支持按世界实例隔离，避免不同题材包之间的任务奖励互相冲击。

### 6.6 原则六：新手友好与反刷取并重

- 提供新手任务模板与自动引导；
- 统一每日/每周任务次数上限与跨任务冷却，防止脚本与多角色刷取；
- 高价值奖励绑定"首次完成"或"账号级别"，降低工作室套利空间。

---

## 7. 结论摘要

LPC 任务系统已经蕴含了社交绑定、限时稀缺、贡献货币、动态激励、排行榜统计等商业化元素，但其 reward 模型过于战斗-centric、创作者门槛高、安全护栏薄弱。对新引擎而言，任务系统应作为题材无关的 core service 重写：保留生命周期、目标生成、奖励上限、统计观测等机制，将奖励类型、任务内容、叙事包装开放给题材包创作者；同时通过严格的货币分层、审计通道与配额管理，避免 pay-to-win 与经济崩溃。任务链既是新手 on-boarding 的引导线，也是题材包消费的核心卖点与创作者分成的主要埋点。
