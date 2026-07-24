# 系统 / NPC 自动触发视角 User Stories

> 本文件采用“作为系统，我……”格式，覆盖任务系统中不由玩家直接指令触发、而由系统定时器、NPC 自主行为或环境状态变化驱动的路径。
> 每条故事均标注证据来源（文件路径 + 函数/对象名）。

---

## 1. 定时刷新与 NPC 自主派生任务

### 1.1 黄河帮帮主根据世界状态动态生成截镖目标

**作为系统，我**每隔一段时间检查当前世界中 `BIAOTOU` 克隆体的数量；如果数量不足 10 个，我就在 `biao_places` 中随机选一个地点生成一名镖头，并把它当前所在房间和所属镖局名告知接任务的玩家。

证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()` case `"截镖"`：

```lpc
obj = filter_array(children(BIAOTOU), (: clonep :));
if( sizeof(obj) < 10 ) {
    ob = new(BIAOTOU);
    file = biao_places[random(sizeof(biao_places))];
    if( !(dest = find_object(file)) ) dest = load_object(file);
    ob->move(dest);
    ...
}
```

### 1.2 黄河帮帮主动态选择示威目标

**作为系统，我**在玩家申请“示威”任务时，扫描所有 `bangzhong` 克隆体，过滤掉与本帮同 title 的帮众，随机选一个敌对帮众作为击杀目标。

证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()` case `"示威"` 与 `private is_victim()`。

### 1.3 都大锦在镖局定时刷新刺客

**作为系统，我**以 3% 的概率在聊天轮询中检查：如果都大锦身处 `/d/hangzhou/biaoju` 且没有在战斗/忙碌，且房间中没有蒙面人，则生成一名蒙面刺客并命令其攻击都大锦。

证据：`/d/hangzhou/npc/du.c` `come_killer()`、`set("chat_chance", 3)` 与 `set("chat_msg", ({ (: come_killer :) }))`。

### 1.4 米正定时刷新御林军名册与降职检查

**作为系统，我**每 20 分钟（1200 秒）遍历一次御林军 7 个等级的职位名册，对每一名在线或离线的侍卫检查：是否已退出门派、是否死亡次数超限、是否长期不点名/不值班；必要时将其降职或除名，并发布兵部通文。

证据：`/clone/npc/mizheng.c` `create()` 中 `call_out("refresh_members", 1200)`；`refresh_members()` 与 `should_demote()`。

---

## 2. 超时清算

### 2.1 一品堂青铁令超时计数

**作为系统，我**每回合递减玩家身上的 `ypjob` condition；当倒计时归零时，给玩家增加一次 `yipin/failure` 失败计数，并告知“青铁令时限已到！”。

证据：`/kungfu/condition/ypjob.c` `update_condition()`：

```lpc
if (duration == 1){
    me->add("yipin/failure", 1);
    tell_object(me, "青铁令时限已到！\n");
    me->apply_condition("ypjob", 0);
    return 1;
}
```

### 2.2 灵隐寺讲经自然结束

**作为系统，我**每回合检查玩家是否仍在 `/d/hangzhou/lingyin3`、精力是否足够；当诵经倒计时结束时，增加一次讲经次数 `lypoint`，让小僧过来提醒玩家休息。

证据：`/kungfu/condition/lyjob.c` `update_condition()`。

### 2.3 华山巡逻 / 黄河帮状态倒计时结束

**作为系统，我**每回合递减 `hz_job` condition；倒计时归零时任务自然结束，不再继续巡逻/示威状态。

证据：`/kungfu/condition/hz_job.c` `update_condition()`。

### 2.4 龙门镖局任务完成提示

**作为系统，我**在 `lmjob` condition 倒计时归零时，给玩家设置 `lmjob/ok` 标记，并派镖头告知玩家可以休息，随后玩家可向都大锦领取红包。

证据：`/kungfu/condition/lmjob.c`（同 `/d/hangzhou/npc/lmjob.c`）`update_condition()`。

### 2.5 丐帮密函随机丢失

**作为系统，我**在玩家持有密函期间，每回合以小概率（`random(kar) < 3 && random(40) < 5`）让密函从玩家身上掉落或被盗，并延迟 3 秒通知玩家。

证据：`/kungfu/condition/gb_job.c` `update_condition()` 与 `let_know()`。

---

## 3. 限额检查

### 3.1 job_server 全局产出限额

**作为系统，我**在每个任务被 `reward()` 结算时，根据该任务预先配置的 `exp_limit` 与 `pot_limit`，以及本次传入的 `exp_rate`/`pot_rate` 和耗时，计算实际奖励；确保单任务每小时总产出不超过巫师设定的上限，并把结果写入玩家属性、统计表与直方图。

证据：`/clone/obj/job_server.c` `reward_func()`。

### 3.2 任务申请冷却检查

