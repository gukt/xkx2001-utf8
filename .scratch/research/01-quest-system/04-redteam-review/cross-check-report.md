# 01-quest-system 红队横向对比验证报告

> 角色：横向对比验证员  
> 输入：Phase 1 已产出的 01-raw-findings、02-user-stories、03-engine-insights 全部初稿  
> 目标：交叉检查各文件之间的一致性，验证通用机制抽象对 LPC 源码的覆盖度，指出伪通用、真特例与声明式/事件驱动假设面临的破坏点。

---

## 1. 跨门派 / 跨任务类型的共同模式总结

通过横向对比，以下模式在多个门派 / 任务类型中反复出现，具有较高抽象价值：

| 共同模式 | 覆盖的任务类型 | 证据来源 |
|---|---|---|
| **对话触发接取** | 师门、走镖、帮派、明教五系、星宿、神龙教、御林军 | `gameplay-slices.md` 切片 1–6；`mechanisms.md` 第 2.1 节；`source-inventory.md` 第 3.1 节 |
| **玩家对象或随身物品保存任务状态** | 少林推荐信、走镖 `biao/*`、黄河帮 `bang ling`、明教 `mingjiao/job`、神龙教 `sgjob/*` | `gameplay-slices.md` 共性抽象速览表；`player-stories.md` Story 7.3；`mechanisms.md` 第 1.1 节 |
| **`accept_object()` 交付物品完成** | 黄河帮寻/截镖、明教火枪/铁矿、星宿毒丹、雪山酥油罐 | `gameplay-slices.md` 切片 4.1、4.2、6；`mechanisms.md` 第 2.2 节 |
| **Condition 倒计时作为限时/持续机制** | 走镖 `biaoju`、一品堂 `ypjob`、灵隐寺 `lyjob`、丐帮 `gb_job`、华山 `hz_job` | `source-inventory.md` 第 2.5 节；`mechanisms.md` 第 5.1 节；`system-stories.md` 第 2 节 |
| **按经验分档选择任务池** | 黄河帮 `bangjob{3000…500000}`、神龙教 `sgjob{20000…2000000}` | `source-inventory.md` 第 2.4、2.5 节；`mechanisms.md` 第 6.5 节 |
| **失败/放弃惩罚：冷却、贡献扣除、失败计数** | 走镖 `biao/fail`+`condition("biao")`、明教扣 `mingjiao/cc`、神龙教扣 `sg/exp`、一品堂 `yipin/failure` | `gameplay-slices.md` 切片 2/4/5 异常路径；`mechanisms.md` 第 5 节 |
| **奖励以经验/潜能/金钱为主，辅以门派贡献/称号** | 明教忠诚度、黄河帮帮令 score、御林军职级、大理 `jobdone` | `mechanisms.md` 第 4.1 节；`source-inventory.md` 第 3.3 节 |
| **NPC 动态生成目标或护送对象** | 黄河帮截镖生成 `BIAOTOU`、护驾生成帮主分身、走镖生成镖车/镖头 | `source-inventory.md` 第 2.4 节；`gameplay-slices.md` 切片 2.2/2.3/3；`system-stories.md` 第 1 节 |

这些模式可以归约为一个最小核心：**任务实例 = 接取条件 + 运行时状态载体 + 目标判定 + 奖励结算 + 失败/超时/放弃处理**。`mechanisms.md` 第 1.1 节与 `abstraction-options.md` 第 3 节提出的“Quest / Objective / Reward / Trigger / Condition / Log”与此吻合。

---

## 2. LPC 任务系统中无法被统一模型覆盖的特例

以下机制在源码中真实存在，但难以被单一声明式或事件驱动模型干净覆盖：

### 2.1 剧情推进型“无奖励”任务
- **代表**：雪山葛伦布“还愿供佛”。玩家交付“酥油罐”后仅获得 `temp("marks/酥", 1)`，用于解锁后续房间/剧情，没有经验/潜能/金钱奖励（`gameplay-slices.md` 切片 6）。
- **覆盖难点**：统一奖励模型会把它误判为“无奖励任务”；其真实价值是“世界状态 flag + 区域准入”，更接近叙事锁而非任务实例。

