# 任务系统通用机制抽象（基于 LPC 源码）

> 本文件从当前仓库 LPC 源码中抽象任务系统的通用机制，为新引擎任务系统提供一手设计输入。
> 所有结论均标注证据来源（文件路径 + 函数/对象名）。
> 注：`/clone/obj/job/` 目录及其子系统（`job_data.c`、`job_menpai.c`、`job_produce.c`、`job_system.c`）在本仓库中缺失，`/d/wizard/center.c` 中大量引用该目录但无法读到实现；以下分析以仓库中实际存在的文件为准。

---

## 1. 任务状态模型

### 1.1 状态枚举

源码中任务状态并非统一枚举，而是散落在 NPC、condition、玩家属性与任务令牌四类对象上。可归纳出以下通用状态：

| 状态 | 典型存储位置 | 说明 |
|------|-------------|------|
| 可接 | NPC 的 `ask_job` 分支条件 | 玩家满足门派、等级、地点、时间、CD 等前置即可触发 |
| 已接/进行中 | 玩家属性（如 `mingjiao/job`、`qz/caiyao`）、任务令牌（如 `bang ling` 的 `job` mapping）、`apply_condition` | 任务数据绑定到玩家或随身物品 |
| 完成待结算 | `lmjob/ok`、`hz_job/*` 等 temp 标记 | 达成目标后先置位，再与 NPC 对话领取奖励 |
| 已完成 | 玩家属性累计字段（如 `dali/jobdone`、`mingjiao/cc`） | 用于晋升、领薪、排行榜 |
| 失败/超时 | condition 中 `duration < 1` 分支 | 多数仅提示，少数写入失败计数（如 `yipin/failure`） |
| 放弃 | `ask_abandon` 删除任务键并扣贡献 | 明教、黄河帮等提供显式放弃 |

证据：

- 明教：`/d/kunlun/npc/zhuangzheng.c` `ask_job()` 设置 `player->set("mingjiao/job","jin_caikuang")`；`/d/kunlun/npc/mingjiao_job.h` `reward()` 中 `me->delete("mingjiao/job")` 表示完成。
- 华山巡逻：`/d/village/sexit.c` `init()` 在玩家进入时 `set_temp("hz_job/sexit", 1)`，`/kungfu/condition/hz_job.c` 在 duration 到 0 时任务结束。
- 龙门镖局：`/d/hangzhou/npc/du.c` `ask_job()` 中 `me->query_temp("lmjob/ok")` 表示已完成，可领红包；否则 `apply_condition("lmjob", ...)` 进入进行中。
- 一品堂：`/clone/npc/xie2.c` `do_hire()` 将任务存入自身 `job/<time>` 与 `job_time/<time>`，自身作为追杀者，状态由 NPC 维护。

### 1.2 状态转换条件

```text
可接 ──[ask_job 前置通过]──> 进行中
进行中 ──[目标达成 / 时间到 / 交付物品]──> 完成待结算
完成待结算 ──[NPC 对话 / accept_object]──> 已结算 / 累计
进行中 ──[超时 / 玩家死亡 / 条件破坏]──> 失败
进行中 ──[ask_abandon / 删除任务键]──> 放弃
```

关键转换实例：

- 黄河帮帮主 `/d/huanghe/npc/bangzhu.c`（`bangzhu_duty.h`）`ask_job()`：
  - 检查 `bangs/fam`、`bangs/asktime` CD、等级匹配；
  - 随机抽取 `/d/huanghe/bangjob/bangjob<N>.c` 的 `query_job()`；
  - 写入帮令 `ling->set("job", job)`。
- 黄河帮交付：`bangzhu_duty.h` `accept_object()` 检查 `bang ling` 的 `job` 与交付物匹配，成功后 `obj->delete("job")`。

---

## 2. 触发器类型

### 2.1 对话触发（Ask / Inquiry）

最普遍的触发方式。NPC 的 `inquiry` mapping 注册话题，玩家 `ask <npc> about <topic>` 进入 `ask_job()`。

证据：

- `/cmds/std/ask.c` `main()` 调用 `INQUIRY_D->parse_inquiry()`，并回退到 `ob->query("inquiry/" + topic)`。
- `/d/hangzhou/npc/du.c` 注册 `"工作" : (: ask_job :)`、`"job" : (: ask_job :)`。
- `/d/kunlun/npc/zhuangzheng.c` 注册 `"任务"`、`"job"`、`"放弃"`、`"abandon"`。
- 丘处机 `/kungfu/class/quanzhen/qiu.c` `ask_job()` 通过 `"任务"`、`"job"` 触发采药任务。

