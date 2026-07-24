# 01-quest-system / 03-engine-insights：任务系统题材无关核心抽象可选方向

> 角色：引擎架构师（核心抽象方向）。
> 输入：当前仓库 LPC 任务源码；`engine/src/mud_engine/quest.py` 仅作事后对照，不用于反向裁剪 LPC 发现。
> 输出：设计灵感与可选方向；不给出具体接口契约或代码。

---

## 一、LPC 任务系统的本质特征

### 1.1 任务入口极度分散，NPC 本身就是“任务机”

《侠客行》里没有统一的“任务对象”或“任务管理器”。任务的发放、判定、奖励全部写在具体 NPC 的脚本中：

- 岳不群通过 `ask_job()` 发放华山巡山任务，通过 `check_student()` 在玩家进入房间时检查完成度并结算奖励（来源：`d/huashan/npc/buqun.c`，`ask_job()` 与 `check_student()`）。
- 玄慈方丈通过 `ask_job()` 直接给玩家一封推荐信物品即算任务开始（来源：`d/shaolin/npc/xuan-ci.c`，`ask_job()`）。
- 黄河帮帮主、长乐帮贝海石、明教各掌旗使都有各自的 `ask_job()` 与 `accept_object()`（来源：`d/huanghe/npc/bangzhu_duty.h`、`d/huanghe/npc/guanjia.h`、`d/forest/npc/cl_bei.c`、`d/kunlun/npc/tangyang.c`、`d/kunlun/npc/xinran.c`）。

这说明原始实现是**分散式、强脚本驱动**的：NPC 与任务逻辑紧耦合，任务的生命周期由 NPC 脚本自行维护。

### 1.2 任务状态“随地写”，没有统一持久化层

LPC 任务状态散落在多个地方：

- 玩家对象属性：`huashan/job_pending`、`mingjiao/job`、`bangs/asktime`、`futou_bang/sacrifice` 等（来源：`d/huashan/npc/buqun.c`、`d/kunlun/npc/tangyang.c`、`d/city/npc/ftb_zhu.c`、`d/huanghe/npc/bangzhu_duty.h`）。
- 玩家临时映射：`ob->query_temp("hz_job")`、`ob->query_temp("bangs/fam")`（来源：`d/huashan/npc/buqun.c`、`d/huanghe/npc/bangzhu_duty.h`）。
- 玩家身上物品：少林推荐信 `letter-job`、黄河帮“帮令”`bang ling`、明教“铁焰令”、水桶等，物品本身携带 `owner`、`job` 等字段充当任务凭证（来源：`d/shaolin/npc/xuan-ci.c`、`d/huanghe/npc/bangzhu_duty.h`、`d/kunlun/npc/tangyang.c`）。
- Condition 计时器：`hz_job`、`gb_job`、`ypjob`、`lmjob` 等以 Buff/Debuff 形式存在，通过每秒 `update_condition()` 倒计时，兼具任务限时与随机事件触发（来源：`kungfu/condition/hz_job.c`、`kungfu/condition/gb_job.c`、`kungfu/condition/ypjob.c`、`kungfu/condition/lmjob.c`）。

这种设计让任务系统没有统一模型，但也极灵活——任何脚本都能随时读写状态。

### 1.3 触发条件覆盖对话、物品、击杀、地点、时间、随机事件

从源码可见任务触发/完成条件非常多样：

- **对话触发**：几乎所有 `ask_job()` 都通过玩家输入“任务/job/工作”启动。
- **物品交付**：`accept_object()` 在玩家 give 物品时判定，如黄河帮寻物/截镖、华山青铜令牌、明教火枪（来源：`d/huanghe/npc/bangzhu_duty.h`、`d/huashan/npc/buqun.c`、`d/kunlun/npc/xinran.c`）。
- **击杀计数**：斧头帮任务在玩家击杀刺客后通过 `kill_num` 计数，并清理未击杀目标（来源：`d/city/npc/ftb_zhu.c`，`tell_job()` 中 `kill_num`、`obj_list`）。
- **地点/巡逻**：华山巡山要求玩家 temp 映射长度达到 12，暗示需要进入足够多房间（来源：`d/huashan/npc/buqun.c`，`check_student()`）。
- **时间/限时**：几乎所有任务都有 `time()` 冷却或 Condition 倒计时；一品堂“青铁令”超时直接记失败（来源：`kungfu/condition/ypjob.c`）。
- **随机事件/小游戏**：星宿“找毒虫”在 `search` 命令中随机刷怪、随机掉落金钱、随机出现正派杀手；丐帮任务在计时过程中随机丢失密函（来源：`d/xingxiu/xx_job.h`、`kungfu/condition/gb_job.c`）。