### 2.2 玩家间 PvP / 强制阵营转换任务
- **代表**：神龙教 `FORCEJOIN` 与 `PK` 教务。`sg_mianzhao.c` 的 `do_forcejoin()` 可对玩家或 NPC 进行 8–18 秒威逼判定，成功后不仅完成任务，还可能掠夺目标物品并改变目标阵营；`cancel_pk.h` 还要处理目标离线后的惩罚（`gameplay-slices.md` 切片 5；`source-inventory.md` 第 2.5 节）。
- **覆盖难点**：目标对象是另一个玩家的角色实例，任务完成判定依赖“击杀并 sign corpse”，且失败条件包含“目标下线/逃跑/进入安全区”。统一模型若只支持 NPC 目标会遗漏玩家目标；若支持玩家目标，则必须同时处理离线状态、PvP 同意、阵营强制变更等外部性。

### 2.3 雇佣型 NPC 自主追杀任务
- **代表**：谢烟客 `xie2.c`、李四 `xiejian.c`、丘处机 `qiu.c`。玩家支付或提交委托后，任务状态写入 NPC 自身的 `save()` 文件，NPC 在 `chat_chance` 触发的 `auto_check()` 中自主决定何时瞬移追杀目标（`system-stories.md` 第 5 节；`mechanisms.md` 第 2.4 节）。
- **覆盖难点**：任务状态持久化在 NPC 而非玩家身上；执行器是 NPC AI 而非玩家行为；完成判定依赖“尸体 present 且 victim_name 匹配”。统一任务实例若以玩家为中心会丢失这些状态。

### 2.4 动态地图遍历 + 自适应奖励
- **代表**：斧头帮程金斧 `ftb_zhu.c`。`find_target_room()` 调用 `mapdb`/`traverser` 在世界中随机选房间，`put_objects()` 在目标房间周围范围内生成刺客，并记录到 `player->set(JOB_NAME"/obj_list", obj_list)`；`adjust_rate()` 根据 20 分钟无人完成的情况自动提高 `exp_limit/pot_limit`（`mechanisms.md` 第 4.2、4.4、8 节；`creator-perspective.md` 第 4.4 节）。
- **覆盖难点**：任务目标不是预定义 NPC/物品/房间，而是运行时空间查询结果；奖励公式与“热度”挂钩，需要引擎级空间服务与经济调控能力。

### 2.5 官衙职级/编制任务
- **代表**：御林军守门。`duolong.c` 派发任务，`outer_gate.h` 的 `do_guard()` 进入执勤状态，`helper.c` 按 `speed_cur`、`pos_ratio`、`kill_ratio` 计算军功并更新 `bingbu/job_total` 等职级字段，晋升受职位空缺 `members/rank*` 限制（`source-inventory.md` 第 2.6 节；`mechanisms.md` 第 4.2、6.3 节）。
- **覆盖难点**：任务与个人任务实例不同，更像“岗位 + 绩效考核 + 编制晋升”，需要世界实例级的职位表和长期档案。

### 2.6 物品即状态且可丢失/被窃
- **代表**：走镖红镖 `biaohuo1.c` 可被其他玩家打开，导致原镖客失败；丐帮密函 `gb_job.c` 在 condition  tick 中随机掉落或被偷（`modern-design-review.md` 第 3.2 节；`system-stories.md` 第 2.5 节）。
- **覆盖难点**：统一任务状态若以玩家属性为主，无法表达“任务凭证在玩家背包中且可能被外部系统销毁”的语义。

---

## 3. 对“任务机制设计师”抽象的挑战：伪通用 vs. 真正的共性

### 3.1 伪通用：目标类型词条
`abstraction-options.md` 第 3 节把目标抽象为“持有/交付物品、击杀指定 NPC、进入指定房间集合、限时存活、积累临时计数”。但横向对比发现，同一词条在不同任务中差异巨大：

- **“击杀”**：黄河帮“杀”是杀指定 NPC（`bangjob*.c` 的 `type:"杀"`）；神龙教 PK 是杀指定玩家；斧头帮是动态生成一群刺客并记录 `obj_list`；黄河帮“示威”要求击杀“非本帮 title 的 bangzhong”；黄河帮“截镖”要求击杀镖头且 `my_killer == 玩家 id`（`mechanisms.md` 第 3.3 节；`gameplay-slices.md` 切片 3）。
- **“护送/护驾”**：走镖护送的是镖车对象 `biaoche` 与跟随 NPC；黄河帮护驾是生成帮主分身并 `set_leader(me)`；现代仙侠/科幻还会有“仙舟/飞船”等可移动实体（`creator-perspective.md` 第 2.2 节）。
- **“搜索/采集”**：明教五系是工种动作 + 工具 + 地点；星宿抓毒虫是 `search bug` 小游戏 + 瓦罐 + 修炼 + 随机遭遇（`gameplay-slices.md` 切片 4）。