### 2.2 物品触发

- **交付物品**：NPC `accept_object()` 判定任务物品并结算。

  证据：丘处机 `/kungfu/class/quanzhen/qiu.c` `accept_object()` 识别 `chuanbei`、`fuling` 等药材；黄河帮 `/d/huanghe/npc/bangzhu_duty.h` `accept_object()` 识别 `BIAOHUO`。

- **持有物品作为前置**：

  - 龙门镖局 `/d/hangzhou/npc/du.c` 要求 `present("tuijian xin", me)` 且 `owner` 匹配。
  - 明教 `/d/kunlun/npc/zhuangzheng.c` 要求 `present("tieyan ling", player)`。

- **获得特定物品后开启后续**：

  - 谢烟客 `/clone/npc/xie2.c` `accept_object()` 收到玄铁令后进入“要枣”分支，再进入雇佣杀人分支。

### 2.3 地点触发

- **进入/离开房间**：房间的 `init()` 或 `valid_leave()` 检查任务标记。

  证据：华山巡逻 `/d/village/sexit.c` `init()` 设置 `hz_job/sexit`；`valid_leave()` 阻止 `hz_job` 状态下向南离开。

  灵隐寺讲经 `/kungfu/condition/lyjob.c` 每回合检查 `base_name(room) != "/d/hangzhou/lingyin3"`。

  龙门镖局 `/d/hangzhou/npc/du.c` 要求 `base_name(environment()) == "/d/hangzhou/biaoju"`。

- **区域名匹配**：黄河帮任务中 `region = explode(file, "/")[1]`，用 `/d/REGIONS.h` 的 `region_names` 做区域描述。

### 2.4 时间触发

- **自然时间 / 时辰**：

  枯木禅师 `/d/hangzhou/npc/kumu.c` `ask_job()` 调用 `NATURE_D->outdoor_room_event()` 检查 `event_dawn`。

  多隆 `/d/beijing/npc/duolong.c` `ask_job()` 用 `HELPER->is_sunrise()` / `is_sunset()` 决定守门班次。

- **相对 CD（cooldown）**：

  黄河帮 `/d/huanghe/npc/bangzhu_duty.h` `ask_job()`：`time() < me->query("bangs/asktime") + 180`。

  方怡 `/d/shenlong/npc/fang.c` `do_work()`：`time() < me->query("marks/方c") + 180`。

- **绝对预约时间**：

  谢烟客 `/clone/npc/xie2.c` `do_hire()`：`set("job_time/" + time(), time() + when * 3600)`，NPC 在 `auto_check()` 中比较 `time()` 与预约时间。

  丘处机 `/kungfu/class/quanzhen/qiu.c` `do_name()`：`set("job_time/" + time(), time())` 立即追杀。

### 2.5 NPC 状态触发

- **NPC 存活/在场**：

  黄河帮“截镖”任务检查 `children(BIAOTOU)` 数量，`sizeof(obj) < 10` 则动态生成镖头。

  都大锦 `/d/hangzhou/npc/du.c` `come_killer()` 在 `chat_msg` 中检测蒙面人并触发战斗。

- **NPC 血量/忙碌**：

  谢烟客、丘处机等追杀 NPC 在 `ask_job` / `auto_check` 中检查 `is_fighting()`、`is_busy()`。

### 2.6 玩家属性触发

常见前置：门派、辈分、性别、阶级、经验、技能、声望、忠诚度、死亡次数、MUD 年龄。

证据：

- 门派：几乎所有 `ask_job()` 都检查 `family/family_name`。
- 辈分：龙门镖局 `/d/hangzhou/npc/du.c` `myfam["generation"] > 37` 拒绝。
- 性别/阶级：枯木禅师 `/d/hangzhou/npc/kumu.c` 要求男性、bonze；多隆 `/d/beijing/npc/duolong.c` 要求男性（`set_shiwei_status` 固定）。
- 经验：黄河帮 `/d/huanghe/npc/bangzhu_duty.h` 按 `combat_exp` 分档选任务；李四 `/clone/npc/xiejian.c` 拒绝目标经验 > 600k。
- 技能：丘处机 `/kungfu/class/quanzhen/qiu.c` 检查剑法、身法、招架、内力；枯木禅师要求 `buddhism >= 120`。
- 死亡次数：米正 `/clone/npc/mizheng.c` `should_demote()` 按官职等级限制死亡次数。
- 忠诚度：明教 `mingjiao/cc`；黄河帮帮令 `score`。

