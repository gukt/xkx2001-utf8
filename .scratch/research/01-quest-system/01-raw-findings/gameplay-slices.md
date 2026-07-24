# 玩法切片：LPC 任务系统玩家视角 + 数据流

> 本文件基于当前仓库一手 LPC 源码整理，每个结论均标注证据来源。仅作设计输入，不做行为等价验证。

---

## 切片 1：师门任务——少林玄慈「龙门镖局授武推荐信」

### 任务类型名称
师门派遣型任务（门派高层 → 指定外派 NPC）

### 触发方式
- 玩家与少林派方丈 **玄慈大师** 对话，输入 `ask xuanci about 工作` 或 `ask xuanci about job`。
- 玄慈的 `inquiry` 将 "工作"/"挑水"/"job" 映射到 `ask_job()` / `ask_tiaoshui()`（`ask_job` 为推荐信任务）。

### 完整玩家流程
1. **接任务**：玄慈校验玩家门派、辈分、CD（`fz_ask` 5 分钟冷却），生成 `/d/shaolin/obj/letter-job` 并 `move(me)`。
2. **执行**：玩家携带推荐信前往龙门镖局，将信交给对应 NPC（本切片未在源码中展示收信人完整逻辑，但信件 `long` 写明「玄慈方丈写给龙门镖局都总镖头」）。
3. **完成/失败**：源码中 letter-job.c 仅定义物品属性，未展示后续奖励脚本；任务状态主要由 `present("tuijian xin", me)` 和 `fz_ask` 控制。

### 关键 NPC、物品、房间、命令
- NPC：玄慈大师 `/d/shaolin/npc/xuanci.c`。
- 物品：推荐信 `/d/shaolin/obj/letter-job.c`（id: `tuijian xin` / `xin` / `letter`，`no_drop`）。
- 命令：`ask xuanci about 工作`。

### 奖励类型与结算时机
- 源码未展示完整结算；从 `ask_job()` 看，任务以「交付推荐信」为终点，奖励由目标 NPC 决定（本次未读取到目标 NPC 处理逻辑）。

### 异常路径
- **门派不符**：非少林派玩家被拒绝。
- **辈分不足**：`generation > 37` 时玄慈让玩家「再练几年」。
- **CD 中**：5 分钟内重复询问被拒绝。
- **已持有推荐信**：`present("tuijian xin", me)` 为真时无法再接。

### 证据来源
- `/d/shaolin/npc/xuanci.c`：`ask_job()` 函数（行 135-160）；`inquiry` 映射（行 80-84）。
- `/d/shaolin/obj/letter-job.c`：物品定义（行 1-18）。

---

## 切片 2：走镖任务——福威镖局「护镖/劫镖/搭档护镖」

### 任务类型名称
护送型任务 + PvP 劫镖对抗 + 组队护送

### 触发方式
- 玩家与福威镖局总镖头 **林震南** 对话，输入 `ask lin about 保镖/走镖/工作/job/jiebiao/劫镖/abandon/放弃`。
- 组队护镖使用专用命令 `jobwith <队友id>`。

### 完整玩家流程

#### 2.1 普通单人走镖（`ask_biao`）
1. **接任务**：林震南随机分配 5 个目的地之一（白鹿书院朱熹、北疆小镇巴依、泉州马五德、玉泉院李铁嘴、泰山江百胜），给玩家一份镖货 `biaohuo`。
2. **执行**：玩家限时将镖货送到目标 NPC，途中可能遭遇土匪/山贼等。
3. **完成**：目标 NPC `accept_object` 收到镖货后调用 `award()`，奖励经验、潜能、金钱，并清空 `biao/*` 状态。
4. **失败**：镖货对象 `biaohuo1` 在 100-120 秒后 `destroy_it`，删除玩家 `biao/*` 状态并置 `biao/fail`。

#### 2.2 高级护镖（`ask_job`）
1. **接任务**：玩家经验需 ≥10k，单人接取时随机 1/12 概率被转为「劫镖」任务（`assign_rob`）。
2. 正常接取后，林震南生成一辆镖车 `biaoche` 置于扬州福威镖局门外，并召唤一名镖头/趟子手 `assign_biaotou` 跟随玩家。
3. 玩家需在 `condition("biaoju")` 倒计时（40 单位）内将镖车送达目标房间 `/d/<area>`。
4. 到达目的地后目标 NPC 接收镖车并结算。