**结论**：把这些都归为一个 `ObjectiveType.KILL / FETCH / ESCORT / SEARCH` 会掩盖实现差异。真正的共性是“触发事件 + 守卫条件 + 副作用”，而不是目标类型标签。

### 3.2 伪通用：奖励结算
各任务奖励公式高度异构：
- `job_server.c`：`exp_limit * exp_rate * 耗时 / 360000`（`mechanisms.md` 第 4.2 节）。
- 黄河帮击杀：`bonus = job["bonus"] * job["max"] / (combat_exp + 1000)`（`mechanisms.md` 第 4.2 节）。
- 黄河帮截镖：`bonus = exp * 120 / (exp + combat_exp)`（`mechanisms.md` 第 4.2 节）。
- 明教：`BASE + random(add_cc)`（`source-inventory.md` 第 6.1 节调用链）。
- 斧头帮：根据搜索范围、击杀比例、牺牲次数、玩家总经验动态调整 rate（`modern-design-review.md` 第 3.1 节；`creator-perspective.md` 第 4.4 节）。

**结论**：不存在统一的“难度-奖励”公式。真正共性只是“结算时应走受控奖励通道、做上限保护、写审计日志”，具体公式必须交给内容包。

### 3.3 伪通用：失败/超时
- 一品堂超时仅增加 `yipin/failure` 计数；灵隐寺 `lyjob` 超时只是自然结束并提醒休息；华山 `hz_job` 超时结束任务；丐帮密函可能在超时前随机丢失；神龙教 PK 目标下线记失败并惩罚（`mechanisms.md` 第 5.1 节；`system-stories.md` 第 2 节）。
- **结论**：失败不是单一状态，而是“超时 / 条件破坏 / 目标状态变更 / 外部事件”等多种原因的集合。统一模型应提供“失败原因”扩展点，而不是一个 `FAILED` 状态。

### 3.4 真正的共性
真正的共性集中在生命周期原语与审计边界：
1. 任务可接取、进行中、完成、失败、放弃（`mechanisms.md` 第 1.2 节）。
2. 状态需要持久化且与玩家存档一起保存（`mechanisms.md` 第 7 节）。
3. 奖励必须经引擎统一通道下发，禁止脚本直接 `add("combat_exp")`（`abstraction-options.md` 第 4 节反模式 3；`creator-perspective.md` 第 4.2 节）。
4. 动态生成的任务对象必须注册到任务作用域并在任务结束时清理（`creator-perspective.md` 第 4.3 节）。

---

## 4. 对“引擎架构师”抽象方案的挑战：哪些 LPC 细节会破坏声明式 / 事件驱动假设

### 4.1 状态载体不统一，打破“QuestProgress 中心”假设
`abstraction-options.md` 第 3 节建议用统一的 `QuestProgress` 保存玩家状态。但 LPC 中状态同时存在于：
- 玩家对象属性：`mingjiao/job`、`biao/*`、`sgjob/*` 等；
- 玩家临时属性：`temp/bangs/fam`、`hz_job/sexit`；
- 任务物品：`bang ling` 的 `job` mapping、推荐信 `owner`、水桶 `water_amount`；
- NPC 自身 save：谢烟客/李四/丘处机的任务队列；
- 全局 daemon：`job_server.o` 的 `stat/<job>`、`exp_hist/<job>`。

**破坏点**：若引擎只维护一个玩家中心的 `QuestProgress`，会遗漏物品凭证、NPC 侧持久化、全局统计这三类状态。`creator-perspective.md` 第 1.1 节已指出“上下文耦合重”。

### 4.2 触发器不是离散事件，而是对象回调链
声明式/事件驱动模型通常假设事件是“玩家输入 → 事件总线 → 任务状态机”。但 LPC 中的触发器分散在：
- `ask.c` → NPC `inquiry` 回调；
- `accept_object()` 在 `give` 指令中回调；
- 房间 `init()` 在玩家进入时无感知地写 temp flag；
- 房间 `valid_leave()` 阻止带 `hz_job` 的玩家离开；
- NPC `chat_chance` 驱动的 `auto_check()` 自主追杀；
- `call_out`/`condition` 心跳 tick 触发超时、随机丢信、刷新刺客（`system-stories.md` 第 2/5 节；`mechanisms.md` 第 2.3/2.4/2.5 节）。