---

## 3. 目标判定机制

### 3.1 收集（寻 / 采集 / 送礼）

- **寻物**：任务 mapping 中 `"type" : "寻"` / `"sgjob_type" : "寻"`，以物品名为目标，交付时 `accept_object()` 按 `name` 或 `id` 匹配。

  证据：神龙教 `/d/shenlong/sgjob/sgjob50000.c`、`sgjob1000000.c` 中大量 `"寻"` 条目，目标包括普通物品与 unique 物品（如“神木王鼎”、“倚天剑”）。

  黄河帮 `/d/huanghe/bangjob/bangjob*.c` 中 `"type" : "寻"` 较少，主要由 `"杀"` 构成。

- **采集**：明教五行旗任务以动作/资源为目标。

  证据：`/d/kunlun/npc/mingjiao_job.h` 定义 `jin_caikuang`（采集铁矿）、`huo_zaoqiang`（打造火枪）、`shui_tiaoshui`（挑水）、`mu_kanshu`（砍树）、`tu_didao`（挖地道），玩家需使用工具（如 `/d/kunlun/obj/qiao` 铁锹）在指定地点完成。

- **送礼**：黄河帮 `"送礼"` 类型从 `info_guest` 随机取目标 NPC，玩家携带 `CAILI` 彩礼交给对方。

  证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()` case `"送礼"`。

### 3.2 护送（护驾 / 押镖）

- **护驾**：黄河帮 `"护驾"` 生成 `BANGZHU2` NPC 并 `set_leader(me)`，帮主随玩家移动到目标区域。

  证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()` case `"护驾"`。

- **押镖/截镖**：

  黄河帮 `"截镖"` 任务要求玩家击杀 `BIAOTOU` 并取得 `BIAOHUO`。

  证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()` case `"截镖"`；`accept_object()` 检查 `base_name(ob) != BIAOHUO` 与 `ob->query("my_killer") != who->query("id")`。

### 3.3 击杀

- **指定 NPC 击杀**：任务 mapping 含 `name`、`file`、`area`、`type:"杀"`。

  证据：黄河帮 `/d/huanghe/bangjob/bangjob5000.c`、`bangjob100000.c` 中大量 `"杀"` 条目；帮主交付时按 `chname != job["name"]` 校验。

- **随机玩家追杀**：

  谢烟客 `/clone/npc/xie2.c`、李四 `/clone/npc/xiejian.c`、丘处机 `/kungfu/class/quanzhen/qiu.c` 接受玩家雇佣，按目标 ID 追杀在线玩家。

  判定完成：检查 `present("corpse", environment())` 且 `victim_name == target_name`。

- **示威**：黄河帮 `"示威"` 随机选一个非本帮 `bangzhong` 击杀。

  证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()` case `"示威"`，使用 `is_victim()` 过滤同 title。

### 3.4 守门 / 驻守

御林军任务按官职等级分配内外城门，玩家需到指定地点执行 `guard` 命令。

证据：`/d/beijing/npc/duolong.c` `ask_job()` 使用 `outer_gate_name`、`inner_gate_name`，并检查日出日落。

### 3.5 搜索 / 巡逻

华山巡逻任务要求玩家依次经过村庄多个标记点（`sexit`、`temple`、`alley`、`majiu` 等），由 condition 倒计时。

证据：`/d/village/sexit.c`、`temple1.c`、`alley2.c`、`/d/city/majiu.c` 的 `init()` 均设置 `hz_job/*` temp 标记；`/kungfu/condition/hz_job.c` 在 `duration < 1` 时结束。

### 3.6 制造 / 加工

明教打造火枪、挖地道等任务属于“在指定地点使用工具完成加工动作”。

证据：`/d/kunlun/npc/mingjiao_job.h` `judge_jobmsg()` 列出五种工种；`reward()` 按工种给不同忠诚度/经验/潜能。

### 3.7 强制加入 / PK

神龙教任务池中大量 `FORCEJOIN` 与 `PK` 类型，高等级任务几乎全是这两者。

证据：`/d/shenlong/sgjob/sgjob50000.c`、`sgjob1000000.c` 中 `FORCEJOIN` 与 `PK` 占位条目。

---

## 4. 奖励结算机制

### 4.1 奖励类型