### 1.4 奖励结算同样脚本化

奖励不是由某个中央“奖励服务”统一计算后下发，而是由 NPC 脚本直接修改玩家数值：

- 经验、潜能、金钱、最大内力、最大精力、神值（善恶）都直接在脚本里 `add()`（来源：`d/huashan/npc/buqun.c`、`d/city/npc/ftb_zhu.c`、`d/huanghe/npc/bangzhu_duty.h`、`d/kunlun/npc/mingjiao_job.h` 的 `reward()`）。
- 黄河帮还用“帮令”上的 `score` 作为功绩点，再拿功绩点换武功学习次数（来源：`d/huanghe/npc/bangzhu_duty.h`，`ask_skills()` / `do_xue()`）。
- 明教任务奖励同时提升“明教忠诚度”（`mingjiao/cc`），这是一种阵营声望（来源：`d/kunlun/npc/mingjiao_job.h`，`reward()`）。

### 1.5 存在两层“集中式调控”，但都不是通用任务核心

第一层是 `clone/obj/job_server.c`：它只负责“每小时经验/潜能上限”与“奖励统计直方图”。任务脚本在开始时调用 `start_job()` 记录时间，完成时调用 `reward()` 并由其按公式 `exp_limit * exp_rate * (duration) / 360000` 发放奖励（来源：`clone/obj/job_server.c`，`start_job()`、`reward_func()`）。它本质上是**刷怪/日常任务的宏观调控器**，不是任务定义本身。

第二层是 `/d/wizard/center.c` 引用的 `/clone/obj/job/job_data`、`job_menpai`、`job_produce`：这是一个世界级别的“主动性任务系统”，管理门派幸运、金钱系数、策略、势力、贡献度、在线玩家任务名单（`ask_job`/`oppose_pker`/`finish_job`）等（来源：`d/wizard/center.c`，`do_start_system()`、`do_check_do_job()`、`do_setorg_*`、`do_check_menpai_*`）。`clone/obj/job.sav/` 下的对应文件为二进制/编码保存文件，无法直接阅读文本，但 `center.c` 的调用关系足以说明存在**独立于 NPC 的全局任务调度层**。这层属于内容/运营配置，不是通用任务模型。

### 1.6 任务逻辑与玩法脚本深度纠缠

LPC 任务不只是“接—做—交”三段式，而是常常绑定具体玩法：

- 斧头帮任务会动态遍历地图、在目标房间周围生成刺客 NPC，并记录每个刺客对象（来源：`d/city/npc/ftb_zhu.c`，`find_target_room()`、`put_objects()`）。
- 黄河帮“截镖”会动态创建镖头 NPC 并移动到具体房间；“护驾”会创建一个副本帮主 NPC 并设置跟随玩家（来源：`d/huanghe/npc/bangzhu_duty.h`，`ask_job()` 中“截镖”、“护驾”分支）。
- 明教五旗任务需要采集、打造、挑水、砍树、挖地道等多步骤，各步骤状态靠玩家属性 + 临时变量 + 物品共同维持（来源：`d/kunlun/npc/mingjiao_job.h`，`judge_jobmsg()`）。

---

## 二、题材无关核心模型的可选抽象方案

下面给出三种**互不排斥、可按阶段叠加**的抽象方向，按“创作者友好”到“表达力最强”排序。

### 方案 A：声明式 QuestDef（轻量 DSL）

**核心思想**

任务以声明式定义为主：一个任务 = 接取条件 + 完成目标 + 奖励 + 文本。引擎负责加载、接取判定、完成判定、持久化。这是当前 `engine/src/mud_engine/quest.py` 已经走的路线（事后对照）：`QuestDef` 包含 `require_npc`、`give_item`、`to_npc`、`required_flags`、`reward_currency` 等字段，`QuestProgress` 保存玩家状态（来源：`engine/src/mud_engine/quest.py`，`QuestDef`、`accept_quest()`、`try_complete_quest_on_give()`、`set_quest_flag()`）。

**对 LPC 机制的覆盖度**

- 能覆盖：对话接取、同处一室 NPC 判定、交物品完成、flag 完成、固定货币奖励。
- 难以覆盖：动态刷怪、多步骤流程、限时/Condition、随机事件、击杀计数、NPC 跟随/护驾、技能/声望/属性混合奖励、自适应奖励公式（如斧头帮按范围、时间、击杀数综合计算）。

**优点**

