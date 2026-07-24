# 玩家视角 User Stories

> 本文件覆盖上述玩法切片中 6 类任务的主路径与常见异常路径。每条故事采用「作为 [玩家类型]，我想 [目标]，以便 [价值]」格式，并附带触发命令/对话示例。所有路径均能在 LPC 源码中找到对应实现。

---

## 1. 师门任务——少林玄慈推荐信

### 主路径

**Story 1.1**
作为少林派 37 代以内弟子，我想向玄慈方丈领取一封去龙门镖局传授武功的推荐信，以便完成门派日常并获得奖励。

- 触发示例：
  ```
  ask xuanci about 工作
  ```
- 证据：`/d/shaolin/npc/xuanci.c` `ask_job()`（行 135-160）。

### 异常路径

**Story 1.2**
作为非少林派玩家，我想向玄慈方丈打听工作，以便尝试接取少林任务。

- 触发示例：
  ```
  ask xuanci about 工作
  ```
- 期望结果：玄慈回复「与本派素无来往，不知此话从何谈起？」。
- 证据：`/d/shaolin/npc/xuanci.c` `ask_job()` 门派校验（行 140-141）。

**Story 1.3**
作为少林低辈分弟子，我想向玄慈方丈领取推荐信，以便快速成长。

- 触发示例：
  ```
  ask xuanci about 工作
  ```
- 期望结果：玄慈让我「还是在少林寺再练几年吧」。
- 证据：`/d/shaolin/npc/xuanci.c` `ask_job()` 辈分校验（行 143-144）。

**Story 1.4**
作为已持有推荐信的玩家，我想再次向玄慈领取任务，以便确认无法重复接取。

- 触发示例：
  ```
  ask xuanci about 工作
  ```
- 期望结果：玄慈回复「已经拿到去龙门镖局传授武功的推荐信了」。
- 证据：`/d/shaolin/npc/xuanci.c` `ask_job()` `present("tuijian xin", me)` 校验（行 149-150）。

---

## 2. 走镖任务——福威镖局

### 主路径

**Story 2.1**
作为江湖正道玩家（经验 ≥10k），我想向林震南接一份普通走镖任务，以便获得经验、潜能和金钱。

- 触发示例：
  ```
  ask lin zhennan about 保镖
  ```
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_biao()`（行 787-842）。

**Story 2.2**
作为经验 ≥200k 的玩家，我想向林震南接高级护镖任务，以便获得更高奖励。

- 触发示例：
  ```
  ask lin zhennan about job
  ```
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_job()`（行 600-686）。

**Story 2.3**
作为经验 10k-200k 的玩家，我想与另一位玩家组队走镖，以便完成必须两人护送的镖。

- 触发示例：
  ```
  jobwith partner_id
  ```
- 证据：`/kungfu/class/misc/linzhennan.c` `do_jobwith()`（行 452-577）。

### 异常路径

**Story 2.4**
作为邪恶阵营玩家，我想接走镖任务，以便测试声望限制。

- 触发示例：
  ```
  ask lin zhennan about job
  ```
- 期望结果：林震南称「是黑道上的英雄，客户信不过」。
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_job()`（行 621-624）。

**Story 2.5**
作为已有一次走镖在身的玩家，我想再接新任务，以便确认并发限制。

- 触发示例：
  ```
  ask lin zhennan about 保镖
  ```
- 期望结果：林震南生气地说「还没将东西送到雇主手上，怎么便想讨多桩差事」。
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_biao()`（行 803-810）。

**Story 2.6**
作为走镖失败的玩家，我想重新接任务，以便确认惩罚机制。

- 触发示例：
  ```
  ask lin zhennan about job
  ```
- 期望结果：林震南训斥后施加 `condition("biao")` 封禁，封禁时长与失败/成功比例相关。
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_job()`（行 605-612）。

**Story 2.7**
作为护镖玩家，我想主动放弃任务，以便了解放弃惩罚。

- 触发示例：
  ```
  ask lin zhennan about 放弃
  ```
- 期望结果：林震南删除任务状态并施加封禁。
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_abandon()`（行 579-598）。

**Story 2.8**
作为高级玩家，我想接劫镖任务，以便通过 PvP 劫取其他玩家的镖货。

- 触发示例：
  ```
  ask lin zhennan about 劫镖
  ```
- 期望结果：林震南将我伪装成土匪，指定一名正在走镖的玩家作为目标。
- 证据：`/kungfu/class/misc/linzhennan.c` `ask_jiebiao()` / `assign_rob()`（行 715-785）。

**Story 2.9**
作为普通走镖玩家，我想确认镖货超时机制，以便规划路线。

- 触发示例：
  ```
  check biao
  ```
- 期望结果：100-120 秒后镖货自毁，任务失败。
- 证据：`/d/city/obj/biaohuo.c` `destroy_it()`（行 42-49）。

---

## 3. 帮派赏金任务——黄河帮

### 主路径

**Story 3.1**
作为无门派或邪派玩家，我想加入黄河帮，以便领取帮务任务。