| 类型 | 典型字段 | 说明 |
|------|---------|------|
| 经验 | `combat_exp` | 最普遍奖励 |
| 潜能 | `potential` / `max_potential` | 多数任务有上限保护 |
| 金钱 | `balance`、`silver`、`gold` | 崔百泉按 `dali/jobdone` 发银行余额 |
| 物品 | 任务道具、unique、令牌 | 如铁焰令、红衣袈裟、侍卫腰牌 |
| 门派贡献 | `mingjiao/cc`、`bangs/score` | 用于学技能或晋升 |
| 技能点 | `improve_skill` | 丘处机按 `bangs/skills_asked` 教学 |
| 官职/称号 | `title`、`family/generation` | 御林军晋升 |
| 声望 | `shen`、`mingjiao/credit` | 可正可负 |

### 4.2 经验/潜能公式

- **job_server 统一结算**：

  证据：`/clone/obj/job_server.c` `reward_func()`：

  ```lpc
  exp_reward = exp_limit*exp_rate*(time_now-start_time)/360000;
  pot_reward = pot_limit*pot_rate*(time_now-start_time)/360000;
  player->add("combat_exp", exp_reward);
  player->add("potential", pot_reward);
  if (player->query("potential") > player->query("max_potential"))
      player->set("potential", player->query("max_potential"));
  ```

  经验上限由巫师通过 `set_exp_limit` 配置；`exp_rate`/`pot_rate` 由任务实现传入（0-100，但接口不强制）。

  结算后 `player->delete("job_server/"+job+"_start")`。

- **按任务独立计算**：

  - 黄河帮击杀：`bonus = job["bonus"] * job["max"] / (combat_exp + 1000)`；`record = bonus / 2 + random(bonus)`。
  - 黄河帮截镖：`bonus = exp * 120 / (exp + combat_exp)`；体现“目标越强奖励越高但递减”。
  - 明教：`/d/kunlun/npc/mingjiao_job.h` `reward()` 中 `add_exp = BASE + random(add_cc)`，`add_pot = 40 + random(add_exp/4)`。
  - 大理：`/d/dali/npc/cui.c` `ask_me()` 中 `wage = (jobdone - lastcheck) * 500` 或 `* combat_exp / 70`，存入 `balance`。
  - 龙门镖局：`/d/hangzhou/npc/du.c` `bonus = combat_exp / 10000 + random(bonus)`，以 `silver` 发放。

### 4.3 一次性 vs 累计

- **一次性即时奖励**：多数击杀/寻物/采集任务在交付时一次性加经验、潜能、贡献。
- **累计计数再兑换**：

  - 大理 `dali/jobdone` 累计完成次数，崔百泉按“上次领薪至今的完成次数”结算。
  - 黄河帮帮令 `score` 累计，用于向帮主学习技能。
  - 御林军 `bingbu/job_cur`、`job_total`、`job_rank*` 累计，用于晋升。

### 4.4 限额与衰减

- **潜能上限**：`max_potential` 封顶。
- **job_server 全局经验/潜能上限**：由巫师设置 `exp_limit`、`pot_limit`。
- **每周保护期**：李四 `/clone/npc/xiejian.c` 对同一目标设置 `last_lisi_mission` 一周 CD，防止被反复追杀。
- **等级分档**：黄河帮、神龙教任务池按 `combat_exp` 分档（如 3000、5000、10000…500000），避免低级玩家接高级任务。

---

## 5. 失败 / 重置 / 放弃机制

### 5.1 超时失败

- **仅提示，不扣奖**：

  一品堂 `/kungfu/condition/ypjob.c`：`duration == 1` 时 `me->add("yipin/failure", 1)` 并提示“青铁令时限已到！”。

  灵隐寺讲经 `/kungfu/condition/lyjob.c`：`duration < 1` 时 `me->add_temp("lypoint", 1)` 并提示休息，未直接惩罚。

- **任务自然结束**：

  华山巡逻 `/kungfu/condition/hz_job.c`、黄河帮状态 `/kungfu/condition/hz_job.c` 仅递减 duration，到 0 返回 0。

- **丢失关键物品导致失败**：

  丐帮密函 `/kungfu/condition/gb_job.c`：携带密函时随机掉落并销毁，触发 `let_know()` 提示。

### 5.2 玩家死亡 / 逃跑

追杀型 NPC（谢烟客、李四、丘处机）在目标死亡、下线或逃入安全区后返回老巢，`delete_temp("target")`。

黄河帮帮主 `accept_kill()` 会召唤跟随者反击。

### 5.3 显式放弃

明教：`/d/kunlun/npc/mingjiao_job.h` `ask_abandon()` 与 `cut_abandon_jl()`：

