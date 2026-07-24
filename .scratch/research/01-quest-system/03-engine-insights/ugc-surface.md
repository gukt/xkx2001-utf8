# 题材包创作层应暴露的最小任务创作表面

> 角色：引擎架构师（题材包扩展方向）。
> 输入：当前仓库 LPC 任务源码、`engine/src/mud_engine/quest.py` 仅作事后对照，不用于反向裁剪 LPC 发现。
> 输出：设计灵感与可选方向；不给出具体接口契约或代码。

---

## 一、LPC 任务创作的本质：创作者当前需要改哪些文件、写哪些回调

《侠客行》的任务不是由单一工具生成的，而是**以 NPC 为中心、分散在四到五类对象中的代码产物**。一个可玩任务上线，创作者通常要同时改动以下内容：

### 1.1 NPC 文件：任务的发放机、判定机与奖励机

- 在 NPC 的 `set("inquiry", ...)` 中注册触发词，如 `"还愿"`、`"任务"`、`"job"`、`"帮务"`，由玩家 `ask <npc> about <topic>` 触发。
  - 证据：`/cmds/std/ask.c::main()` 调用 `ob->query("inquiry/" + topic)` 并执行对应函数；`/d/xueshan/npc/gelun1.c` 的 `inquiry` 将 `"还愿"`/`"烧香"`/`"供佛"` 映射到 `do_huanyuan()`（行 44-48）。
- 在 NPC 中写 `ask_job()` 或同类回调，完成：
  - 前置校验（门派、辈分、性别、经验、声望、已有任务、冷却时间）；
  - 目标生成（随机抽任务池、动态生成 NPC/物品、分配目的地）；
  - 玩家状态写入（`player->set("mingjiao/job", ...)`、`player->set_temp("biao/dest", ...)`）。
  - 证据：`/d/kunlun/npc/mingjiao_job.h` 中 `judge_jobmsg()` 维护工种映射（行 8-41）；`/d/city/npc/biao_assign.h::ask_biao()` 随机分配 5 个目的地之一并写入 `temp/biao/*`（行 52-95）；`/d/huanghe/npc/bangzhu_duty.h::ask_job()` 按经验分档选择 `/d/huanghe/bangjob/bangjob<N>.c` 的任务池（行 77-136）。
- 在 NPC 中写 `accept_object()`，用于交付物品时判定任务完成并结算奖励。
  - 证据：`/d/xueshan/npc/gelun1.c::accept_object()` 按 `ob->name()=="酥油罐"` 判定并设置 `temp("marks/酥", 1)`（行 61-72）；`/d/huanghe/npc/bangzhu_duty.h::accept_object()` 按任务 `type`（寻/截镖）结算（行 277-333）；`/d/kunlun/npc/mingjiao_job.h` 的 `reward()` 由掌旗使 `accept_object()` 调用后发放经验、潜能、忠诚度（行 122-169）。

### 1.2 任务池/配置表：随机目标的数据源

- 帮派/教务任务通常把目标列表单独放在按经验分档的文件中，NPC 运行时 `random()` 抽取。
  - 证据：`/d/huanghe/bangjob/bangjob3000.c` 与 `bangjob50000.c` 用 `mapping *bangjobs` 定义 `"杀"`/`"寻"`/`"截镖"` 条目，含 `name`/`file`/`area`/`type`/`bonus`/`score`（行 9-637 与行 8-418）；`/d/shenlong/sgjob/sgjob20000.c` 与 `sgjob500000.c` 用 `mapping *sgjobs` 定义 `"寻"`/`"FORCEJOIN"`/`"PK"` 条目（行 8-159 与行 8-324）。

### 1.3 玩家状态：任务进度的实际存储

- 任务进度大量依赖玩家对象的 dbase 键值对，包括持久属性与 `temp` 临时属性。
  - 证据：`/d/city/npc/biao_assign.h::ask_biao()` 写入 `temp/biao/zhu`、`temp/biao/pending`、`temp/biao/times`（行 54-85）；`/d/huanghe/npc/bangzhu_duty.h::ask_join()` 写入 `bangs/jointime`、`temp/bangs/fam`（行 45-69）；`/d/kunlun/npc/mingjiao_job.h::reward()` 删除 `mingjiao/job`（行 158）。

### 1.4 任务物品：既是剧情道具，也是状态凭证