**作为系统，我**在玩家向黄河帮主申请任务时，检查 `bangs/asktime`：如果距离上次申请不足 180 秒且帮令上已有任务，则拒绝并提示“不是刚问过我吗？”。

证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()`。

### 3.3 方怡抓蛇任务冷却

**作为系统，我**在玩家向方怡打听任务时，检查 `marks/方c`：如果距离上次领取不足 180 秒，则怒斥玩家并拒绝。

证据：`/d/shenlong/npc/fang.c` `do_work()`。

### 3.4 李四追杀目标保护期

**作为系统，我**在接受玩家雇佣追杀目标时，检查目标身上的 `last_lisi_mission`：如果一周内已被追杀过，则拒绝此次委托，给目标一个“喘息机会”。

证据：`/clone/npc/xiejian.c` `do_hire()`。

### 3.5 御林军职位空缺检查

**作为系统，我**在玩家投军或晋升时，检查对应 `rank` 的 `members/rank*` 数组是否有空位；若无空位，则告知“兵部人满为患，没有实缺”。

证据：`/clone/npc/mizheng.c` `add_user_succ()`。

### 3.6 明教放弃任务时的忠诚度扣减

**作为系统，我**在玩家请求放弃明教任务时，根据工种随机扣除一定忠诚度；如果忠诚度不足，则不允许放弃，强制玩家继续完成。

证据：`/d/kunlun/npc/mingjiao_job.h` `cut_abandon_jl()`。

---

## 4. 状态重置

### 4.1 任务完成后删除玩家任务键

**作为系统，我**在明教任务交付后，删除玩家 `mingjiao/job` 字段，使其可以再次领取新任务。

证据：`/d/kunlun/npc/mingjiao_job.h` `reward()`。

### 4.2 黄河帮交付后清空帮令任务

**作为系统，我**在玩家向帮主交付任务物品后，删除帮令上的 `job` mapping，并发放经验、负神与帮令 score。

证据：`/d/huanghe/npc/bangzhu_duty.h` `accept_object()`。

### 4.3 任务 NPC 失败后返回老巢并满状态重置

**作为系统，我**在雇佣追杀 NPC（谢烟客、李四、丘处机）血量过低、目标逃跑或下线时，让 NPC 瞬间回到自己的 office 房间，回满气血/精力/内力，清除临时状态，并进入一段忙碌/休息期。

证据：

- `/clone/npc/xie2.c` `waiting()`、`do_back()`、`full_all()`。
- `/clone/npc/xiejian.c` `waiting()`、`do_back()`。
- `/kungfu/class/quanzhen/qiu.c` `waiting()`、`do_back()`、`full_all()`。

### 4.4 雪山派铜缸法事场景重置

**作为系统，我**在雪山派渡母殿被捣乱者点燃铜缸或被杀死后，调用 `reset_to_normal()` 恢复场景默认状态。

证据：`/d/xueshan/npc/robber.c` `clear_dumudian()` 与 `die()`。

---

## 5. NPC 自主追杀与任务执行

### 5.1 谢烟客按预约时间自主追杀

**作为系统，我**以 3% 概率在谢烟客的聊天轮询中检查当前是否有到期的追杀委托；如果有，目标在线且不在安全区/限制区/船上，且血量/内力不过于饱满，则锁定目标、瞬移到目标身边并发起攻击。

证据：`/clone/npc/xie2.c` `auto_check()`、`do_chase()`、`do_kill()`。

### 5.2 李四自主追杀

**作为系统，我**以 5% 概率在李四的聊天轮询中检查追杀列表；当委托到期且目标满足条件（非安全区、非限制区域、非高血高内高手）时，变身“邪剑”称号、增加临时属性、瞬移追杀。

证据：`/clone/npc/xiejian.c` `auto_check()`。

### 5.3 丘处机自主追杀恶人

**作为系统，我**以 3% 概率在丘处机的聊天轮询中检查复仇委托；委托到期后，排除武林盟主/赏善使者/法恶使者的保护对象，瞬移追杀目标，直到目标死亡或逃跑。

证据：`/kungfu/class/quanzhen/qiu.c` `auto_check()`。

### 5.4 雪山派捣乱者自主执行任务链

**作为系统，我**在被召唤到渡母殿后，先等待 15-25 秒，然后检查玩家是否仍在场：

- 若玩家在场，则攻击玩家；
- 若玩家不在场但值班喇嘛在场，则攻击喇嘛；
- 若都不在场且铜缸还有酥油，则点燃铜缸并逃离；
- 20 分钟后无论结果如何自毁。

证据：`/d/xueshan/npc/robber.c` `start_checking()`、`start_job()`、`self_destruct()`。

---

## 6. 全局系统开关与巫师干预

### 6.1 武林幻境开启/关闭主动性任务系统

**作为系统，我**在巫师于 `/d/wizard/center.c` 输入 `start_system` 或 `close_system` 时，调用 `job_data` 的开关方法，并在系统频道发布天地异象公告。

证据：`/d/wizard/center.c` `do_start_system()`、`do_close_system()`。

### 6.2 巫师强制发布/停止任务

**作为系统，我**在巫师输入 `job_start [玩家名]` 时，调用 `job_produce->produce_job()` 为指定玩家或全服生成一次任务。

证据：`/d/wizard/center.c` `do_start()`。

### 6.3 巫师查询任务执行状态

**作为系统，我**在巫师输入 `check_do_job` 时，从 `job_data` 中读取 `ask_job`、`oppose_pker`、`finish_job` 三个在线玩家列表并展示。

证据：`/d/wizard/center.c` `do_check_do_job()`。

### 6.4 巫师手动清除玩家任务数据

**作为系统，我**在巫师输入 `job_cut all` 时重置整个 `job_data`；输入 `job_cut 玩家名` 时，删除该玩家的任务 mapping 并保存。

证据：`/d/wizard/center.c` `do_cut_job()`。

### 6.5 job_server 统计与直方图维护

**作为系统，我**在每次任务奖励结算后，更新该任务按玩家 ID 的累计统计（次数、耗时、经验、潜能、rate），以及 10 分位的经验/潜能直方图，供巫师通过 `job_stat`、`job_hist` 查询。

证据：`/clone/obj/job_server.c` `reward_func()`。

---

## 7. 地点 / 环境自动标记

### 7.1 巡逻点自动打卡

**作为系统，我**在玩家进入华山巡逻任务涉及的房间（如南村口、玄坛庙、小巷尽头、马厩）时，如果玩家身上有 `huashan/job_pending`，就自动在 temp 中设置对应的 `hz_job/*` 标记。

证据：`/d/village/sexit.c`、`/d/village/temple1.c`、`/d/village/alley2.c`、`/d/city/majiu.c` 的 `init()`。

### 7.2 华山巡逻区域限制离开

**作为系统，我**在玩家身负 `hz_job` condition 且试图从南村口向南离开时，阻止其离开并提示“身负巡山任务，不能轻离职守”。

证据：`/d/village/sexit.c` `valid_leave()`。

---

## 8. 社交 / PvP 任务自动触发

### 8.1 雇佣追杀到期自动执行

**作为系统，我**在玩家通过谢烟客、李四雇佣追杀后，把目标 ID 与执行时间写入 NPC 自身的 save 文件；到期后由 NPC 自主决定是否满足出手条件并执行追杀。

证据：`/clone/npc/xie2.c` `do_hire()`、`auto_check()`；`/clone/npc/xiejian.c` `do_hire()`、`auto_check()`。

### 8.2 丘处机复仇委托自动执行

**作为系统，我**在玩家向丘处机提交复仇对象后，校验玩家经验、PK 记录、目标是否最近杀过自己；通过后将目标写入丘处机的 `job/job_time` save 数据，并由 NPC 自主追杀。

证据：`/kungfu/class/quanzhen/qiu.c` `do_name()`、`auto_check()`。

---

## 9. 任务令牌与身份信物管理

### 9.1 黄河帮令自动发放与覆盖

**作为系统，我**在玩家加入黄河帮或申请任务时，检查其是否持有帮令；如果没有或帮令不匹配，则生成新的帮令并绑定 owner、帮派、经验，作为任务状态载体。

证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_join()` 与 `ask_job()`。

### 9.2 明教铁焰令补发与惩罚

**作为系统，我**在玩家向冷谦询问铁焰令且未持有时，扣除其部分 `mingjiao/credit` 声望，并补发一块新的铁焰令。

证据：`/d/kunlun/npc/mingjiao_npc.c` `ask_tyling()`。

### 9.3 御林军腰牌补发

**作为系统，我**在御林军玩家向多隆申请腰牌且身上没有时，生成新的侍卫腰牌。

证据：`/d/beijing/npc/duolong.c` `ask_yaopai()`。

---

## 10. 现代设计启示（供后续讨论）

1. **NPC 自主行为丰富**：LPC 中 NPC 不仅是任务发放者，还是任务执行者（追杀、护驾、捣乱），新引擎需要考虑 NPC 任务执行器与玩家任务状态的解耦。
2. **定时器密集**：大量 `call_out`、`chat_chance`、`condition` 构成任务节奏，需要统一的心跳/调度机制。
3. **安全区/限制区规则重复**：追杀 NPC 多处重复排除 `no_fight`、特定区域、船上等，应抽象为统一的“任务可执行区域”规则。
4. **离线玩家数据读取**：雇佣追杀时会克隆离线玩家对象 `new(USER_OB)` 读取属性，现代设计中需考虑隐私与数据一致性。
