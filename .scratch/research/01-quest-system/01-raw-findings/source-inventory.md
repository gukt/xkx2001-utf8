# 01-quest-system 源码盘点：任务系统

> 本文件为 LPC 源码考古员产出的第一手清单，覆盖《侠客行》LPC 源码中可识别的任务类型、任务周边系统、关键调用链与状态变量。所有结论均标注证据来源（文件路径 + 函数/对象名）。本文件止步于源码事实层，不输出 engine 抽象或接口设计。

## 1. 任务源码总体分布

按目录与系统维度，任务相关源码可粗分为以下几大类：

### 1.1 通用任务基础设施

| 目录/文件 | 说明 |
|-----------|------|
| `/clone/obj/job_server.c` | 全服通用任务奖励伺服器，提供经验/潜能上限登记、按时间计酬、统计直方图、巫师调试命令。 |
| `/clone/obj/job.sav/` | 主动性任务系统（武林幻境）的运行时数据与源码备份，含 `job_data.c`、`job_menpai.c`、`job_produce.c`、`job_system.c.sav` 等，部分为二进制存档。 |
| `/cmds/std/ask.c` | 玩家 `ask` 指令入口，是大多数 NPC 任务对话的触发点。 |
| `/cmds/wiz/award.c` | 巫师手动颁奖指令（头衔、九阴真经权限），属于任务外奖励通道。 |
| `/d/wizard/center.c` | 武林幻境（主动性任务系统）的巫师控制台。 |

### 1.2 门派/势力日常任务

| 目录/文件 | 说明 |
|-----------|------|
| `/d/kunlun/npc/mingjiao_job.h` + `/d/kunlun/obj/mingjiao_job.h` | 明教五旗日常任务（采矿、造枪、挑水、砍树、挖地道）的公共奖励与放弃逻辑。 |
| `/d/kunlun/npc/{xinran,zhuangzheng,tangyang,wencangsong,yanyuan}.c` | 明教烈火/锐金/洪水/巨木/厚土五旗掌旗使，分别派发对应日常任务。 |
| `/d/xingxiu/xx_job.h` | 星宿派「找毒虫」日常任务的搜索逻辑与战斗 NPC 生成。 |
| `/kungfu/class/emei/persjob.h` / `pers_job.h` | 峨嵋派护送/接应同门任务（随机生成目标客栈与同门 NPC）。 |
| `/kungfu/class/misc/linzhennan.c` | 福威镖局总镖头，承担走镖、劫镖、普通送货三类任务发放。 |
| `/d/city/npc/biao_assign.h` | 扬州福威镖局普通走镖任务分配头文件。 |
| `/d/city/obj/biaohuo.c` | 普通镖货对象，含限时自毁与任务失败逻辑。 |
| `/d/beijing/npc/duolong.c` + `/d/beijing/job_info.h` + `/d/beijing/helper.c` + `/d/beijing/outer_gate.h` | 北京御林军（侍卫）守门任务链：多隆派任务、城门生成杀手、玩家 `guard/allow`、换班奖励结算。 |

### 1.3 帮派/赏金任务

| 目录/文件 | 说明 |
|-----------|------|
| `/d/huanghe/bangjob/bangjob{3000,5000,10000,20000,50000,100000,300000,500000}.c` | 黄河帮帮主按玩家经验分档发放的任务池：寻物、杀人、截镖、示威、送礼、护驾、摊费等。 |
| `/d/huanghe/changle/bangjob{...}.c` | 长乐帮同分档任务池，结构与黄河帮一致。 |
| `/d/huanghe/npc/bangzhu.c` + `bangzhu_duty.h` | 黄河帮帮主 NPC 与入帮、派任务、验收、授武逻辑。 |
| `/d/huanghe/npc/biaotou.c`、 `/d/huanghe/obj/biaohuo.c`、 `/d/huanghe/doc/info_biao.h` | 截镖任务生成的镖头 NPC、镖货对象、镖局名称与截镖地点池。 |
| `/d/huanghe/obj/bangling.c`、 `bangyin2.c`、 `caili.c` | 帮令（记录任务与积分）、帮印（帮主死亡掉落）、彩礼（送礼任务物品）。 |
| `/d/forest/npc/cl_mi.c`、 `/d/city/npc/huoji.c` | 长乐帮伙计任务、长白山人参买卖任务 NPC。 |

### 1.4 神龙教教务

| 目录/文件 | 说明 |
|-----------|------|
| `/d/shenlong/sgjob/sgjob{20000,50000,100000,500000,1000000,2000000}.c` | 神龙教按经验分档的任务池：寻物、强迫入教（FORCEJOIN）、追杀玩家（PK）。 |
| `/d/shenlong/obj/sg_mianzhao.c` | 神龙教面罩，提供 `sign`、`forcejoin`、`job`、`jobtime` 等教务指令。 |
| `/d/shenlong/sg_process.h` | 神龙教自动教务进程：规劝高经验间谍离教、洪安通追杀拒绝离教者。 |
| `/d/shenlong/junk/cancel_pk.h` | 取消 PK 任务相关逻辑（未深入）。 |
| `/kungfu/class/shenlong/*.c` | 神龙教各 NPC（洪安通、胖头陀、瘦头陀、钟志灵等）与教务交互。 |