**破坏点**：事件来源不仅是玩家动作，还包括世界心跳、NPC AI、房间状态。若引擎事件总线只订阅玩家命令，会遗漏大量触发源。

### 4.3 奖励结算假设被打破：脚本直接修改玩家属性
LPC 中奖励不是由中央服务下发，而是 NPC 脚本直接 `player->add("combat_exp")`、`add("potential")`、`add("max_neili")`、`add("shen")`（`abstraction-options.md` 第 1.4 节；`creator-perspective.md` 第 4.2 节）。

**破坏点**：声明式 `reward_currency` 字段无法表达“同时加经验、潜能、负神、帮贡、忠诚度、技能熟练度、临时属性 buff”的混合奖励；必须引入“奖励表 + 受控 Effect 通道”。

### 4.4 空间与对象生成假设被打破
声明式模型通常假设任务目标在配置中静态指定。但 LPC 中：
- 斧头帮用 `traverser` + `mapdb` 在世界中随机选房间并生成刺客（`mechanisms.md` 第 3.3 节；`creator-perspective.md` 第 3.2 节）。
- 黄河帮“截镖”用 `children(BIAOTOU)` 全局计数限制动态对象数量（`system-stories.md` 第 1.1 节）。
- 走镖生成镖车 `biaoche` 与镖头跟随，镖车本身是可移动对象（`source-inventory.md` 第 2.3 节）。

**破坏点**：需要引擎提供空间查询、动态对象配额、对象-任务作用域绑定等基础设施，否则声明式 DSL 会在中等复杂度任务上立刻触顶。

### 4.5 时间模型不是简单倒计时
LPC 使用时间的方式包括：
- `time()` 比较的自然 CD；
- `condition` 心跳 tick（每秒递减 `duration`）；
- `call_out` 一次性延迟；
- `chat_chance` 轮询；
- 自然事件如 `event_dawn` / 日出日落（`mechanisms.md` 第 2.4 节；`system-stories.md` 第 2 节）。

**破坏点**：事件驱动状态机若只支持 wall-clock 定时器，无法表达“MUD 心跳 + 自然时辰 + 随机轮询”的混合时间语义。

### 4.6 多玩家共享任务状态
走镖组队 `jobwith` 让两名玩家共享 `biao/dest` 与 `biao/dest2`，镖车所有者为两人（`gameplay-slices.md` 切片 2.4）。

**破坏点**：若 `QuestProgress` 是单玩家单实例，组队任务需要引入“共享任务实例 / 角色组”概念。

### 4.7 任务完成判定涉及外部世界状态
- 神龙教 PK 完成需要 `present("corpse", environment())` 且 `victim_name == target_name`（`mechanisms.md` 第 3.3 节）。
- 雇佣追杀 NPC 会检查目标是否在线、是否在安全区、血量/内力是否不过于饱满（`system-stories.md` 第 5.1 节）。
- 黄河帮截镖验收检查 `ob->query("my_killer") != who->query("id")`（`gameplay-slices.md` 切片 3）。

**破坏点**：完成条件不仅是“背包有物品 / 计数满”，还涉及目标在线状态、死亡现场、击杀归属、区域规则等世界运行时状态。

---

## 5. 发现的矛盾或遗漏

### 5.1 华山巡逻 condition 文件被误判为空壳
- **矛盾**：`source-inventory.md` 第 2.7 节与“特殊发现 5”把 `/kungfu/condition/hz_job.c` 列为“空壳 condition”；`mechanisms.md` 第 1.1、3.5 节与 `modern-design-review.md` 第 2.1 节却把它当作华山巡逻任务的核心计时器。
- **事实核查**：`hz_job.c` 仅递减 `duration` 并在归零时返回 0，没有业务逻辑；真正的巡逻打卡依赖 `/d/village/sexit.c` 等房间的 `init()` 设置 `hz_job/*` temp 标记，完成判定在岳不群等 NPC 脚本中（`system-stories.md` 第 7.1 节）。
- **影响**：统一 condition 模型若只看 condition 文件，会漏掉房间 init 与 NPC 校验。建议后续把“巡逻”拆分为“地点触发器集合 + 计时器 + 完成校验器”三层，而不是一个 condition。