- 推荐信、帮令、镖货、水桶等物品本身携带 `owner`、`job`、`dest` 等字段，NPC 通过物品属性反查任务。
  - 证据：`/d/city/npc/biao_assign.h::ask_biao()` 生成 `/d/city/obj/biaohuo1` 并写入 `temp/guard`、`temp/dest`、`temp/prop`（行 88-124）；`/d/huanghe/npc/bangzhu_duty.h::ask_job()` 为 `"送礼"` 任务生成 `CAILI` 并写入 `job`/`owner`（行 223-238）。

### 1.5 条件（Condition）文件：限时与周期性事件

- 大量任务用 `/kungfu/condition/*.c` 做倒计时，并在 `update_condition()` 中处理失败或随机事件。
  - 证据：`/kungfu/condition/biaoju.c` 在 duration 归零时删除 `biao/*` 并置 `biao/fail`（来源：`source-inventory.md` 2.3 节与 `gameplay-slices.md` 切片 2）；`/kungfu/condition/ypjob.c` 在 duration 到 1 时增加 `yipin/failure`（来源：`mechanisms.md` 5.1 节）。

### 1.6 全局奖励/运营伺服器

- `job_server.c` 负责按时间计酬、经验/潜能上限、统计直方图；`center.c` 负责主动性任务系统的全局开关与参数配置。
  - 证据：`/clone/obj/job_server.c::reward_func()` 按 `exp_limit*exp_rate*(time_now-start_time)/360000` 结算（行 583-588），并提供 `set_exp_limit_func()`、`get_job_hist_func()` 等运营接口（行 541-718）；`/d/wizard/center.c::do_start_system()` / `do_close_system()` 控制 `/clone/obj/job/job_data` 与 `job_system`（行 629-682）。

**本质概括**：LPC 任务创作是**以 NPC 脚本为粘合剂，把玩家状态、任务物品、条件计时器、任务池、全局伺服器拼接起来的过程**。没有统一的任务对象，也没有统一的任务生命周期接口。

---

## 二、题材包创作层应提供的声明式能力清单

基于 LPC 源码反复出现的模式，题材包创作层至少应把以下能力暴露为声明式配置（而非代码）：

### 2.1 任务定义（QuestDef）

- 任务 ID、名称、描述、是否可重复、是否互斥。
- 接取 NPC（`require_npc`）、完成 NPC（`to_npc`）、交付物品（`give_item`）。
- 证据：当前 `engine/src/mud_engine/quest.py::QuestDef` 已包含 `quest_id`、`name`、`require_npc`、`give_item`、`to_npc`、`required_flags`、`reward_currency`、`accept_message`、`complete_message`（行 31-44），覆盖了 LPC 中最常见的"对话接取 + 交物品/flag 完成 + 货币奖励"形态（来源：`abstraction-options.md` 五、与现有 engine 草案的对照）。

### 2.2 目标（Objective）

- **寻物/交付**：指定物品模板、交付 NPC、是否销毁物品。
  - 证据：`/d/huanghe/bangjob/bangjob3000.c` 中大量 `"type":"寻"` 条目（行 203-503）；`/d/xueshan/npc/gelun1.c::accept_object()` 按名称判定交付物（行 61-72）。
- **击杀指定 NPC**：目标模板、数量、所在区域/房间。
  - 证据：`/d/huanghe/bangjob/bangjob50000.c` 中 `"type":"杀"` 条目含 `name`、`file`、`area`、`bonus`、`score`（行 8-160）。
- **到达/巡逻**：目标房间集合、是否需要按顺序访问。
  - 证据：`/kungfu/condition/hz_job.c` 配合多个房间的 `init()` 设置 `hz_job/*` temp 标记（来源：`mechanisms.md` 3.5 节）。
- **守卫/驻守**：指定地点、持续时间、防守波次。
  - 证据：`/d/beijing/npc/duolong.c::ask_job()` 分配 `outer_gate_name`/`inner_gate_name`，`/d/beijing/outer_gate.h::do_guard()` 执行守卫（来源：`source-inventory.md` 2.6 节与 `gameplay-slices.md` 切片 5）。

### 2.3 触发器（Trigger）