- 按工种扣减 `mingjiao/cc`（忠诚度）；
- 若忠诚度不足则无法放弃；
- 成功后 `player->delete("mingjiao/job")`。

黄河帮：未看到显式放弃命令，但任务存在 `bangs/asktime` CD，可理解为“不完成就不能再接”。

### 5.4 重置

- **任务位置重置**：

  丘处机 `/kungfu/class/quanzhen/qiu.c` 用 `job_pos` temp 计数，每日/每次有上限（`me->query_temp("job_pos") == 0` 时可能无任务）。

- **全局系统开关**：

  `/d/wizard/center.c` `do_start_system()` / `do_close_system()` 调用 `job_data->set_job_start()` / `set_close_start()`，控制主动性任务系统开关。

- **巫师手动清除**：

  `/d/wizard/center.c` `do_cut_job()` 可删除指定玩家或全部 `job_data`。
  `/clone/obj/job_server.c` `do_job_clear()` 删除某 job 的统计与直方图。

---

## 6. 并发与限额

### 6.1 同类型任务互斥

- 明教：`player->query("mingjiao/job")` 存在时无法再接新任务。
- 丘处机：`job_stat || qz/bdgranted` 存在时拒绝新任务。
- 黄河帮：通过帮令 `ling->query("job")` 存在判断，再次 ask 会覆盖旧任务（`ling->delete("job"); ling->set("job", job)`）。
- 龙门镖局：`me->query_condition("lmjob")` 存在时不可再接。

### 6.2 同时可接任务数

源码中未显式限制“不同类型任务同时存在”的数量，但实际互斥隐含：

- 一个 condition 槽位只能挂一个同名 condition；
- 多个 temp 标记可同时存在（如 `hz_job/sexit`、`hz_job/temple`）。

### 6.3 每日/每周限额

- **时间 CD**：

  黄河帮 `bangs/asktime + 180` 秒。

  方怡 `marks/方c + 180` 秒。

- **每周保护**：李四 `/clone/npc/xiejian.c` 对目标 `last_lisi_mission` 一周 CD。

- **位置/次数限额**：

  丘处机 `/kungfu/class/quanzhen/qiu.c` `job_pos` 计数，`me->add_temp("job_pos", -1)`，为 0 时可能无任务。

  米正 `/clone/npc/mizheng.c` 每 rank 有固定职位数 `rank_position_num(rank)`，满员则不可加入。

### 6.4 总经验上限

- **job_server 上限**：`/clone/obj/job_server.c` 通过 `exp_limit` / `pot_limit` 限制每个 job 每小时总产出。
- **现代视角提示**：源码未按玩家维度做每日经验上限，而是按 job 维度做产出速率上限，容易导致“刷子”行为。

### 6.5 等级匹配

- 黄河帮 `/d/huanghe/npc/bangzhu_duty.h` 将玩家经验 `(4*exp + random(2*exp))/5` 与 `levels` 数组比对，选对应任务池。
- 多隆 `/d/beijing/npc/duolong.c` 按 `SHIWEI_LEVEL(player)` 分配任务。

---

## 7. 数据持久化

### 7.1 玩家数据（player save）

任务状态、累计计数、CD、贡献度等主要保存在玩家对象属性中，由玩家存档机制持久化。

证据字段：

- `job_server/<job>_start`：`/clone/obj/job_server.c` `start_job()`。
- `mingjiao/job`、`mingjiao/cc`、`mingjiao/credit`：明教相关。
- `bangs/fam`、`bangs/asktime`、`bangs/jointime`：黄河帮。
- `dali/jobdone`、`lastcheck`：大理。
- `bingbu/job_cur`、`job_total`、`job_rank*`：御林军。
- `last_lisi_mission`：李四追杀保护 CD。

### 7.2 NPC 数据（NPC save）

追杀型 NPC 自身持久化任务队列：

- 谢烟客 `/clone/npc/xie2.c` `query_save_file()` 返回 `/data/npc/xie`；`do_hire()` 中 `set("job/" + time(), who)` 后 `save()`。
- 李四 `/clone/npc/xiejian.c` `query_save_file()` 返回 `/data/npc/xiejian`；同样 `save()` 任务。
- 丘处机 `/kungfu/class/quanzhen/qiu.c` `query_save_file()` 返回 `/data/npc/qiu`。
- 米正 `/clone/npc/mizheng.c` 持久化侍卫名册 `members/rank*` 与通文 `bingbu/news`。

### 7.3 全局守护进程 / 数据对象