- 触发示例：
  ```
  ask bangzhu about 入帮
  ```
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_join()`（行 7-73）。

**Story 3.2**
作为黄河帮众，我想向帮主领取一份适合我经验的帮务，以便赚取经验和帮贡。

- 触发示例：
  ```
  ask bangzhu about 帮务
  ```
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()`（行 77-267）。

**Story 3.3**
作为黄河帮众，我想将寻到的任务物品交给帮主，以便领取奖励。

- 触发示例：
  ```
  give lingpai to bangzhu
  ```
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `accept_object()`（行 277-333）。

### 异常路径

**Story 3.4**
作为丐帮弟子，我想加入黄河帮，以便确认门派限制。

- 触发示例：
  ```
  ask bangzhu about 入帮
  ```
- 期望结果：帮主大怒，怀疑我是卧底。
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_join()`（行 15-18）。

**Story 3.5**
作为黄河帮众，我 3 分钟内再次 ask 帮务，以便确认冷却限制。

- 触发示例：
  ```
  ask bangzhu about 帮务
  ```
- 期望结果：帮主说「不是刚问过我吗」。
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_job()`（行 115-118）。

**Story 3.6**
作为截镖任务玩家，我想将非本人击杀的镖货交给帮主，以便确认归属校验。

- 触发示例：
  ```
  give biaohuo to bangzhu
  ```
- 期望结果：帮主怒斥「江湖中最讲究的就是信用」。
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `accept_object()`（行 310-311）。

**Story 3.7**
作为帮贡累计足够的帮众，我想向帮主请教武功，以便消耗帮贡学习技能。

- 触发示例：
  ```
  ask bangzhu about 武功
  xue <skill_id>
  ```
- 证据：`/d/huanghe/npc/bangzhu_duty.h` `ask_skills()` / `do_xue()`（行 336-419）。

---

## 4. 门派日常任务——明教五系 / 星宿抓毒虫

### 4.1 明教五系

**Story 4.1**
作为明教弟子，我想向唐洋领取挑水任务，以便获得明教忠诚度、经验和潜能。

- 触发示例：
  ```
  ask tang yang about 任务
  ```
- 证据：`/d/kunlun/npc/tangyang.c` `ask_job()`（行 62-103）。

**Story 4.2**
作为已完成挑水的明教弟子，我想返回唐洋处交任务，以便领取奖励。

- 触发示例：
  ```
  ask tang yang about 任务
  ```
- 期望结果：唐洋检测到 `water_amount >= 15`，调用 reward。
- 证据：`/d/kunlun/npc/tangyang.c` `ask_job()`（行 77-86）。

**Story 4.3**
作为正在执行挑水任务的明教弟子，我想放弃任务，以便测试忠诚度惩罚。

- 触发示例：
  ```
  ask tang yang about 放弃
  ```
- 期望结果：扣除 `mingjiao/cc`，删除任务状态。
- 证据：`/d/kunlun/npc/mingjiao_job.h` `ask_abandon()` / `cut_abandon_jl()`（行 43-118）。

**Story 4.4**
作为没有铁焰令的明教弟子，我想领取任务，以便确认信物要求。

- 触发示例：
  ```
  ask tang yang about 任务
  ```
- 期望结果：唐洋让我先去拿铁焰令。
- 证据：`/d/kunlun/npc/tangyang.c` `ask_job()`（行 71-72）。

### 4.2 星宿抓毒虫

**Story 4.5**
作为星宿弟子，我想向丁春秋领取抓毒虫任务，以便获得经验和星宿贡献。

- 触发示例：
  ```
  ask ding chunqiu about 工作
  ```
- 证据：`/kungfu/class/xingxiu/ding.c` `ask_job()`（行 349-371）。

**Story 4.6**
作为持有瓦罐的星宿弟子，我想在星宿后山搜索毒虫，以便找到任务目标。

- 触发示例：
  ```
  search bug
  ```
- 证据：`/d/xingxiu/xx_job.h` `do_search()`（行 11-176）。

**Story 4.7**
作为已找到毒虫的星宿弟子，我想用瓦罐扣住毒虫并修炼成毒丹，以便交付任务。

- 触发示例：
  ```
  kou chong
  xiulian
  give du dan to ding chunqiu
  ```
- 证据：`/d/xingxiu/obj/waguan.c` `do_hold()` / `do_xiulian()`（行 36-109）；`/kungfu/class/xingxiu/ding.c` `accept_object()`（行 432-462）。

**Story 4.8**
作为没有瓦罐的星宿弟子，我想直接搜索毒虫，以便确认工具限制。

- 触发示例：
  ```
  search bug
  ```
- 期望结果：系统提示「你找到虫子用什么来盛呢」。
- 证据：`/d/xingxiu/xx_job.h` `do_search()`（行 39-40）。

**Story 4.9**
作为搜索毒虫的星宿弟子，我想确认可能遭遇的正派追杀，以便评估风险。

- 触发示例：
  ```
  search bug
  ```
- 期望结果：随机刷出正派 NPC 并攻击玩家。
- 证据：`/d/xingxiu/xx_job.h` `do_search()`（行 108-118）。

---

## 5. 追杀 / PK 任务——神龙教面罩

### 主路径