- 对话触发：关键词 → 接取/推进/完成。
- 物品交付触发：`accept_object` 等价事件。
- 击杀触发：`on_kill` 计数。
- 地点触发：`on_enter` / `on_leave`。
- 时间触发：绝对时间（日出/日落/时辰）、相对 CD、倒计时。
  - 证据：`/d/beijing/npc/duolong.c::ask_job()` 用 `HELPER->is_sunrise()` / `is_sunset()` 决定班次；`/d/huanghe/npc/bangzhu_duty.h::ask_job()` 用 `time() < bangs/asktime + 180` 做冷却（来源：`mechanisms.md` 2.4 节）。

### 2.4 奖励（Reward）

- 通用奖励表：经验、潜能、货币、物品、声望/贡献度、技能熟练度、称号。
  - 证据：明教 `mingjiao_job.h::reward()` 发放忠诚度、经验、潜能（行 122-169）；黄河帮 `bangzhu_duty.h::accept_object()` 发放经验、`shen`、帮令 `score`（行 293-328）。
- 奖励上限与速率控制：按任务维度的小时上限、玩家日/周累计上限。
  - 证据：`/clone/obj/job_server.c::set_exp_limit_func()` / `set_pot_limit_func()`（行 541-551）。

### 2.5 限时与失败条件

- 任务存在有效时间；超时自动失败并清理状态。
- 失败/放弃惩罚：扣除声望/贡献、进入冷却、计数失败次数。
  - 证据：`/d/kunlun/npc/mingjiao_job.h::cut_abandon_jl()` 按工种扣除 `mingjiao/cc`（行 43-76）；`/kungfu/condition/ypjob.c` 超时增加 `yipin/failure`（来源：`mechanisms.md` 5.1 节）。

### 2.6 并发、限额与等级匹配

- 同类型任务互斥、全局任务数量上限、每日/每周次数上限。
- 按玩家经验/等级分档选择任务池。
  - 证据：`/d/huanghe/npc/bangzhu_duty.h::ask_job()` 用 `levels` 数组与 `(4*exp+random(2*exp))/5` 做分档匹配（行 85-132）；`/d/shenlong/sgjob/sgjob*.c` 按经验分档（来源：`source-inventory.md` 2.5 节）。

### 2.7 运营观测接口

- 任务统计、单玩家追踪、奖励直方图、全局开关、异常清理。
  - 证据：`/clone/obj/job_server.c::get_job_stat_func()`、`get_job_hist_func()`（行 684-695）；`/d/wizard/center.c::do_check_player()`、`do_check_do_job()`、`do_cut_job()`（行 685-864）。

---

## 三、必须保留的"脚本钩子"或"自定义回调"点

纯声明式无法覆盖 LPC 中大量**与具体玩法深度纠缠**的任务形态。以下能力必须保留为受限脚本/钩子，供高级创作者在声明式骨架上扩展：

### 3.1 动态目标生成与地图遍历

- 斧头帮任务会动态遍历地图、在目标房间周围生成刺客 NPC；黄河帮"截镖"动态创建镖头并移动到具体房间。
  - 证据：`/d/city/npc/ftb_zhu.c::find_target_room()`、`put_objects()`（来源：`abstraction-options.md` 1.6 节与 `creator-perspective.md` 3.2 节）；`/d/huanghe/npc/bangzhu_duty.h::ask_job()` "截镖"分支用 `children(BIAOTOU)` 做全局数量限制并 `new(BIAOTOU)->move(dest)`（行 163-206）。

### 3.2 NPC 跟随/护驾/镖车移动

- 黄河帮"护驾"创建帮主分身并 `set_leader(me)`，随玩家移动到目标区域。
  - 证据：`/d/huanghe/npc/bangzhu_duty.h::ask_job()` "护驾"分支生成 `BANGZHU2` 并设置 `set_leader(me)`（行 241-263）。

### 3.3 搜索/采集类小游戏与随机遭遇

- 星宿"找毒虫"在 `search bug` 命令中随机刷怪、随机掉落金钱、随机出现正派杀手。
  - 证据：`/d/xingxiu/xx_job.h::do_search()`（来源：`gameplay-slices.md` 切片 4.2 与 `mechanisms.md` 2.3 节）。

### 3.4 多步骤制造/加工链

- 明教五旗任务需要采集铁矿、打造火枪、挑水、砍树、挖地道等多步骤，各步骤状态靠玩家属性 + 临时变量 + 物品共同维持。
  - 证据：`/d/kunlun/npc/mingjiao_job.h` 的 `judge_jobmsg()` 列出五种工种，`reward()` 按工种给不同忠诚度/经验/潜能（行 8-169）。