#### 2.3 劫镖（`ask_jiebiao` / `assign_rob`）
1. 林震南从在线玩家中筛选 `is_suitable_rob`：目标为黑道（`shen < 0`）、经验相近、正在执行走镖任务（`xbiao/dest2`）。
2. 玩家被伪装成土匪（临时 `apply/name/short/long/id`），目标是被指定的在线玩家。
3. 击杀目标后，目标尸体/镖货交给林震南结算。

#### 2.4 组队护镖（`do_jobwith`）
1. 玩家 A 输入 `jobwith B`，双方经验差不能过大（`diff > 2 || diff < -2`）。
2. 成功后双方共享 `biao/dest` 与 `biao/dest2`，同时获得条件倒计时，镖车所有者设为两人。

### 关键 NPC、物品、房间、命令
- NPC：林震南 `/kungfu/class/misc/linzhennan.c`。
- 物品：镖货 `/d/city/obj/biaohuo.c`（红镖，限时自毁）、高级镖车 `/kungfu/class/misc/obj/biaoche.c`。
- 房间：扬州福威镖局 `/d/city/biaoju`，以及目标房间如 `/d/dali/yuxuguan`、 `/d/xingxiu/house` 等。
- 命令：`ask lin about 保镖/走镖/工作/job`、`ask lin about 劫镖/jiebiao`、`jobwith <id>`、`ask lin about 放弃/abandon`。

### 奖励类型与结算时机
- 普通走镖：由目标 NPC `award()` 结算，基础 `bonus = 1800 + random(1200)` 经验、潜能 `bonus/2`，并调用 `award2` 发黄金 `(10 + random(10)) * 10000`。
- 劫镖：经验奖励随镖货 `combat_exp` 浮动。
- 组队护镖：奖励由 greeting 函数在玩家再次回到林震南处时结算，公式 `bonus = ob->query("biao/bonus")`，并扣减丐帮/华山派额外 150 点。

### 异常路径
- **失败/放弃惩罚**：删除 `biao`、增加 `biaoju/fail`、施加 `condition("biao")` 封禁，封禁时长与失败/成功比例挂钩。
- **声望不足**：`shen < 0` 无法接镖。
- **经验过低**：<10k 无法接高级护镖；<20k 必须两人组队。
- **每日上限**：林震南自身 `temp("biao") >= 1000` 时称「今天的镖已送完」。
- **超时**：镖货/镖车条件倒计时归零即失败。

### 证据来源
- `/kungfu/class/misc/linzhennan.c`：`ask_biao()`（行 787-842）、`ask_job()`（行 600-686）、`ask_jiebiao()`（行 715-747）、`assign_rob()`（行 749-785）、`do_jobwith()`（行 452-577）、`ask_abandon()`（行 579-598）、`award()`（行 261-294）。
- `/d/city/obj/biaohuo.c`：`destroy_it()` 超时逻辑（行 42-49）。
- `/d/city/npc/biao_assign.h`：另一处普通走镖分配逻辑（行 1-145）。

---

## 切片 3：帮派赏金任务——黄河帮「帮务分档」

### 任务类型名称
帮派赏金任务（按经验分档的随机任务池）

### 触发方式
- 玩家先通过 `ask bangzhu about 入帮/join` 加入随机帮派，成为帮众。
- 再输入 `ask bangzhu about 帮务/job/任务` 领取任务。

### 完整玩家流程
1. **入帮**：帮主校验玩家不是丐帮/大理/名门正派，经验不能高于帮主，且 10 分钟内未反复入帮；成功后给玩家「帮令」`bang ling` 并设置 `bangs/fam`、`bangs/jointime`。
2. **接任务**：帮主根据玩家经验从分档文件 `bangjob3000` ~ `bangjob500000` 中随机选一档，再从该档任务数组中随机抽取一条任务，写入帮令 `ling->set("job", job)`。
3. **执行任务**：任务类型包括：
   - **寻**：找回指定物品（如令牌、砍刀、药材等）。
   - **杀**：击杀指定 NPC（如镖头、家丁、李沅芷、向问天等）。
   - **摊费**：向指定商铺收取保护费（改写 `job` 为商铺信息）。
   - **截镖**：截取镖车，击杀镖头后带回 `biaohuo`。
   - **示威**：击杀敌对帮派帮众。
   - **送礼**：携带彩礼 `caili` 送给指定宾客。
   - **护驾**：护送帮主分身到指定地区。
4. **完成**：除「杀」「送礼」「护驾」外，多数任务通过将物品交给帮主 `accept_object` 完成；帮主删除帮令上的 `job` 并结算。