**Story 5.1**
作为想加入神龙教的江湖人士（经验 10k-100k），我想向胖头陀领取投名状，以便完成入会条件。

- 触发示例：
  ```
  ask pang toutuo about 神龙教
  ```
- 证据：`/kungfu/class/shenlong/pang.c` `ask_jiao()`（行 205-284）。

**Story 5.2**
作为已入神龙教的玩家，我想向胖头陀领取日常教务，以便获得豹胎易筋丸并维持教籍。

- 触发示例：
  ```
  ask pang toutuo about 任务
  ```
- 证据：`/kungfu/class/shenlong/pang.c` `ask_task()`（行 348-407）。

**Story 5.3**
作为被指派追杀某玩家的神龙教徒，我想戴上面罩击杀目标并在尸体上签名，以便完成任务。

- 触发示例：
  ```
  wear mianzhao
  kill target_id
  sign corpse
  ```
- 证据：`/d/shenlong/obj/sg_mianzhao.c` `do_wear()` / `do_sign()`（行 51-115）。

**Story 5.4**
作为被指派威逼 NPC 入教的神龙教徒，我想对目标使用 forcejoin，以便完成教务。

- 触发示例：
  ```
  forcejoin target_id
  ```
- 证据：`/d/shenlong/obj/sg_mianzhao.c` `do_forcejoin()` / `complete_forcejoin()`（行 118-303）。

### 异常路径

**Story 5.5**
作为追杀目标已离线的神龙教徒，我想等待系统处理，以便确认离线惩罚。

- 触发示例：无主动命令；系统在目标离线后自动触发。
- 期望结果：删除 `sgjob`，增加 `sg/failure`，扣除 `sg/exp`。
- 证据：`/d/shenlong/junk/cancel_pk.h` `cancel_pk()`（行 1-44）。

**Story 5.6**
作为 30 分钟内未完成教务的神龙教徒，我想再次 ask 任务，以便确认超时惩罚。

- 触发示例：
  ```
  ask pang toutuo about 任务
  ```
- 期望结果：胖头陀大怒，扣除 `sg/exp` 与 `sg/failure`，并重新分配任务。
- 证据：`/kungfu/class/shenlong/pang.c` `ask_task()`（行 381-404）。

**Story 5.7**
作为叛徒（已解毒 `sg/cured`），我想找胖头陀接任务，以便确认排斥逻辑。

- 触发示例：
  ```
  ask pang toutuo about 任务
  ```
- 期望结果：胖头陀怒斥「无耻的叛徒，还不给我滚」。
- 证据：`/kungfu/class/shenlong/pang.c` `ask_task()`（行 355-356）。

**Story 5.8**
作为神龙教徒，我想查看当前教务和已用时间，以便规划完成节奏。

- 触发示例：
  ```
  job
  jobtime
  ```
- 证据：`/d/shenlong/obj/sg_mianzhao.c` `do_job()` / `do_jobtime()`（行 422-488）。

---

## 6. 剧情 / 触发任务——雪山葛伦布还愿

### 主路径

**Story 6.1**
作为路过雪山密宗的玩家，我想与葛伦布对话触发还愿剧情，以便推进后续区域/剧情。

- 触发示例：
  ```
  ask ge lunbu about 还愿
  ```
- 证据：`/d/xueshan/npc/gelun1.c` `do_huanyuan()` / `inquiry`（行 44-60）。

**Story 6.2**
作为已触发还愿对话的玩家，我想将酥油罐交给葛伦布，以便获得进入后续区域的标记。

- 触发示例：
  ```
  give su you guan to ge lunbu
  ```
- 期望结果：葛伦布说「佛爷保佑施主，里边请」，并设置 `temp("marks/酥", 1)`。
- 证据：`/d/xueshan/npc/gelun1.c` `accept_object()`（行 61-72）。

### 异常路径

**Story 6.3**
作为没有酥油罐的玩家，我想随便给葛伦布一个物品，以便确认剧情物品校验。

- 触发示例：
  ```
  give some_item to ge lunbu
  ```
- 期望结果：葛伦布「露出迷惑的表情」并摇头。
- 证据：`/d/xueshan/npc/gelun1.c` `accept_object()`（行 62-67）。

---

## 跨类型通用 User Stories

**Story 7.1**
作为任何玩家，我想在接任务前确认自己是否符合门派/声望/经验限制，以便避免被拒绝。

- 覆盖：少林师门（门派/辈分）、走镖（声望/经验）、黄河帮（门派/经验）、神龙教（经验/阵营）。

**Story 7.2**
作为任何玩家，我想在任务失败或被放弃后了解惩罚，以便决定是否继续尝试。

- 覆盖：走镖 `condition("biao")`、明教忠诚度扣除、神龙教 `sg/exp` 扣除。

**Story 7.3**
作为任何玩家，我想确认任务状态由谁持有（玩家对象 vs 任务物品），以便理解数据流。

- 覆盖：少林推荐信绑定玩家对象；走镖状态绑定玩家对象 `biao/*`；黄河帮状态写在帮令对象上；神龙教状态写在玩家对象 `sgjob/*`。

---

*文件结束*