### 3.5 玩家间 PvP / 强制交互任务

- 神龙教教务包含 `FORCEJOIN`（威逼入教）与 `PK`（追杀玩家），目标是在线玩家或 livings() 中筛选的候选者。
  - 证据：`/d/shenlong/sgjob/sgjob20000.c` 与 `sgjob500000.c` 含大量 `FORCEJOIN`/`PK` 占位条目（行 107-148 与行 308-316）；`/d/shenlong/obj/sg_mianzhao.c::do_forcejoin()`、`do_sign()` 完成交互（来源：`gameplay-slices.md` 切片 5）。

### 3.6 自适应/补偿性奖励公式

- 黄河帮击杀奖励 `bonus = job["bonus"] * job["max"] / (combat_exp + 1000)`，截镖奖励 `bonus = exp * 120 / (exp + combat_exp)`；斧头帮根据搜索范围、击杀比例、耗时、牺牲次数综合调整。
  - 证据：`/d/huanghe/npc/bangzhu_duty.h::accept_object()`（行 293-328）；`/d/city/npc/ftb_zhu.c::tell_job()` / `adjust_rate()`（来源：`abstraction-options.md` 四、9）。

### 3.7 世界事件/全局任务系统

- `/d/wizard/center.c` 管理的门派幸运、金钱系数、策略、势力、贡献度、在线任务名单属于世界级别的主动任务系统，不是单任务声明能表达的。
  - 证据：`/d/wizard/center.c::do_start_system()`、`do_setorg_*()`、`do_check_menpai_job()`（行 629-682、行 985-1118）。

---

## 四、创作者友好性评估：哪些 LPC 机制容易声明化，哪些必须保留代码

| 机制 | 声明化难度 | 说明 | 证据来源 |
|------|-----------|------|---------|
| 对话接取 + 固定文本 | 低 | 将 `inquiry` 映射与 `ask_job()` 前置校验转为声明字段即可。 | `/d/xueshan/npc/gelun1.c` `inquiry`（行 44-48）；`/cmds/std/ask.c::main()`（行 31-73）。 |
| 寻物/交付任务 | 低 | 物品模板、交付 NPC、奖励表均可声明。 | `/d/huanghe/bangjob/bangjob3000.c` `"寻"` 条目；`gelun1.c::accept_object()`。 |
| 击杀指定 NPC 任务 | 低-中 | 目标模板、数量、区域可声明；动态生成与全局配额需要钩子。 | `/d/huanghe/bangjob/bangjob50000.c` `"杀"` 条目。 |
| 到达/巡逻/守卫 | 中 | 房间集合、顺序、持续时间可声明；但防守波次生成需要钩子。 | `/kungfu/condition/hz_job.c` + 多房间 `init()`；`/d/beijing/outer_gate.h::do_guard()`。 |
| 经验分档任务池 | 中 | 分档规则、任务池条目可声明；匹配公式可由引擎统一。 | `/d/huanghe/npc/bangzhu_duty.h::ask_job()`（行 85-132）；`/d/shenlong/sgjob/sgjob*.c`。 |
| 限时/冷却/失败 | 中 | duration、CD、失败惩罚类型可声明；但随机丢失物品等副作用需要钩子。 | `/kungfu/condition/ypjob.c`；`/kungfu/condition/gb_job.c`（来源：`mechanisms.md` 5.1 节）。 |
| 护送/跟随 NPC | 高 | 路径跟随、NPC 状态同步、目的地判定需要脚本支持。 | `/d/huanghe/npc/bangzhu_duty.h` "护驾"分支。 |
| 动态地图遍历与生成 | 高 | 需要调用引擎的地图/Encounter 服务，无法纯声明。 | `/d/city/npc/ftb_zhu.c::find_target_room()` / `put_objects()`。 |
| 搜索/采集小游戏 | 高 | 随机遭遇、多步骤加工、状态组合需要脚本。 | `/d/xingxiu/xx_job.h::do_search()`；`/d/kunlun/npc/mingjiao_job.h`。 |
| PvP / FORCEJOIN | 高 | 目标筛选、在线玩家交互、成功率判定需要脚本。 | `/d/shenlong/sgjob/sgjob*.c`；`/d/shenlong/obj/sg_mianzhao.c`。 |
| 自适应奖励公式 | 高 | 内容平衡策略应由题材包配置或脚本，不应固化到引擎。 | `/d/huanghe/npc/bangzhu_duty.h::accept_object()`；`/d/city/npc/ftb_zhu.c::adjust_rate()`。 |
| 世界政治/主动任务系统 | 高 | 属于全局运营系统，不是单任务创作面。 | `/d/wizard/center.c`。 |