- **job_server.o**：`/clone/obj/job_server.c` 继承 `F_SAVE`，存档路径 `/data/npc/job_server`。保存：

  - `exp_limit/<job>`、`pot_limit/<job>`；
  - `stat/<job>` 每个玩家的任务次数、耗时、奖励；
  - `exp_hist/<job>`、`pot_hist/<job>` 奖励分布直方图；
  - `job_data/<job>_<data>` 通用数据。

- **缺失的中心数据对象**：`/d/wizard/center.c` 引用 `/clone/obj/job/job_data`、`job_menpai`、`job_produce`、`job_system`，但本仓库中这些文件缺失，无法分析其持久化结构。

### 7.4 任务令牌对象

- 黄河帮“帮令” `/d/huanghe/obj/bangling` 是随身携带的持久化任务载体，`ling->set("job", job)`。
- 明教“铁焰令” `/d/kunlun/obj/tieyanling` 作为身份与记录信物。
- 御林军“侍卫腰牌” `/d/beijing/obj/yaopai`。

### 7.5 日志文件

- `/clone/obj/job_server.c` `reward_func()` 写入 `log_file("job_server-"+job, ...)`。
- `/d/huanghe/npc/bangzhu_duty.h` 写入 `log_file("test/BangJob", ...)`。
- `/d/wizard/center.c` 写入 `log_file("test/job_system_set", ...)`。
- 谢烟客、丘处机、李四写入 `log_file("Playing", ...)` / `log_file("Qiu_Anti_Pker", ...)`。

---

## 8. 典型任务类型速查

| 任务 | 核心文件 | 触发 | 目标 | 奖励 |
|------|---------|------|------|------|
| 明教五行旗日常 | `/d/kunlun/npc/zhuangzheng.c` 等 + `mingjiao_job.h` | ask | 采集/打造/挑水/砍树/挖地道 | 经验、潜能、忠诚度 |
| 黄河帮帮务 | `/d/huanghe/npc/bangzhu.c` + `bangzhu_duty.h` + `bangjob/*.c` | ask | 寻、杀、截镖、示威、送礼、护驾 | 经验、帮令 score、负神 |
| 龙门镖局 | `/d/hangzhou/npc/du.c` + `lmjob` condition | ask | 在镖局传授武功（驻守类） | 银两 |
| 灵隐寺讲经 | `/d/hangzhou/npc/kumu.c` + `lyjob` condition | ask + 时辰 | 在 lingyin3 诵经倒计时 | 潜能、buddhism 熟练、袈裟 |
| 华山巡逻 | 多房间 `init()` + `hz_job` condition | ask（由其他 NPC 触发，本仓库未读到派发 NPC） | 经过村庄多个标记点 | （本仓库未读到奖励 NPC） |
| 全真采药 | `/kungfu/class/quanzhen/qiu.c` | ask | 采集药材并交付 | （本仓库未读到经验奖励代码，仅删除状态） |
| 御林军守门 | `/d/beijing/npc/duolong.c` + `mizheng.c` | ask + 时辰 | 到指定城门 guard | 军功、晋升 |
| 大理打杂 | `/d/dali/npc/cui.c` | ask | 累计 `dali/jobdone` | 按次数发银行余额 |
| 雇佣追杀 | 谢烟客 `/clone/npc/xie2.c`、李四 `/clone/npc/xiejian.c`、丘处机 `/kungfu/class/quanzhen/qiu.c` | 物品/对话 + 命令 | 追杀指定玩家 | 复仇、社交惩罚 |
| 神龙教 | `/d/shenlong/sgjob/*.c` + `fang.c` | ask | 寻物、抓蛇、PK、FORCEJOIN | 经验、潜能、score |

---

## 9. 对现代设计的提示（非结论，供后续讨论）

1. **状态分散**：任务状态同时存在于玩家对象、condition、令牌、NPC 对象，缺乏统一任务 ID 与生命周期管理。
2. **奖励公式黑箱**：各任务独立计算，没有统一“难度-奖励”评估器，容易出现数值失衡。
3. **时间/地点触发硬编码**：大量房间 `init()` 与 NPC `ask_job()` 直接写死路径名，不利于 UGC 扩展。
4. **社交压力设计**：雇佣追杀、PK 任务、FORCEJOIN 等机制在现代多人游戏中可能带来强烈的负向社交体验，需要谨慎评估。
5. **限额维度单一**：主要用“时间 CD”和“job 总产出上限”控制，缺少玩家日/周累计上限、疲劳值等现代常见设计。