### 关键 NPC、物品、房间、命令
- NPC：黄河帮帮主 `/d/huanghe/npc/bangzhu.c`。
- 物品：帮令 `/d/huanghe/obj/bangling.c`、彩礼 `/d/huanghe/obj/caili.c`、镖货 `/d/huanghe/obj/biaohuo.c`。
- 任务数据：分档文件 `/d/huanghe/bangjob/bangjob{3000,5000,...,500000}.c`。
- 命令：`ask bangzhu about 入帮/join`、`ask bangzhu about 帮务/job/任务`。

### 奖励类型与结算时机
- **寻物**：`record = bonus/2 + random(bonus)` 经验，其中 `bonus = job["bonus"] * job["max"] / (combat_exp + 1000)`；另加 `score` 到帮令。
- **截镖**：`record = bonus + random(bonus)` 经验，`bonus` 与镖头 `combat_exp` 和玩家经验挂钩。
- 所有结算均降低玩家 `shen`（邪恶阵营）。
- 帮令 `score` 累计到 10/100 以上可找帮主学技能。

### 异常路径
- **无帮令**：帮主会重新发放。
- **任务不符**：交错物品时被斥「连自己的帮务都记不住」。
- **截镖非本人击杀**：`ob->query("my_killer") != who->query("id")` 会被拒绝。
- **CD**：3 分钟重复询问被拒绝。
- **没有适合任务**：当前经验超过所有分档上限时，帮主说「最近没有适合你的帮务」。

### 证据来源
- `/d/huanghe/npc/bangzhu.c`：入帮与任务分配（行 1-318，含 `#include "/d/huanghe/npc/bangzhu_duty.h"`）。
- `/d/huanghe/npc/bangzhu_duty.h`：`ask_join()`（行 7-73）、`ask_job()`（行 77-267）、`accept_object()`（行 277-333）。
- `/d/huanghe/bangjob/bangjob5000.c`、`bangjob50000.c`：任务池定义。

---

## 切片 4：门派日常任务——明教五系生产 / 星宿抓毒虫

### 任务类型名称
门派生产循环 / 采集炼制任务

### 4.1 明教五系日常

#### 触发方式
- 明教弟子与对应掌旗使对话，输入 `ask <npc> about 任务/job` 或 `ask <npc> about 放弃/abandon`。
- 五系对应 NPC：庄铮（金-采矿）、辛然（火-造枪）、唐洋（水-挑水）、闻苍松（木-砍树）、颜垣（土-挖地道）。

#### 完整玩家流程（以唐洋「挑水」为例）
1. **接任务**：唐洋校验明教身份、铁焰令 `tieyan ling`、无当前任务；设置 `mingjiao/job" = "shui_tiaoshui"`，给玩家木桶 `mutong`。
2. **执行**：玩家到碧水寒潭取水，累计 `water_amount` 达到 15 后返回。
3. **完成**：唐洋检测到 `water_amount >= 15`，销毁木桶，调用 `reward(me, "挑水")`。
4. **奖励**：增加明教忠诚度 `mingjiao/cc`、经验、潜能。

#### 关键 NPC、物品、命令
- NPC：唐洋 `/d/kunlun/npc/tangyang.c`；通用奖励与放弃逻辑 `/d/kunlun/npc/mingjiao_job.h`。
- 物品：木桶 `/d/kunlun/obj/mutong.c`（推测路径，由 `OBJ_PATH"/mutong"` 引用）。
- 命令：`ask tang yang about 任务`。

#### 异常路径
- **放弃**：需找对应掌旗使，扣除 `mingjiao/cc` 忠诚度，并删除 `mingjiao/job`。
- **忠诚度过低**：无法再放弃。
- **非对应掌旗使**：想放弃挑水任务却找庄铮，会被要求找对应掌旗使。

#### 证据来源
- `/d/kunlun/npc/tangyang.c`：`ask_job()`（行 62-103）。
- `/d/kunlun/npc/mingjiao_job.h`：`reward()`（行 122-169）、`ask_abandon()`（行 81-118）、`judge_jobmsg()`（行 8-41）。

### 4.2 星宿抓毒虫

#### 触发方式
- 星宿弟子与丁春秋对话，输入 `ask ding about 工作/job`。