- 对 UGC 创作者最友好：声明 YAML/JSON 即可，不需要写脚本。
- 引擎可完全控制生命周期，便于验证、测试、AI 导航、本地化。
- 与当前 engine 草案自然衔接，MVP 可以先用它实现“送信/寻物/flag”类简单任务。

**缺点与取舍**

- 表达力天花板低，复杂任务必须“逃逸”到脚本或扩展钩子。
- 若把太多 LPC 特例硬塞进声明字段，会导致 DSL 字段爆炸，反而失去简洁优势。

### 方案 B：事件驱动状态机（Quest State Machine）

**核心思想**

每个任务有一个运行时实例，包含若干状态与迁移。迁移由世界事件触发：`on_talk`、`on_give`、`on_kill`、`on_enter`、`on_timer`、`on_flag`。每条迁移可带守卫条件（guard）与动作（action）。引擎提供统一的事件总线、计时器、flag 服务和奖励通道。

**对 LPC 机制的覆盖度**

- 能覆盖：
  - 对话接取（`on_talk` 迁移到 active）。
  - 交物品完成（`on_give` + guard 匹配 item + npc）。
  - 击杀计数/击杀目标（`on_kill` 累加计数器）。
  - 进入房间/巡逻（`on_enter` 检查房间集合是否遍历完）。
  - 限时/超时（`on_timer` 触发失败或强制结算）。
  - 随机分支（迁移 guard 中使用随机权重）。
  - 动态生成 NPC/物品（action 调用引擎的 spawn 服务）。
- 较难覆盖：需要复杂地图遍历、根据玩家强度实时调整敌人属性、需要跨越多个独立脚本的“全局任务系统”。

**优点**

- 在创作者可控性与表达力之间取得较好平衡。
- 状态机天然适合可视化编辑器（节点图），为后续 UGC Web 平台留下扩展点。
- 引擎仍能在状态层做安全校验（如禁止非法迁移、限制动作白名单）。

**缺点与取舍**

- 比纯声明式复杂，需要定义事件类型、guard 表达式、动作原语。
- 对于“搜索毒虫”这种带大量随机小游戏的玩法，状态机仍会显得笨重，需要动作脚本补充。

### 方案 C：脚本化 Behavior Tree / 受限脚本钩子

**核心思想**

任务是一棵行为树或一段受限脚本，引擎只提供节点库/ API 原语：接取、等待事件、生成 NPC、移动 NPC、检查背包、给予奖励、设置 flag、播放文本等。创作者可以组合节点或写简短脚本来实现任意 LPC 式任务。

**对 LPC 机制的覆盖度**

- 几乎可以完整覆盖 LPC 源码中的任意任务形态，包括：
  - 动态地图遍历与刺客生成（斧头帮）。
  - 多步骤采集打造（明教五旗）。
  - search 命令小游戏与随机遭遇（星宿）。
  - 护驾/跟随 NPC、镖车移动、截镖。
  - 自适应奖励公式、牺牲补偿、溢出保护。

**优点**

- 表达力最强，能忠实保留原作自由度。
- 对已有 LPC 设计者迁移心理成本低。

**缺点与取舍**

- 安全与性能风险：UGC 脚本若不受限，可能死循环、刷资源、破坏世界状态。
- 可验证性差：AI 难以自动分析脚本任务是否可完成、是否有死路。
- 与当前 engine 追求的“声明式内容包 + 受限脚本”方向存在张力；若采用，必须配套沙箱、资源配额、审计日志。

### 三种方案的比较与建议取舍

| 维度 | 方案 A 声明式 QuestDef | 方案 B 事件驱动状态机 | 方案 C 脚本化 BT/钩子 |
|------|------------------------|----------------------|------------------------|
| 创作者门槛 | 低 | 中 | 高（需脚本/节点逻辑） |
| 表达力 | 低-中 | 中-高 | 高 |
| 引擎可控性 | 高 | 中 | 低（需沙箱） |
| 可测试/AI 导航 | 高 | 中 | 低 |
| 对 LPC 常见形态的覆盖 | 约 30%（简单任务） | 约 70% | 约 95% |
| UGC 安全 | 高 | 中 | 低（需额外限制） |

**建议**：新引擎不必在“核心层”选择单一方案，而应分层：

1. **核心层只保留最小概念**（Quest/Objective/Reward/Trigger/Condition/Log）。
2. **默认实现采用方案 A** 满足 MVP 简单任务，并留出扩展点。
3. **复杂任务通过方案 B 的状态机扩展**，或在未来通过方案 C 的受限脚本钩子实现。
4. 无论哪种方案，**奖励应统一走引擎奖励通道**，而不是让脚本直接修改玩家属性。

---

## 三、必须保留的最小核心概念