### 5.2 龙门镖局 / 都大锦在 source-inventory 中缺失
- **遗漏**：`source-inventory.md` 的关键文件清单表（第 2.1–2.7 节）未列出 `/d/hangzhou/npc/du.c`（都大锦）。
- **但**：`player-stories.md` Story 1.1 明确把“龙门镖局都总镖头”作为少林推荐信的交付目标；`mechanisms.md` 第 1.1、8 节把龙门镖局任务列为驻守/累计类；`modern-design-review.md` 第 4.1 节把“少林 → 龙门镖局”作为新手引导链。
- **影响**：source-inventory 的任务类型清单对“推荐信交付链”覆盖不完整，可能让机制抽象组低估“师门派遣型任务”的复杂度。

### 5.3 斧头帮任务未被玩法切片覆盖
- **遗漏**：`gameplay-slices.md` 6 个切片未包含斧头帮 `ftb_zhu.c` 任务；`source-inventory.md` 仅在第 4.7 节关键词索引末尾提及 `/d/city/npc/ftb_zhu.c`，未进入关键文件清单表。
- **但**：`mechanisms.md` 第 1.1、3.1、3.3、4.2、4.4、8 节与 `modern-design-review.md` 第 3.1 节反复引用该任务，强调其动态地图遍历、自适应奖励、对象列表管理等复杂机制。
- **影响**：Phase 1 切片选择可能遗漏了 LPC 中最具代表性的“程序化生成 + 经济调控”任务类型，导致对声明式 DSL 覆盖度的评估偏乐观。

### 5.4 任务目标类型清单不一致
- **矛盾**：`source-inventory.md` 第 3.2 节“常见任务目标类型”未列出“剧情触发 / flag 解锁 / 守门 / 诵经”等类型；但 `gameplay-slices.md` 切片 6（雪山葛伦布）、`mechanisms.md` 第 3.4/3.5 节、现代设计审视都明确列出这些类型。
- **影响**：目标类型分类框架不统一，建议后续由评审委员会统一术语，并在 `05-synthesis/` 中给出与抽象层映射关系。

### 5.5 黄河帮是否存在显式放弃命令描述不一致
- **矛盾**：`mechanisms.md` 第 5.3 节称“黄河帮：未看到显式放弃命令”，但 `source-inventory.md` 第 6.1 节调用链示例中玩家可向帮主交付错误物品被斥，未体现放弃；`player-stories.md` 中也无黄河帮放弃故事。
- **影响**：若统一模型强制要求每个任务都有“显式放弃”路径，需要确认黄河帮是否真的没有；当前证据支持“无显式放弃”，只有任务覆盖与冷却重置。

### 5.6 现代设计审视与抽象层之间的张力
- **矛盾**：`abstraction-options.md` 第 2 节认为方案 A（声明式 QuestDef）“能覆盖约 30% LPC 常见形态”，方案 B（事件驱动状态机）“约 70%”。但 `modern-design-review.md` 第 5.1 节提出的 objective 类型（`dialogue`、`condition`、`survive`、`faction_reputation` 等）与 `creator-perspective.md` 第 2 节对仙侠/科幻/校园题材所需能力（多层空间、对话树、日程、好感度）的描述，暗示方案 B 的 70% 可能仍然过于乐观，因为大量 LPC 任务的判定逻辑依赖运行时世界状态而非状态机可枚举的事件。
- **影响**：建议把方案 C（受限脚本/行为树）定位为“必要补充”，而不是仅作为远期选项。

---

## 6. 结论：对后续 Phase 2 红队对抗的关键问题

1. **任务状态载体**是否必须统一为玩家中心 `QuestProgress`，还是应承认“物品凭证 + NPC 侧队列 + 全局 daemon”也是合法状态载体？
2. **目标类型**是否需要从“寻/杀/护送/巡逻”等名词抽象，改为“事件 + 守卫 + 副作用”三元组？
3. **奖励通道**是否应在引擎层强制统一，并禁止任何脚本直接写玩家核心属性？
4. **动态对象 / 空间查询 / 自适应奖励**是否应作为 engine 层原子能力暴露，还是留在题材包受限脚本中？
5. **PvP / 强制阵营变更 / 玩家离线处理**是否纳入通用任务模型，还是作为独立的“社交冲突系统”与任务系统解耦？

这些问题将直接影响引擎核心层与题材包创作面的边界划分，建议在 `05-synthesis/` 中给出明确裁决。