#### 完整玩家流程
1. **接任务**：丁春秋校验星宿派身份、无当前任务 `xx_job`；给玩家瓦罐 `wa guan`，设置 `temp("xx_job", 1)`。
2. **寻找毒虫**：玩家在星宿后山房间使用 `search bug` 或 `zhao bug`，基于福缘、属性、搜索次数判定是否刷出毒虫 `duchong`。
3. **捕捉**：毒虫出现后，玩家用 `kou <毒虫id>` 将其扣入瓦罐；成功后 `bug_hold=1`、`found=1`。
4. **炼制**：玩家执行 `xiulian`，瓦罐中毒虫吸血；经过若干轮后生成毒丹 `du dan`。
5. **完成**：将毒丹交给丁春秋 `accept_object`，校验 `player` 匹配后结算经验、潜能、星宿贡献。

#### 关键 NPC、物品、房间、命令
- NPC：丁春秋 `/kungfu/class/xingxiu/ding.c`。
- 物品：瓦罐 `/d/xingxiu/obj/waguan.c`、毒虫 `/d/xingxiu/npc/duchong.c`、毒丹 `/d/xingxiu/obj/dudan.c`。
- 房间：星宿森林 `forest1` ~ `forest12`。
- 命令：`ask ding about 工作`、`search bug` / `zhao bug`、`kou <毒虫>`、`xiulian`。

#### 异常路径
- **无瓦罐**：无法搜索毒虫。
- **精力不足**：搜索消耗 `jingli`/`jing`。
- **战斗中**：无法搜索。
- **已找到未复命**：`temp("found")==1` 时搜索被拒。
- **他人毒虫**：`bug->query("playerid")` 不匹配无法捕捉。
- **随机遭遇**：搜索时可能刷出正派 NPC 追杀玩家；也可能踩到石头受伤。
- **高经验中毒**：`combat_exp > 100000` 时修炼可能中 `huadu_poison`。

#### 证据来源
- `/kungfu/class/xingxiu/ding.c`：`ask_job()`（行 349-371）、`accept_object()` 毒丹结算（行 432-462）。
- `/d/xingxiu/xx_job.h`：`do_search()` 搜索逻辑（行 11-176）。
- `/d/xingxiu/obj/waguan.c`：`do_hold()` / `do_xiulian()`（行 36-109）。
- `/d/xingxiu/npc/duchong.c`：毒虫定义与自毁（行 1-87）。

---

## 切片 5：追杀 / PK 任务——神龙教面罩任务

### 任务类型名称
强制入会投名状 + 教内追杀/威逼任务

### 触发方式
- 非神龙教玩家与胖头陀对话 `ask pang about 神龙教/jiao` 领取「投名状」任务。
- 已入教（`sg/spy`）玩家与胖头陀对话 `ask pang about 效命/task/job/任务` 或服用豹胎易筋丸时触发 `assign_job()`。

### 完整玩家流程

#### 5.1 入会投名状（ask_jiao 分支）
1. 玩家经验 10k-100k，胖头陀从在线玩家中 `filter_array(users(), "is_suitable")` 随机挑选目标。
2. 给玩家面罩 `sg_mianzhao`，记录 `sgjob_join/victim_name`、`victim_id`、`assigntime`。
3. 玩家戴上面罩（`wear mianzhao`）伪装成蒙面人，击杀目标。
4. 在目标尸体上 `sign corpse` 写下「逆神龙教者杀！」，完成任务，设置 `sg_ok/join = 1`。
5. 再次与胖头陀对话服用豹胎易筋丸，正式成为 `sg/spy`。

#### 5.2 教内日常教务（assign_job）
1. 胖头陀根据玩家经验从 `sgjob20000` ~ `sgjob2000000` 分档抽取任务。
2. 任务类型：
   - **寻**：找回指定物品（如少林秘籍、蓝玉钵、血刀等），若仓库已有则重新抽取。
   - **威逼入教（FORCEJOIN）**：从 livings() 中筛选 `is_candidate`，设置 `sgjob/forcejoin`；玩家找到目标后使用 `forcejoin <id>` 进行 8-18 秒的威逼判定。
   - **追杀玩家（PK）**：从在线玩家中筛选 `is_suitable`，设置 `sgjob/victim_id/name`；击杀后在尸体 `sign corpse` 完成。
3. 完成后找胖头陀领豹胎易筋丸或继续接任务。

### 关键 NPC、物品、房间、命令
- NPC：胖头陀 `/kungfu/class/shenlong/pang.c`、洪安通 `/kungfu/class/shenlong/hong.c`。
- 物品：面罩 `/d/shenlong/obj/sg_mianzhao.c`、豹胎易筋丸。
- 命令：`ask pang about jiao/task/job`、`wear mianzhao`、`remove mianzhao`、`sign corpse`、`forcejoin <id>`、`job`、`jobtime`。