基于 LPC 源码的共性，题材无关的引擎任务核心至少应包含以下概念：

1. **Quest / QuestDef（任务定义）与 QuestInstance（玩家侧运行时实例）**
   - 对应 LPC 中每个 NPC 的 `ask_job()` 及其维护的玩家属性。没有这一层就无法区分“哪些任务是独立任务”。
   - 来源：`d/huashan/npc/buqun.c` 的 `huashan/job_pending`、`d/kunlun/npc/mingjiao_job.h` 的 `mingjiao/job`、`d/city/npc/ftb_zhu.c` 的 `JOB_NAME`。

2. **Objective / Condition（目标与条件）**
   - LPC 中的目标形态包括：持有/交付物品、击杀指定 NPC、进入指定房间集合、限时存活、积累临时计数等。
   - 来源：`d/huanghe/bangjob/bangjob*.c` 中的 `type`（“寻/杀/截镖/示威/送礼/护驾/摊费”）、`d/huashan/npc/buqun.c` 的 `sizeof(job_stat) < 12`、`d/city/npc/ftb_zhu.c` 的 `kill_num`/`obj_num`。

3. **Reward（奖励）**
   - 经验、潜能、金钱、物品、声望/贡献度都频繁出现。核心层至少应支持“货币/经验/潜能/物品”这类通用奖励，声望则作为题材包扩展。
   - 来源：`d/huashan/npc/buqun.c`、`d/city/npc/ftb_zhu.c`、`d/huanghe/npc/bangzhu_duty.h`、`d/kunlun/npc/mingjiao_job.h` 的奖励代码。

4. **Trigger（触发器）**
   - 包括接取触发（对话/同处一室）、推进触发（击杀/进入/获得物品）、完成触发（交物品/flag 全满）、超时触发（Condition 归零）。
   - 来源：`d/shaolin/npc/xuan-ci.c`（对话给信）、`d/huashan/npc/buqun.c`（房间进入检查）、`kungfu/condition/ypjob.c`（超时失败）、`d/city/npc/ftb_zhu.c`（击杀计数）。

5. **Condition / Timer（限时与状态条件）**
   - LPC 大量使用 Condition 文件做倒计时，并在倒计时中插入副作用。核心层应支持“任务存在有效时间”以及“周期性/一次性检查”。
   - 来源：`kungfu/condition/hz_job.c`、`kungfu/condition/gb_job.c`、`kungfu/condition/ypjob.c`、`kungfu/condition/lmjob.c`。

6. **Log / QuestProgress（任务日志与持久化）**
   - LPC 用玩家属性、临时映射、物品共同充当日志。引擎核心应提供统一的玩家任务进度组件，进存档。
   - 来源：遍布各 NPC 脚本的 `player->set(...)`/`player->query_temp(...)`；与 `engine/src/mud_engine/quest.py` 的 `QuestProgress` 形成对照。

---

## 四、明确的反模式：哪些 LPC 设计不应进入引擎核心

以下做法在 LPC 中普遍存在，但属于**内容实现细节或历史包袱**，不应被固化为题材无关引擎核心的一部分。

1. **把 NPC 脚本直接作为任务系统**
   - LPC 中每个 NPC 都自己实现接取、判定、奖励，导致逻辑碎片化、难以检索、无法做统一日志。
   - 来源：`d/huashan/npc/buqun.c`、`d/shaolin/npc/xuan-ci.c`、`d/huanghe/npc/bangzhu_duty.h` 等大量 NPC 的 `ask_job()`。

2. **用玩家身上物品充当任务凭证或进度存储**
   - 黄河帮“帮令”记录 `job` 映射，少林推荐信记录 `owner`，明教水桶记录挑水次数。物品丢失/复制会导致任务状态异常。
   - 来源：`d/huanghe/npc/bangzhu_duty.h` 中 `ling->set("job", job)`、`d/shaolin/npc/xuan-ci.c` 中 `obj->set("owner", me->query("id"))`、`d/kunlun/npc/tangyang.c` 中水桶物品与 `water_amount`。

3. **让脚本直接修改玩家核心属性作为奖励**
   - LPC 中 NPC 直接 `add("combat_exp")`、`add("potential")`、`add("max_neili")`、`add("shen")`。新引擎应通过统一的奖励/Effect 通道下发，便于审计、防止溢出、支持双货币账本与未来商业化埋点。
   - 来源：`d/huashan/npc/buqun.c`（`add("combat_exp")`、`add("potential")`）、`d/city/npc/ftb_zhu.c`（`add("max_neili")`、`add("eff_jingli")`、给予黄金）、`d/kunlun/npc/mingjiao_job.h` 的 `reward()`。