**评估结论**：约 60%-70% 的 LPC 常见任务形态可以通过"声明式 QuestDef + 有限目标库 + 触发器"覆盖；剩余 30%-40% 的高自由度玩法需要保留脚本钩子，但应通过**白名单 API** 和**沙箱**限制其能力边界。

---

## 五、对 DSL / JSON / YAML / Python 等创作层形态的方向性建议

以下仅为方向性建议，不定稿具体格式。

### 5.1 分层创作模型

建议采用**三层递进**模型，与 `abstraction-options.md` 中的方案 A/B/C 保持一致：

1. **声明层（YAML/JSON）**：覆盖最常见的接取/交付/击杀/flag/奖励任务。这是 UGC 创作者的主要界面，门槛低、可验证性强。
2. **状态机层（JSON/YAML 描述的状态迁移）**：覆盖巡逻、限时击杀、护送等多步骤任务。迁移事件包括 `on_talk`、`on_give`、`on_kill`、`on_enter`、`on_timer` 等。
3. **受限脚本层（Python 子集）**：仅用于无法被前两层表达的极端玩法（动态生成、PvP、小游戏、自适应公式）。脚本运行在引擎沙箱中，禁止直接修改玩家核心属性、禁止写文件系统、禁止无限制循环。

### 5.2 优先 YAML/JSON 作为默认形态

- 与当前 `engine/src/mud_engine/quest.py::QuestDef` 的自然形态对齐，便于场景包加载与版本管理。
- 字段设计应避免"把 LPC 特例硬塞进去导致 DSL 字段爆炸"（参见 `abstraction-options.md` 方案 A 的缺点）。
- 奖励、限时、失败条件等应作为可复用原语，而不是每个任务独立写公式。

### 5.3 脚本钩子走受限 Python 而非开放 LPC

- 旧方案教训：UGC 脚本应使用受限 Python 而非 WASM（参见 `CLAUDE.md` 架构不变量第 5 条）。
- 脚本只能调用引擎提供的白名单 API：生成 NPC/物品、查询玩家属性（只读）、设置任务 flag、发送消息、记录日志。
- 奖励必须统一走引擎奖励通道，脚本不能直接 `add("combat_exp")` 或 `add("potential")`（参见 `creator-perspective.md` 4.2 节）。

### 5.4 运营与治理内建

- 题材包应能声明每个任务的 `exp_limit`/`pot_limit`、每日上限、失败率阈值，引擎自动采样并告警。
- 全局开关、单玩家追踪、版本回滚应作为引擎默认能力，而不是每个题材包重复实现（参见 `creator-perspective.md` 5.3 节）。

### 5.5 避免把内容实现细节固化为核心

- 硬编码门派/身份/辈分检查、自适应奖励公式、忠诚度扣除、全服广播等应留在题材包配置或脚本中，不进入题材无关的引擎核心（参见 `abstraction-options.md` 四、明确的反模式）。

---

## 六、结论

1. LPC 任务创作的本质是**分散式脚本拼接**：NPC 同时承担发放、判定、奖励三重职责，进度散落在玩家属性、物品、条件计时器中。
2. 题材包创作层应优先提供**声明式 QuestDef + 目标库 + 触发器 + 奖励表**，覆盖 60%-70% 的常见任务形态。
3. 必须保留**受限脚本钩子**用于动态生成、护送、搜索小游戏、PvP、自适应公式等高自由度玩法，但脚本不能直接修改玩家核心属性。
4. 创作层形态建议采用 **YAML/JSON 为主、状态机为扩展、受限 Python 为逃逸口** 的三层模型，与现有 `engine/src/mud_engine/quest.py` 的方向自然衔接。
5. 运营观测、安全护栏、版本治理应内建在引擎层，而不是让题材包创作者重复 LPC 时代的 `job_server.c` / `center.c` 式手工运维。