### 奖励类型与结算时机
- **入会投名状**：完成后获得豹胎易筋丸并正式入教；无直接经验奖励。
- **追杀玩家**：`sign corpse` 时根据目标 `combat_exp` 计算 `mygain`，增加 `sg/exp` 与 `combat_exp`。
- **威逼入教**：根据目标门派系数 `eff_fam`、毒/伤状态等计算成功率；成功后获得经验、潜能、sg/exp，并掠夺目标身上的独特/高价值物品。
- **寻物**：交给神龙教仓库后由胖头陀确认。

### 异常路径
- **目标离线**：`cancel_pk()` 每日清理，对追杀者施加 `sg/failure` 与 `sg/exp` 惩罚。
- **超时**：投名状 24 小时；教内任务 30 分钟未接或未完成会被惩罚并重新分配。
- **拒绝入会**：被威逼目标多次 `forcetimes > 2` 后会逃跑或反击。
- **非神龙教成员**：无法接教内任务。
- **叛徒**：`sg/cured` 玩家会被拒绝。

### 证据来源
- `/kungfu/class/shenlong/pang.c`：`ask_jiao()`（行 205-284）、`ask_wan()`（行 286-346）、`ask_task()`（行 348-407）、`assign_job()`（行 713-800）。
- `/d/shenlong/obj/sg_mianzhao.c`：`do_wear()`、`do_sign()`、`do_forcejoin()`、`complete_forcejoin()`（行 39-303）。
- `/d/shenlong/junk/cancel_pk.h`：目标离线惩罚逻辑（行 1-44）。

---

## 切片 6：剧情 / 触发任务——雪山葛伦布「还愿供佛」

### 任务类型名称
剧情触发 + 物品交付任务

### 触发方式
- 玩家与雪山派密宗戒律僧 **葛伦布** 对话，输入 `ask ge about 还愿/烧香/供佛`。
- 触发 `do_huanyuan()` 对话。

### 完整玩家流程
1. **触发对话**：葛伦布反问「你拿什么孝敬佛爷呀？」。
2. **交付物品**：玩家将「酥油罐」交给葛伦布（`give su you guan to ge`），触发 `accept_object()`。
3. **完成**：若物品名称匹配「酥油罐」，葛伦布让玩家「里边请」，并设置玩家 `temp("marks/酥", 1)`，作为进入后续房间/剧情的标记。

### 关键 NPC、物品、房间、命令
- NPC：葛伦布 `/d/xueshan/npc/gelun1.c`。
- 物品：酥油罐（本切片未读取到具体定义文件，但 accept_object 以 `ob->name()=="酥油罐"` 判定）。
- 命令：`ask ge about 还愿`、`give <酥油罐> to ge`。

### 奖励类型与结算时机
- 无直接经验/潜能奖励；奖励为剧情推进标记 `marks/酥`，用于解锁后续区域或剧情。

### 异常路径
- **物品错误**：交非酥油罐时葛伦布「露出迷惑的表情」并摇头。
- **无物品**：仅触发对话，无法推进。

### 证据来源
- `/d/xueshan/npc/gelun1.c`：`do_huanyuan()`（行 56-60）、`accept_object()`（行 61-72）、`inquiry` 映射（行 44-48）。

---

## 共性抽象速览

| 维度 | 高频模式 | 代表文件 |
|------|----------|----------|
| 任务状态存储 | 玩家对象 `set("<quest_key>", ...)` / `set_temp("<quest_key>", ...)` | 各任务文件 |
| 任务物品 | `new()` 生成后 `move(me)`，常以 `owner/player` 标记绑定 | biaohuo.c、letter-job.c、waguan.c |
| 冷却/限额 | `time()` 比较、每日上限 `temp("biao")`、条件 `condition` | pang.c、linzhennan.c、xuanci.c |
| 失败惩罚 | `apply_condition` 封禁、扣除门派贡献/忠诚、增加失败计数 | linzhennan.c、bangzhu_duty.h、mingjiao_job.h |
| 奖励结算 | `add("combat_exp", ...)` / `add("potential", ...)` / 金钱 / 技能点 / 门派贡献 | 各任务文件 |
| 目标匹配 | 按经验分档、按门派/声望过滤、随机抽在线玩家或 NPC | bangzhu_duty.h、pang.c、linzhennan.c |

---

*文件结束*