4. **把任务专属宏观调控（job_server）当作通用任务核心**
   - `job_server.c` 只负责“每小时经验/潜能上限”与“奖励统计直方图”，本质是日常/刷怪任务的运营平衡器，不应成为通用任务模型的一部分。
   - 来源：`clone/obj/job_server.c`，`set_exp_limit_func()`、`reward_func()` 中的 `exp_limit * exp_rate * (time_now - start_time) / 360000`。

5. **把世界级门派政治系统混入任务核心**
   - `/d/wizard/center.c` 管理的门派幸运、金钱系数、策略、势力、贡献度、在线任务名单（`ask_job`/`oppose_pker`/`finish_job`）属于武侠题材包的世界事件/阵营系统，不是题材无关任务抽象。
   - 来源：`d/wizard/center.c`，`do_start_system()`、`do_check_do_job()`、`do_setorg_*`、`do_check_menpai_*`。

6. **把动态地图遍历与运行时 NPC 生成作为核心原语**
   - 斧头帮的动态地图选点、范围生成刺客，黄河帮的“截镖”生成镖头、“护驾”生成跟随 NPC，本质上是关卡/Encounter 服务的能力。任务系统可以调用，但不应把这些机制内建为核心原语。
   - 来源：`d/city/npc/ftb_zhu.c` 的 `find_target_room()`、`put_objects()`；`d/huanghe/npc/bangzhu_duty.h` 的“截镖”、“护驾”分支。

7. **把 Condition 文件的副作用当作任务条件**
   - `kungfu/condition/*.c` 是角色状态效果（计时/Debuff），丐帮任务在倒计时中随机丢失密函更是副作用。任务系统应订阅事件或订阅计时器，而不是把任务逻辑直接写在 Condition 脚本里。
   - 来源：`kungfu/condition/gb_job.c`（随机丢信）、`kungfu/condition/hz_job.c`（纯倒计时）。

8. **把硬编码门派/身份/辈分检查作为核心任务条件**
   - `family_name`、`generation`、`class`、特定信物（铁焰令）等属于内容包设定。引擎核心只应提供通用的前置条件槽位，由题材包填充具体规则。
   - 来源：`d/huashan/npc/buqun.c`（`family/family_name == "华山派"`）、`d/shaolin/npc/xuan-ci.c`（`generation > 37`、`class == "bonze"`）、`d/kunlun/npc/tangyang.c`（`family_name == "明教"`、要求 `tieyan ling`）。

9. **把自适应/补偿性奖励公式固化到核心**
   - 斧头帮根据搜索范围、击杀比例、耗时、牺牲次数、玩家总经验进行复杂公式调整，还包括“超过 6M 经验衰减”和“丐帮系数惩罚”。这些都是内容平衡策略，应由内容包配置，而不是写死在引擎核心。
   - 来源：`d/city/npc/ftb_zhu.c`，`tell_job()` 中 `rate`、`exp_rate`、`sacrifice` 计算与 `adjust_rate()`。

10. **把任务失败惩罚（忠诚度扣除）作为核心机制**
    - 明教放弃任务会扣除“明教忠诚度”，这是阵营玩法的一部分，不是通用任务概念。
    - 来源：`d/kunlun/npc/mingjiao_job.h`，`cut_abandon_jl()`。

---

## 五、与现有 engine 草案的对照（仅作事后参考）

当前 `engine/src/mud_engine/quest.py` 已经实现了方案 A 的雏形：

- 以 `QuestDef` 承载任务定义（`quest_id`、`name`、`require_npc`、`give_item`、`to_npc`、`required_flags`、`reward_currency`）。
- 以 `QuestProgress` 承载玩家进度（`quests`、`flags`）。
- 以 `accept_quest()`、`try_complete_quest_on_give()`、`set_quest_flag()` 处理接取与两类完成方式（交物品、flag 全满）。
- 来源：`engine/src/mud_engine/quest.py`。

这一实现覆盖了 LPC 中最常见的“对话接取 + 交物品/flag 完成 + 货币奖励”形态，但无法覆盖动态刷怪、限时、击杀计数、多步骤、声望奖励、技能奖励等复杂形态。因此后续抽象决策可以考虑：

- **MVP 阶段**：沿用并扩展声明式 `QuestDef`，优先支持物品交付、flag 完成、基础奖励。
- **MVP 之后**：引入事件驱动状态机作为扩展层，让复杂任务（巡逻、限时击杀、护送）不依赖全功能脚本。
- **远期**：在受控沙箱内提供受限脚本钩子，仅用于无法被状态机表达的极端玩法。