### 1.5 Condition 任务状态与计时

| 目录/文件 | 说明 |
|-----------|------|
| `/kungfu/condition/biao.c` | 福威镖局失败后的冷却 condition（自信恢复）。 |
| `/kungfu/condition/biaoju.c` | 走镖/劫镖任务限时 condition，到期判定失败。 |
| `/kungfu/condition/xbiao.c` | 劫镖失败后的冷却 condition。 |
| `/kungfu/condition/ypjob.c` | 一品堂「青铁令」限时 condition，到期记失败。 |
| `/kungfu/condition/lyjob.c` | 灵隐寺诵经任务 condition，在特定房间持续获得佛学/潜能。 |
| `/kungfu/condition/lmjob.c` | 龙门镖局/长乐帮相关计时 condition。 |
| `/kungfu/condition/gb_job.c` | 丐帮密函任务 condition，随机触发密函丢失事件。 |
| `/kungfu/condition/hz_job.c` | 杭州相关任务 condition（目前为空壳）。 |
| `/kungfu/condition/th_yapu_job.c` | 桃花岛哑仆任务 condition（空壳）。 |

### 1.6 其他任务化 NPC/对象

| 目录/文件 | 说明 |
|-----------|------|
| `/d/xueshan/npc/gelun1.c` | 雪山派葛伦布，接受酥油罐触发进门（任务化交互）。 |
| `/d/shaolin/obj/letter-job.c` | 少林推荐信对象，龙门镖局剧情链任务物品。 |
| `/d/dali/npc/duanjin.c` 等 | 大理段氏任务相关 NPC（未深入）。 |
| `/d/huashan/npc/maskman.h`、`maskman2.h` | 华山派面具人相关任务/追杀 NPC。 |

---

## 2. 关键文件清单表

### 2.1 通用基础设施

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/clone/obj/job_server.c` | 任务奖励伺服器：登记各 job 的 exp/pot 上限，按耗时计酬，维护统计直方图 | `start_job()`, `abort_job()`, `reward()`, `set_exp_limit()`, `set_pot_limit()`, `reward_func()`, `set_job_data_func()` | `exp_limit/<job>`, `pot_limit/<job>`, `job_server/<job>_start`（玩家身上）, `stat/<job>`, `exp_hist/<job>`, `pot_hist/<job>`, `job_data/<job>_<data>` | 各任务脚本调用 `JOB_SERVER->reward()` |
| `/cmds/std/ask.c` | 玩家打听指令入口，触发 NPC `inquiry` 回调 | `main()`, `INQUIRY_D->parse_inquiry()` | `inquiry/<topic>`（NPC 属性） | 所有含 `inquiry` 的任务 NPC |
| `/d/wizard/center.c` | 武林幻境主动性任务系统巫师控制台 | `do_start_system()`, `do_close_system()`, `do_start()`, `do_check_menpai_job()`, `do_check_player()`, `do_cut_job()`, `do_change_rate()`, `do_setorg_*()` | 依赖 `/clone/obj/job/job_data`、`job_menpai`、`job_produce` | `/clone/obj/job.sav/*` |
| `/cmds/wiz/award.c` | 巫师手动颁奖（头衔、九阴权限） | `main()` | `title`, `9yin` | 比武大会等奖励场景 |

### 2.2 明教五旗日常任务

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/d/kunlun/npc/mingjiao_job.h` | 五旗任务公共逻辑：任务名映射、放弃扣忠诚、统一奖励 | `judge_jobmsg()`, `cut_abandon_jl()`, `ask_abandon()`, `reward()` | `mingjiao/job`（值如 `jin_caikuang`/`huo_zaoqiang`/`shui_tiaoshui`/`mu_kanshu`/`tu_didao`）, `mingjiao/cc`, `potential`, `combat_exp` | 各掌旗使 `.c` |
| `/d/kunlun/obj/mingjiao_job.h` | 锐金/烈火两旗任务对象验收逻辑 | `judge_jobmsg()`, `cut_abandon_jl()`, `ask_abandon()`, `reward_dest()` | 同上 | `/d/kunlun/npc/xinran.c`, `zhuangzheng.c` |
| `/d/kunlun/npc/zhuangzheng.c` | 锐金旗掌旗使：派发采矿任务 | `ask_job()`, `accept_object()` | `mingjiao/job="jin_caikuang"` | `mingjiao_job.h` |
| `/d/kunlun/npc/xinran.c` | 烈火旗掌旗使：派发造枪任务 | `ask_job()`, `accept_object()` | `mingjiao/job="huo_zaoqiang"` | `mingjiao_job.h` |
| `/d/kunlun/npc/tangyang.c` | 洪水旗掌旗使：派发挑水任务 | `ask_job()` | `mingjiao/job="shui_tiaoshui"`, `temp/water_amount` | `mingjiao_job.h` |
| `/d/kunlun/npc/wencangsong.c` | 巨木旗掌旗使：派发砍树任务 | `ask_job()`, `accept_object()` | `mingjiao/job="mu_kanshu"` | `mingjiao_job.h` |
| `/d/kunlun/npc/yanyuan.c` | 厚土旗掌旗使：派发挖地道任务 | `ask_job()` | `mingjiao/job="tu_didao"`, `temp/didao_done` | `mingjiao_job.h` |
| `/kungfu/class/mingjiao/mingjiao_npc.c` | 明教 NPC 基础模板：铁焰令补发、武功传授、属性初始化 | `ask_tyling()`, `Set_Inquiry()`, `Set_Npcattrib()` | `mingjiao/credit`, `teach_skillsname` | 各掌旗使 `.c` |

### 2.3 福威镖局/走镖/劫镖任务

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/kungfu/class/misc/linzhennan.c` | 福威镖局总镖头：走镖、双人走镖、劫镖、普通送货、验收 | `ask_job()`, `ask_biao()`, `ask_jiebiao()`, `do_jobwith()`, `assign_rob()`, `award()`, `accept_object()` | `biao/dest`, `biao/dest2`, `biao/times`, `biao/fail`, `biaoju/succeed`, `biaoju/fail`, `temp/apply/short`, `xbiao/dest` | `/kungfu/condition/biao.c`, `biaoju.c`, `xbiao.c`; `/kungfu/class/misc/obj/biaoche.c` |
| `/d/city/npc/biao_assign.h` | 扬州普通走镖任务分配 | `ask_biao()` | `temp/biao/zhu`, `temp/biao/bayi`, `temp/biao/ma`, `temp/biao/li`, `temp/biao/jiang`, `temp/biao/times`, `temp/biao/pending` | `/d/city/obj/biaohuo1.c`, `biaohuo.c` |
| `/d/city/obj/biaohuo.c` | 普通镖货对象 | `destroy_it()`, `do_check()` | `temp/dest`, `temp/prop`, `temp/guard` | `biao_assign.h` |
| `/kungfu/condition/biaoju.c` | 走镖/劫镖限时 condition | `update_condition()` | `biao`, `xbiao`, `biao/fail`, `xbiao/fail` | `linzhennan.c` |
| `/kungfu/condition/biao.c` | 走镖失败冷却 condition | `update_condition()` | 无（纯计时） | `linzhennan.c` |
| `/kungfu/condition/xbiao.c` | 劫镖失败冷却 condition | `update_condition()` | 无（纯计时） | `linzhennan.c` |

### 2.4 黄河帮/长乐帮赏金任务

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/d/huanghe/bangjob/bangjob3000.c` | 经验 3000 档任务池（杀/寻/摊费） | `query_job()` | `bangjobs[]` mapping | `/d/huanghe/npc/bangzhu.c` |
| `/d/huanghe/bangjob/bangjob5000.c` | 经验 5000 档任务池（杀/寻/截镖） | `query_job()` | `bangjobs[]` | `bangzhu.c` |
| `/d/huanghe/bangjob/bangjob10000.c` | 经验 10000 档任务池（杀/寻/截镖） | `query_job()` | `bangjobs[]` | `bangzhu.c` |
| `/d/huanghe/bangjob/bangjob{20000,50000,100000,300000,500000}.c` | 更高经验档任务池（结构同上） | `query_job()` | `bangjobs[]` | `bangzhu.c` |
| `/d/huanghe/changle/bangjob{...}.c` | 长乐帮同分档任务池 | `query_job()` | `bangjobs[]` | 长乐帮帮主 NPC |
| `/d/huanghe/npc/bangzhu.c` | 黄河帮帮主 NPC | `ask_join()`, `ask_job()`, `ask_skills()`, `accept_object()` | `fam`, `follower`, `temp/bangs/fam`, `bangs/jointime`, `bangs/asktime` | `bangzhu_duty.h`, `bangjob*.c`, `info_*.h` |
| `/d/huanghe/npc/bangzhu_duty.h` | 帮主职责实现：入帮、派任务、验收、授武 | `ask_join()`, `ask_job()`, `accept_object()`, `do_xue()` | `bangs/fam`, `bangs/jointime`, `bangs/asktime`, `bang ling/job`, `bang ling/score` | `bangzhu.c` |
| `/d/huanghe/obj/bangling.c` | 帮令对象，记录任务与积分 | （对象属性） | `job`, `score`, `owner`, `fam` | `bangzhu_duty.h` |
| `/d/huanghe/doc/info_biao.h` | 镖局名称映射与截镖地点池 | `info_biaoju`, `biao_places` | 无 | `bangzhu.c` |
| `/d/huanghe/obj/caili.c` | 送礼任务彩礼对象 | （对象属性） | `job`, `owner` | `bangzhu_duty.h` |
| `/d/huanghe/obj/bangyin2.c` | 帮主死亡掉落的帮印 | （对象属性） | `my_killer`, `combat_exp` | `bangzhu.c` |

### 2.5 神龙教教务

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/d/shenlong/sgjob/sgjob20000.c` | 经验 2 万档教务池（寻物/FORCEJOIN/PK） | `query_sgjob()` | `sgjobs[]` | 神龙教派发 NPC |
| `/d/shenlong/sgjob/sgjob50000.c` | 经验 5 万档教务池 | `query_sgjob()` | `sgjobs[]` | 同上 |
| `/d/shenlong/sgjob/sgjob100000.c` | 经验 10 万档教务池 | `query_sgjob()` | `sgjobs[]` | 同上 |
| `/d/shenlong/sgjob/sgjob{500000,1000000,2000000}.c` | 更高经验档教务池 | `query_sgjob()` | `sgjobs[]` | 同上 |
| `/d/shenlong/obj/sg_mianzhao.c` | 神龙教面罩：执行任务、验收、查询状态 | `do_sign()`, `do_forcejoin()`, `do_job()`, `do_jobtime()` | `sg/spy`, `sgjob/victim_name`, `sgjob/victim_id`, `sgjob/forcejoin`, `sgjob_join/*`, `sg_ok/pk`, `sg_ok/join`, `sg_ok/forcejoin`, `sg/exp`, `sg_victim/<time>` | `sg_process.h`, `sgjob/*.c` |
| `/d/shenlong/sg_process.h` | 神龙教自动教务：钟志灵规劝离教、洪安通追杀 | `sg_process()`, `message_zhong()`, `message_hong()`, `persuade_leave()`, `do_killing()` | `sg/zhong_persuade`, `sg/zhong_time`, `temp/zhong/nod` | `sg_mianzhao.c`, 神龙教各 NPC |

### 2.6 星宿/峨嵋/雪山/御林军/其他任务

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/d/xingxiu/xx_job.h` | 星宿派找毒虫任务 | `do_search()`, `setup_npc()` | `xx_job`, `find_bug`, `temp/xx/find`, `temp/bug_out`, `temp/found` | 星宿派 NPC |
| `/kungfu/class/emei/persjob.h` / `pers_job.h` | 峨嵋派接应同门任务 | `ask_for_job()` | `condition/get_pers_job`, `last_finished` | `/d/emei/npc/guide.c` |
| `/d/xueshan/npc/gelun1.c` | 雪山派守门喇嘛，接受酥油罐触发进门 | `do_huanyuan()`, `accept_object()` | `temp/marks/酥` | 雪山派入口房间 |
| `/d/beijing/npc/duolong.c` | 御林军侍卫总管，派发守门任务 | `ask_job()`, `ask_suicong()`, `ask_yaopai()`, `do_ling()` | `temp/current_job`, `suicong_num`, `bingbu/*` | `/d/beijing/job_info.h`, `helper.c`, `outer_gate.h` |
| `/d/beijing/job_info.h` | 北京城门名称常量 | `outer_gate_name`, `inner_gate_name` | 无 | `duolong.c`, `outer_gate.h` |
| `/d/beijing/helper.c` | 御林军奖励计算与职级辅助 | `job_reward()`, `shichen()`, `rank_name()`, `juewei_name()` | `bingbu/job_total`, `bingbu/job_rank*`, `bingbu/job_cur`, `bingbu/job_lazy`, `temp/kill_num`, `temp/allow_num` | `duolong.c`, `outer_gate.h` |
| `/d/beijing/outer_gate.h` | 外城门房间逻辑：生成杀手、`guard/allow/climb`、奖励结算 | `do_guard()`, `do_allow()`, `reward_shiwei()`, `gen_killer()` | `temp/can_allow`, `temp/start_job_time`, `temp/kill_num`, `temp/allow_num` | `helper.c`, `duolong.c` |
| `/d/city/npc/huoji.c` | 药铺伙计：长乐帮人参买卖任务询价 | `ask_me()` | `bang ling/job/type`, `bang ling/job/name`, `bang ling/job/prices` | 长乐帮帮主 |
| `/d/forest/npc/cl_mi.c` | 长乐帮长信堂香主：伙计任务收发 | `ask_job()`, `ask_over()` | `temp/bangs/shoptime`, `temp/bangs/fam` | 长乐帮帮主 |

### 2.7 Condition 任务状态文件

| 路径 | 文件用途 | 核心函数/对象 | 关键状态变量 | 相关文件 |
|------|---------|--------------|-------------|---------|
| `/kungfu/condition/ypjob.c` | 一品堂青铁令限时 | `update_condition()` | `yipin/failure` | 一品堂任务 |
| `/kungfu/condition/lyjob.c` | 灵隐寺诵经计时 | `update_condition()` | `temp/lypoint`, 佛学 learned | 灵隐寺 NPC |
| `/kungfu/condition/lmjob.c` | 龙门镖局/长乐帮计时 | `update_condition()` | `temp/lmjob/ok` | 相关 NPC |
| `/kungfu/condition/gb_job.c` | 丐帮密函任务：随机丢失密函 | `update_condition()`, `let_know()` | 检测 `mihan` 对象存在 | 丐帮任务 NPC |
| `/kungfu/condition/hz_job.c` | 杭州任务 condition 空壳 | `update_condition()` | 无 | 杭州任务 |
| `/kungfu/condition/th_yapu_job.c` | 桃花岛哑仆任务 condition 空壳 | `update_condition()` | 无 | 桃花岛任务 |

---

## 3. 任务类型与状态机速览

### 3.1 任务触发方式

| 触发方式 | 代表文件/函数 | 说明 |
|----------|--------------|------|
| 对话触发（`ask <npc> about job/任务`） | `cmds/std/ask.c` → NPC `inquiry/job` 回调 | 最普遍的触发方式，几乎覆盖所有门派/帮派任务。 |
| 指令触发（`guard`、`allow`、`jobwith`、`ling`、`forcejoin` 等） | `/d/beijing/outer_gate.h::do_guard()`、`linzhennan.c::do_jobwith()` 等 | 玩家在任务地点使用特定指令推进。 |
| 物品交付触发 | `accept_object()` 回调 | 交回任务物品（镖货、毒虫、火枪、人参等）完成验收。 |
| 自动进程触发 | `/d/shenlong/sg_process.h::sg_process()`、城门 `call_out gen_killer` | 系统按时间自动生成任务目标或追杀者。 |
| 状态持续触发 | `/kungfu/condition/*.c` 的 `update_condition()` | 每心跳 tick 推进计时或持续收益。 |

### 3.2 常见任务目标类型

| 类型 | 说明 | 代表实现 |
|------|------|---------|
| 寻物 | 寻找指定物品并带回 | 明教采矿/造枪、黄河帮 `bangjob*.c` 中 `type: "寻"`、神龙教 `sgjob*.c` 寻物条目。 |
| 杀 NPC | 击杀指定 NPC | 黄河帮 `type: "杀"`、神龙教 PK/FORCEJOIN。 |
| 送货/走镖 | 将镖货送至指定 NPC/地点 | `linzhennan.c` 走镖、`biao_assign.h` 普通送货。 |
| 截镖 | 击杀系统生成的镖头，夺取镖货 | `bangzhu_duty.h` 截镖分支、`linzhennan.c` 劫镖分支。 |
| 护送 | 护送 NPC 到指定区域 | `bangzhu_duty.h` 护驾分支。 |
| 示威/送礼/摊费/买卖/伙计 | 帮派杂务 | `bangzhu_duty.h` 各分支、`cl_mi.c`、`huoji.c`。 |
| 守门 | 御林军在指定城门防守 | `duolong.c` 派任务 + `outer_gate.h` 执行 + `helper.c` 奖励。 |
| 教务（PK/逼入教/寻物） | 神龙教特有，含玩家间 PK | `sg_mianzhao.c` + `sgjob*.c` + `sg_process.h`。 |
| 诵经/打坐 | 在指定地点持续动作获得收益 | `lyjob.c`。 |

### 3.3 状态变量命名模式

| 命名空间 | 用途 | 典型键值 | 证据来源 |
|----------|------|---------|---------|
| `job_server/<job>_start` | 记录任务开始时间，用于奖励伺服器计酬 | `/clone/obj/job_server.c::start_job()` |
| `<menpai>/job` | 门派当前任务类型 | 明教 `mingjiao/job`：`jin_caikuang` 等 | `/d/kunlun/npc/mingjiao_job.h` |
| `<menpai>/cc` / `credit` / `exp` | 门派贡献/声望 | 明教 `mingjiao/cc`，神龙教 `sg/exp` | `mingjiao_job.h::reward()`、`sg_mianzhao.c::do_sign()` |
| `biao/*` / `xbiao/*` | 走镖/劫镖任务状态 | `biao/dest`, `biao/fail`, `biaoju/succeed` | `linzhennan.c`、`biaoju.c` |
| `temp/bangs/*` | 帮派任务临时状态 | `temp/bangs/fam`, `temp/bangs/shoptime` | `bangzhu_duty.h`、`cl_mi.c` |
| `temp/current_job` | 御林军当前值班城门 | `temp/current_job` | `duolong.c::ask_job()` |
| `bingbu/*` | 御林军职级与任务统计 | `bingbu/job_total`, `bingbu/job_rank*` | `helper.c::job_reward()` |
| `sgjob/*` / `sgjob_join/*` | 神龙教教务目标 | `sgjob/victim_name`, `sgjob/forcejoin` | `sg_mianzhao.c` |
| `sg_ok/*` | 神龙教已完成教务标记 | `sg_ok/pk`, `sg_ok/join`, `sg_ok/forcejoin` | `sg_mianzhao.c::do_job()` |
| `condition/*` | 限时/持续状态 | `biaoju`, `ypjob`, `lyjob`, `gb_job` 等 | `/kungfu/condition/*.c` |
| `temp/apply/short` | 玩家头顶称号/临时外观 | `temp/apply/short` | `linzhennan.c`、`bangzhu_duty.h` |

---

## 4. 任务相关关键词索引

以下列出关键词在源码中出现的主要文件（按目录分组，未穷尽所有引用）：

### 4.1 `job` / `job_server` / `reward`

- `/clone/obj/job_server.c`（核心奖励伺服器）
- `/clone/obj/job.sav/job_data.c`（运行时二进制存档）
- `/clone/obj/job.sav/job_menpai.c`（运行时二进制存档）
- `/clone/obj/job.sav/job_produce.c`（运行时二进制存档）
- `/clone/obj/job.sav/job_system.c.sav`（运行时二进制存档）
- `/d/wizard/center.c`（武林幻境控制台）
- `/cmds/wiz/award.c`（巫师颁奖）
- `/d/huanghe/npc/bangzhu.c`、`bangzhu_duty.h`
- `/d/forest/npc/cl_mi.c`
- `/d/city/npc/huoji.c`
- `/kungfu/class/wudang/zhix.c`、`zhixiang.c`
- `/kungfu/class/misc/linzhennan.c`
- `/d/kunlun/npc/mingjiao_job.h`

### 4.2 `bangjob` / `bangs`

- `/d/huanghe/bangjob/bangjob{3000,5000,10000,20000,50000,100000,300000,500000}.c`
- `/d/huanghe/changle/bangjob{3000,5000,10000,20000,50000,100000,300000,500000}.c`
- `/d/huanghe/npc/bangzhu.c`
- `/d/huanghe/npc/bangzhu_duty.h`
- `/d/huanghe/npc/bangzhong.c`
- `/d/huanghe/obj/bangling.c`
- `/d/huanghe/obj/bangyin2.c`
- `/d/huanghe/obj/caili.c`
- `/d/huanghe/doc/info_biao.h`、`info_bang.h`、`info_store.h`、`info_guest.h`、`info_destine.h`
- `/d/forest/npc/cl_mi.c`

### 4.3 `sgjob` / `sg/spy` / `sg_ok`

- `/d/shenlong/sgjob/sgjob{20000,50000,100000,500000,1000000,2000000}.c`
- `/d/shenlong/obj/sg_mianzhao.c`
- `/d/shenlong/sg_process.h`
- `/d/shenlong/junk/cancel_pk.h`
- `/kungfu/class/shenlong/{lu,hong,pang,xu,su,yin,zhong,fang,shou}.c`
- `/d/shenlong/npc/fang.c`
- `/d/shenlong/qianlong.c`、`liangongfang.c`、`luanshi.c`、`tingkou.c`、`haitan.c`、`zhulin1.c`

### 4.4 `mingjiao_job` / `mingjiao/*`

- `/d/kunlun/npc/mingjiao_job.h`
- `/d/kunlun/obj/mingjiao_job.h`
- `/d/kunlun/npc/{xinran,zhuangzheng,tangyang,wencangsong,yanyuan}.c`
- `/d/kunlun/npc/mingjiao_npc.c`
- `/kungfu/class/mingjiao/mingjiao_npc.c`
- `/d/kunlun/tiekuang.c`、`didao/didao.h`

### 4.5 `biao` / `biaoju` / `biaohuo` / 走镖

- `/kungfu/class/misc/linzhennan.c`
- `/d/city/npc/biao_assign.h`
- `/d/city/npc/biaotou.c`
- `/d/city/obj/biaohuo.c`、`biaohuo1.c`
- `/d/city/npc/obj/biaohuo.c`、`biaohuo1.c`
- `/d/huanghe/npc/biaotou.c`
- `/d/huanghe/obj/biaohuo.c`
- `/d/huanghe/doc/info_biao.h`
- `/kungfu/condition/biao.c`、`biaoju.c`、`xbiao.c`
- `/clone/npc/obj/biaohuo.c`
- `/kungfu/class/misc/obj/biaoche.c`

### 4.6 `condition` 任务相关

- `/kungfu/condition/biao.c`
- `/kungfu/condition/biaoju.c`
- `/kungfu/condition/xbiao.c`
- `/kungfu/condition/ypjob.c`
- `/kungfu/condition/lyjob.c`
- `/kungfu/condition/lmjob.c`
- `/kungfu/condition/gb_job.c`
- `/kungfu/condition/hz_job.c`
- `/kungfu/condition/th_yapu_job.c`

### 4.7 `quest` / `ask` / `inquiry`

- `/cmds/std/ask.c`
- 大量 NPC 文件通过 `set("inquiry", ([...]))` 注册任务入口，如 `/d/kunlun/npc/*.c`、`/kungfu/class/misc/linzhennan.c`、`/d/beijing/npc/duolong.c`、`/d/huanghe/npc/bangzhu.c` 等。

---

## 5. 已发现但未深入文件清单

以下文件在目录浏览或关键词搜索中被识别为与任务系统相关，但本次盘点未逐行阅读，留待后续切片策划或机制抽象组深入：

### 5.1 主动性任务系统（武林幻境）运行时与配置

- `/clone/obj/job.sav/job_area.h`
- `/clone/obj/job.sav/job_ask_about.h`
- `/clone/obj/job.sav/job_assess.h`
- `/clone/obj/job.sav/job_family_master.h`
- `/clone/obj/job.sav/job_include.h`
- `/clone/obj/job.sav/job_message.h`
- `/clone/obj/job.sav/job_npc_pker.h`
- `/clone/obj/job.sav/job_searchitem.h`
- `/clone/obj/job.sav/job_s_opker.c`
- `/clone/obj/job.sav/job_protect_npc.c`
- `/clone/obj/job.sav/default_data.h`
- `/clone/obj/job.sav/lpc_math.h`
- `/clone/obj/job.sav/job_produce.h`
- 说明：`job_data.c`、`job_menpai.c`、`job_produce.c`、`job_system.c.sav` 为二进制或运行时存档，本次仅确认存在与大致职责，未解析内部数据结构。

### 5.2 帮派任务外围文件

- `/d/huanghe/npc/bangzhong.c`（帮众 NPC，可能参与示威/护驾）
- `/d/huanghe/npc/biaotou.c`（截镖目标镖头）
- `/d/huanghe/npc/guanjia.h`（可能与任务验收相关）
- `/d/huanghe/doc/info_bang.h`
- `/d/huanghe/doc/info_store.h`
- `/d/huanghe/doc/info_guest.h`
- `/d/huanghe/doc/info_destine.h`
- `/d/huanghe/doc/set_bang.h`
- `/d/huanghe/doc/bangskills.h`
- `/d/huanghe/skills/*.c`（帮派特殊武功，与授武任务相关）
- `/d/huanghe/obj/bangyin.c`、`bangyin2.c` 差异

### 5.3 神龙教教务外围文件

- `/d/shenlong/npc/fang.c`
- `/d/shenlong/npc/snake.h`
- `/d/shenlong/junk/cancel_pk.h`
- `/kungfu/class/shenlong/{lu,hong,pang,xu,su,yin,zhong,fang,shou}.c`
- `/d/shenlong/data/Sgjob`（运行时数据文件）
- `/d/shenlong/qianlong.c`、`liangongfang.c`、`luanshi.c`、`tingkou.c`、`haitan.c`、`zhulin1.c` 与教务触发关系

### 5.4 门派任务 NPC 与房间

- `/d/xingxiu/npc/*.c`（星宿派任务 NPC 与毒虫对象）
- `/d/xingxiu/npc/xxdizi.c`、`bayi.c`、`duchong.c`、`guaishe.c`
- `/d/xingxiu/obj/{waguan,mianju}.c`
- `/d/emei/npc/guide.c`（峨嵋接应任务目标 NPC）
- `/d/xueshan/npc/{robber,shui,hua,liu,lu}.c`
- `/d/xueshan/dumudian.c`
- `/d/kunlun/didao/didao.h`、`tiekuang.c`（明教挖地道、采矿相关房间/对象）
- `/d/kunlun/npc/wujincao.c`（可能相关）

### 5.5 走镖/劫镖外围

- `/kungfu/class/misc/obj/biaoche.c`（镖车对象）
- `/clone/npc/obj/xbiaoche.c`
- `/clone/weapon/jqbiao.c`、`feibiao.c`
- `/d/xixia/biaoqiyin.c`、`yinfang.c`
- `/d/quanzhou/npc/biao_robber.h`、`biaotou.c`、`qiangdao.c`
- `/d/jiaxing/npc/biao_robber.h`、`qiangdao.c`
- `/d/xingxiu/npc/biao_robber.h`

### 5.6 御林军/北京任务外围

- `/d/beijing/inner_gate.h`
- `/d/beijing/npc/mizheng.c`（兵部尚书，职级升迁）
- `/d/beijing/npc/killer1.c`
- `/d/beijing/beijing_defs.h`
- `/d/beijing/bingbuyamen.c`
- `/d/beijing/wusheng.c`、`east/chongwendajie.c`

### 5.7 其他含 `job`/`quest` 关键词但未深入

- `/d/city/npc/ftb_zhu.c`
- `/d/city/tmp/zhang.c`
- `/d/taohua/npc/{yapu_npc.c,jiading.c,mianfeng.c,yapu_auto_perform.h}`
- `/d/taohua/discuss.h`
- `/d/huashan/npc/{teller.c,t.c,buqun.h,buqun.c,maskman.h,maskman2.h}`
- `/d/huashan/sheshen.c`、`xiaozhu.c`、`hsforest*.c`、`shan*.c`、`fengding.c`、`chaoyang.c`
- `/d/hangzhou/npc/{kumu.c,zhu.c,shi.c,du.c}`
- `/d/hangzhou/xiaoyuan*.c`
- `/d/zhongnan/npc/{qiu.c,killer.c}`
- `/d/zhongnan/obj/pine.c`
- `/d/wudang/shanmen.c`、`/d/wudang/obj/pine.c`
- `/kungfu/class/{taohua/lu.c,murong/yuyan.c,lingjiu/xuzhu.c,lingjiu/tonglao.c,lingjiu/meijian.c,huashan/buyou.c,wudang/zhike.c}`
- `/clone/npc/{qiu.c,xie.c,xie2.c,xiejian.c}`
- `/clone/anqi/*.c`

---

## 6. 关键调用链示例

### 6.1 明教日常任务调用链

```
玩家: ask zhuang zheng about job
  -> /d/kunlun/npc/zhuangzheng.c::ask_job()
     检查 family == "明教"、铁焰令、无当前任务
     -> player->set("mingjiao/job", "jin_caikuang")
     -> 给予铁锹
玩家: 采矿/精炼后交回
  -> /d/kunlun/npc/zhuangzheng.c::accept_object()
     -> /d/kunlun/npc/mingjiao_job.h::reward_dest() 或 reward()
        -> player->add("mingjiao/cc", add_cc)
        -> player->add("combat_exp", add_exp)
        -> player->add("potential", add_pot)
        -> player->delete("mingjiao/job")
```

### 6.2 福威镖局走镖调用链

```
玩家: ask lin zhennan about 走镖
  -> /kungfu/class/misc/linzhennan.c::ask_job()
     -> 检查 biao/fail、condition("biao")、shen、已有 biao 等
     -> player->set("biao/dest", "...")、set("biao/dest2", "/d/...")
     -> player->apply_condition("biaoju", 40)
     -> 生成镖车、镖头跟随
玩家: 到达目标房间交付
  -> 目标 NPC accept_object 或回归林震南
     -> /kungfu/class/misc/linzhennan.c::award()
        -> player->add("combat_exp", bonus)
        -> player->add("potential", bonus/2)
        -> player->add("biaoju/succeed", 1)
        -> clear_one_condition("biaoju")
        -> player->delete("biao")
限时到期:
  -> /kungfu/condition/biaoju.c::update_condition() duration < 1
     -> player->delete("biao/xbiao")、set("biao/fail",1)/set("xbiao/fail",1)
```

### 6.3 黄河帮赏金任务调用链

```
玩家: ask bangzhu about 帮务
  -> /d/huanghe/npc/bangzhu_duty.h::ask_job()
     -> 检查 temp/bangs/fam、bang ling、asktime
     -> 按经验选档：/d/huanghe/bangjob/bangjob<N>.c::query_job()
     -> ling->set("job", job)
     -> 根据 job["type"] 派生：寻/杀/截镖/示威/送礼/护驾/摊费
玩家: 完成任务回交
  -> /d/huanghe/npc/bangzhu_duty.h::accept_object()
     -> 按 type 结算 combat_exp、shen、ling->score
     -> ling->delete("job")
```

### 6.4 神龙教教务调用链

```
玩家（戴面罩）: job
  -> /d/shenlong/obj/sg_mianzhao.c::do_job()
     查询 sgjob/* / sgjob_join/* 状态
玩家: 向胖头陀等领取教务
  -> 对应 NPC 从 /d/shenlong/sgjob/sgjob<N>.c::query_sgjob() 随机抽取
     -> 设置 sgjob/victim_name、sgjob/forcejoin 等
玩家: 完成 PK/逼入教后 sign corpse
  -> /d/shenlong/obj/sg_mianzhao.c::do_sign()
     -> me->set("sg_ok/pk", 1) 或 set("sg_ok/forcejoin", 1)
     -> me->add("sg/exp", ...)
系统自动:
  -> /d/shenlong/sg_process.h::sg_process() 周期性调用
     -> message_zhong() 规劝高经验间谍
     -> message_hong() 洪安通追杀拒绝离教者
```

### 6.5 御林军守门调用链

```
玩家: ask duolong about job
  -> /d/beijing/npc/duolong.c::ask_job()
     -> 检查 IS_SHIWEI、无 current_job
     -> player->set_temp("current_job", outer_gate_name[i])
玩家: 到城门 guard
  -> /d/beijing/outer_gate.h::do_guard()
     -> player->set_temp("can_allow", 1)
     -> player->set_temp("kill_num", 0)
     -> player->set_temp("allow_num", 0)
城门 heartbeat:
  -> /d/beijing/outer_gate.h::gen_killer()
     -> 生成 killer1 NPC
     -> 换班时调用 reward_shiwei()
        -> /d/beijing/helper.c::job_reward()
           -> 计算 speed_cur、pos_ratio、kill_ratio
           -> player->add("combat_exp", exp_reward)
           -> player->add("potential", exp_reward/10)
           -> 更新 bingbu/job_total 等
```

---

## 7. 特殊发现与备注

1. **job_server 与具体任务解耦**：`job_server.c` 只负责按时间计酬与统计，不感知任务内容；具体任务脚本在完成后调用 `JOB_SERVER->reward()` 并传入完成度百分比（`exp_rate`/`pot_rate`）。证据：`/clone/obj/job_server.c::reward_func()` 中按 `(time_now-start_time)` 计算奖励。

2. **任务数据存档混合源码与二进制**：`/clone/obj/job.sav/` 下既有 `.h` 配置头文件，也有 `.c` 运行时数据存档（已序列化），部分文件（如 `job_data.c`）无法直接文本阅读。证据：本次读取显示为乱码。

3. **同一任务逻辑分散在多个头文件与对象中**：例如黄河帮任务池（`bangjob*.c`）与派发/验收逻辑（`bangzhu.c` + `bangzhu_duty.h`）分离；明教奖励逻辑在 `mingjiao_job.h`，但派发在五旗掌旗使 `.c`。

4. **任务状态大量依赖玩家 dbase 临时/永久属性**：几乎所有任务都通过 `player->set()` / `player->query()` / `player->delete()` 保存状态，condition 系统仅用于计时与周期性事件。

5. **存在空壳 condition**：`hz_job.c`、`th_yapu_job.c` 仅做计时器框架，无实际业务逻辑，可能是预留或废弃任务。

6. **玩家间 PvP 任务存在**：神龙教 `sgjob*.c` 中的 `FORCEJOIN` 与 `PK` 条目直接指向玩家角色，配合 `sg_mianzhao.c` 与 `sg_process.h` 实现跨玩家任务链。

7. **任务奖励与职级/贡献绑定**：御林军 `helper.c::job_reward()` 引入职位饱和度（`pos_ratio`）、当前速度（`speed_cur`）等宏观经济参数；明教任务奖励直接增加 `mingjiao/cc` 忠诚度。

---

*文件生成时间：2026-07-24*
*证据来源范围：/home/gukt/github/xkx2001-utf8 仓库根目录下 LPC 源码（adm/、cmds/、d/、kungfu/、clone/ 等）*
