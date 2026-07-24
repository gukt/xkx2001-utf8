# 世界空间层 LPC 源码考古清单

> 调研主题：03-world-space（地图拓扑基底 + Nature 环境叠加层 + 交通跨区移动层）
> 角色：LPC 源码考古员
> 唯一真相源：仓库根下 LPC 一手源码（`d/`、`adm/daemons/natured.c`、`adm/etc/nature/`、`clone/horse/`、`clone/ship/`、`inherit/room/`、`inherit/char/`、`feature/`、`cmds/std/`）。
> 证据要求：每条结论标注来源（文件路径 + 函数/对象名 + 行号或行号区间）。

---

## 0. 重大事实校正（相对 brief 的偏差）

在盘点过程中发现 brief 描述与一手源码存在若干偏差，先列出以纠正后续角色认知：

1. **"6414 房间"实为 6414 个 .c 文件总数（含 NPC/obj），真正房间（`inherit ROOM`）只有 3684 个**。证据：`d/` 下 `find . -name '*.c'` = 6414；其中 `obj/` 子目录 1478 个、`npc/` 子目录 1401 个；`grep -rl "inherit ROOM"` 全 `d/` = 3684 文件；`grep -rl "replace_program(ROOM)"` = 2478（部分房间未调用 replace_program，仍保留 OO 层）。来源：`d/REGIONS.h`（区域声明）、各区域 `wc -l` 统计。
2. **"35 区域"为约数**：`d/REGIONS.h` 的 `region_names` mapping 实际声明 **34 个区域键**（baituo/beijing/changbai/city/dali/death/emei/forest/foshan/gaibang/hangzhou/huanghe/huangshan/huashan/island/jiaxing/kunlun/miaojiang/qilian/quanzhou/shaolin/shenlong/taihu/taishan/taohua/village/wizard/wudang/xiakedao/xingxiu/xixia/xueshan/zhongnan/lingjiu）。但 `d/` 下实际有 **43 个子目录**。9 个目录存在但未在 REGIONS.h 声明：`bwdh`（比武大会/赛事实例）、`dongtinghu`（洞庭湖）、`em`（峨嵋另一部分）、`heimuya`（黑木崖）、`hengshan`（衡山）、`taohuacun`（桃花村）、`tianying`（天鹰教）、`wanshou`（万兽庄）、`xiangyang`（襄阳）。2 个声明无目录：`miaojiang`（苗疆）、`lingjiu`（灵鹫宫）。来源：`d/REGIONS.h` + `ls d/`。
3. **`weather_msg` 5 档天气数组是死代码**：`adm/daemons/natured.c:11` 声明 `string *weather_msg = ({ ... 5 条 ... })`，但全仓库（排除 engine/）`grep weather_msg` 仅此一处出现，**无任何读取/使用**。natured.c 的 `update_day_phase()` 只广播 `day_phase[...]["time_msg"]`（时段切换文案）与 `desc_msg`（房间描述），**没有任何动态天气切换机制**。brief 所称"weather_msg 5 档天气"实际未接线。来源：`adm/daemons/natured.c:11`、`grep -rn "weather_msg"`。
4. **8 个 event_fun 回调中 7 个是空操作**：`adm/etc/nature/day_phase` 为 8 时段各配 `event_fun`（event_dawn/sunrise/morning/noon/afternoon/evening/night/midnight），但 `adm/daemons/natured.c` 只定义了 `event_sunrise()`（自动存档，行 83）与 `event_common()`（行 100）。其余 7 个函数（event_dawn/event_morning/event_noon/event_afternoon/event_evening/event_night/event_midnight）**全仓库无定义**，`call_other(this_object(), "event_dawn")` 在 LPC 里是 no-op。来源：`adm/daemons/natured.c:83,100`、`grep -rn "void event_dawn"`。
5. **`feature/move.c`（154 行）是对象搬迁原语，不是玩家移动命令**：它实现 `move(dest, silently)` + 负重/重量/装备卸下，被万物（含玩家）搬迁环境时调用。真正的**玩家移动命令是 `cmds/std/go.c`（289 行）**，它解析 exits mapping、检查门/骑乘/消耗、调用 `me->move(obj)`、再触发 `follow_me` 跟随。brief 把二者合并描述，实为两个层次。来源：`feature/move.c`、`cmds/std/go.c`。
6. **`outdoor:vision` 广播的户外过滤不在 natured.c，而在 `feature/message.c:25-27`**：`natured.c:71` 的 `message("outdoor:vision", msg, users())` 发给**全体在线玩家**；真正的"只户外房间收到"过滤发生在每个玩家对象的 `receive_message()` 里——`feature/message.c:23` 解析 `outdoor:vision` 为 subclass="outdoor"，行 25-27 `if( !environment() || !environment()->query("outdoors") ) return;` 丢弃非户外房间的消息。来源：`feature/message.c:23-27`、`adm/daemons/natured.c:71`。

---

## 1. 总体分布

### 1.1 地图（d/ 区域与房间）

- **d/ 顶层**：43 个区域子目录 + `d/REGIONS.h`（区域中文名映射，34 键）。来源：`ls d/`、`d/REGIONS.h`。
- **文件总数**：6414 个 `.c`（含 `obj/` NPC 物品 1478 + `npc/` 角色对象 1401 + 房间 3684 + 其它 inherit/skill 等）。来源：`find d/ -name '*.c'`。
- **真正房间数**（`inherit ROOM`）：3684。各区前 10（按房间数降序）：来源 `grep -rl "inherit ROOM"` per region。

  | 区域 | 房间数 | 目录总数(.c) | 备注 |
  |------|-------|------|------|
  | beijing 北京 | 517 | 625 | 含 zijin/beihai/kangqin/west/east 等 8 子目录，最大区 |
  | dali 大理 | 285 | 467 | 文件数第二大但房间数第二 |
  | bwdh 比武大会 | 192 | 276 | 赛事实例区（sjsz 少林之战/sjsz2/sjsz3 看台），非常规地理 |
  | shaolin 少林 | 187 | 368 | |
  | xingxiu 西域 | 183 | 388 | |
  | zhongnan 终南山 | 149 | 246 | |
  | kunlun 昆仑 | 148 | 211 | 含 didao（地道）/mjskill |
  | emei 峨嵋 | 140 | 246 | 与 `em/` 区分开（em 另有 136 房间，疑为峨嵋另一段） |
  | em（峨嵋另一段） | 136 | 242 | 是 `outdoor_room_description()` 的主要使用者 |
  | quanzhou 泉州 | 131 | 323 | 含 biwudahui（比武大会）/yaopu（药铺） |

  其余 33 区房间数见 `grep -rl "inherit ROOM"` 统计（village 华山村 33、city 扬州 124、wizard 仙界 6、death 地狱 12、island 海外 7 等）。完整 41 行分布已采集。

- **户外房间**（`set("outdoors", "xxx")`）：1842 个。前 5 区：dali 188、xingxiu 128、zhongnan 103、beijing 91、qilian/hangzhou 各 86。来源：`grep -rl 'set("outdoors"'`。
- **移动消耗房间**（`set("cost", N)`）：2781 个。来源：`grep -rl 'set("cost'`。
- **景物细节房间**（`set("item_desc", ...)`）：571 个。来源：`grep -rl 'set("item_desc"'`。
- **草地资源房间**（`set("resource/grass")`，供马匹吃草恢复体力）：59 个。来源：`grep -rl 'resource/grass'`。
- **子目录约定**：多数区域含 `obj/`（物品）与 `npc/`（角色）两个标准子目录；部分区有特化子目录（beijing/zijin、huanghe/changle、kunlun/didao、quanzhou/biwudahui、taohua/maze 迷宫、wudang/taoyuan、xueshan/inherit）。

### 1.2 Nature（natured.c 结构）

- **单文件 daemon**：`adm/daemons/natured.c`（193 行），`#pragma save_binary`，无 inherit（独立 daemon）。来源：`adm/daemons/natured.c:1-15`。
- **时段数据文件**：`adm/etc/nature/day_phase`（65 行），文本表格，由 `natured.c` 的 `read_table()` 解析。8 时段：dawn/sunrise/morning/noon/afternoon/evening/night/midnight。各时段 4 字段：`length`（分钟）/`time_msg`（切换广播）/`desc_msg`（房间描述）/`event_fun`（回调名）。来源：`adm/etc/nature/day_phase`。
- **时长校验**：240+120+180+180+180+180+120+240 = **1440 分钟 = 24 小时**（整天循环）。来源：`adm/etc/nature/day_phase` length 列。
- **时间比例**：`natured.c:3` `#define TIME_TICK (time()*60)`——现实 1 秒 = 游戏 1 分钟（60 倍加速）。`init_day_phase()` 用 `localtime(TIME_TICK)` 取当前游戏时刻。来源：`adm/daemons/natured.c:3,30-50`。
- **消息内嵌 ANSI 颜色码**：day_phase 的 time_msg/desc_msg 内含 `[1;36m`/`[46m`/`[37;0m` 等转义序列，由 `feature/message.c` 经 `<ansi.h>` 处理。来源：`adm/etc/nature/day_phase`。

### 1.3 交通（horse / ship / ferry 文件清单）

- **坐骑 `clone/horse/`**：22 个 `.c` 马匹/坐骑 + `horse.h`（2286 字节，通用 condition_check/init）+ `test.c`/`test.h`（测试残留）。马匹清单：aijiaoma（矮脚马）、bailong（白龙马，特殊，能渡河）、baima（白马）、btcamel（白驼）、camel（骆驼）、chuanma（川马）、donkey（驴）、feiyun（飞云）、gongma（公马）、heima（黑马）、hongma（红马）、huangma（黄马）、liuma（骝马）、mengguma（蒙古马）、qingma（青马）、sanhema（三合马）、xiaohongma（小红马）、xiaoma（小马）、yilima（伊犁马）、zaohongma（枣红马）。来源：`ls clone/horse/`。
- **渡口 `inherit/room/ferry.c`**（157 行）+ **渡船房间实例**：`d/shaolin/duchuan.c`、`d/taihu/duchuan.c`、`d/taihu/duchuan2.c`、`d/xixia/duchuan.c`、`d/taohua/duchuan.c`、`d/xiangyang/duchuan.c`、`d/changbai/duchuan.c`（7 处渡船房间）。**FERRY 继承实例**（`inherit FERRY`）：`d/xixia/oldwall.c`、`d/xixia/xhbao.c`、`d/taihu/matou.c`、`d/taihu/matou2.c`、`d/taihu/taihu.c`、`d/heimuya/shuitan1.c`、`d/heimuya/shuitan2.c`、`d/shaolin/hanshui1.c`、`d/shaolin/hanshui2.c`（9 处渡口岸）。来源：`grep -rln "inherit.*FERRY"`、`find d/ -name "duchuan*"`。
- **海船 `inherit/room/ship.c`**（591 行）+ **港口 `inherit/room/harbor.c`**（5194 字节）+ **数据头**：`clone/ship/harbor.h`（港口/海岛坐标）、`clone/ship/seashape.h`（暗礁坐标）。**海船实例**：`clone/ship/seaboat1.c`/`seaboat2.c`/`seaboat3.c`（3 艘，同构）+ **船舱** `clone/ship/cabin1.c`/`cabin2.c`/`cabin3.c`（3 间，seaboat 下行 `down`）。来源：`ls clone/ship/`。
- **官道分布**：`find d/ -name "*road*.c"` = 164 个 + `find d/ -name "*guandao*.c"` = 9 个（d/qilian/guandao1-3）。官道前 5 区：hangzhou 36、wudang 31、xingxiu 27、foshan 18、village 12。官道与普通 road 同构（`inherit ROOM` + exits + outdoors + cost），区别仅在文案"青石官道"。来源：`find d/ -name "*road*"`、`d/qilian/guandao1.c`。

---

## 2. 关键文件清单表

| 文件路径 | 行数 | 职责 | 关键函数/对象 |
|---------|------|------|--------------|
| `inherit/room/room.c` | 281 | 基础房间 inherit（门/reset/物品生成/离开校验） | `static mapping doors`；`make_inventory(file)`；`reset()`（解析 `query("objects")` mapping 生成 NPC/物品）；`look_door(dir)`；`open_door(dir,from_other_side)`/`close_door`；`check_door(dir,door)`；`create_door(dir,data,other_side_dir,status)`；`query_doors()`/`query_door(dir,prop)`；`valid_leave(me,dir)`（门关则阻止离开）；`setup()`（seteuid+reset）；`usr_in()`；`npc_clean_up(str)`；`query_max_encumbrance()` 返回 100000000000（房间无限承重） |
| `d/village/alley1.c` | 24 | 房间定义模式样例（最简） | `inherit ROOM`；`create()` set short/long/exits(方向->目标 mapping)/outdoors/cost/no_clean_up；`setup()`；`replace_program(ROOM)` |
| `d/qilian/guandao1.c` | ~30 | 官道房间样例（跨区连接） | 同上模式；exits 用 `__DIR__"guandao2"` 与 `__DIR__"lanzhou-ximen"` 连接 |
| `d/shaolin/hanshui1.c` | ~45 | 渡口岸房间样例（inherit FERRY） | `inherit FERRY`；set `name`（江名）/`boat`（渡船文件）/`opposite`（对岸文件）；`item_desc`/`resource/water` |
| `d/shaolin/duchuan.c` | ~25 | 渡船房间样例（最简 ROOM） | `inherit ROOM`；`outdoors`/`cost`/`invalid_startroom`；被 ferry.c 动态增删 `exits/out` |
| `feature/move.c` | 154 | 对象搬迁原语（万物 move） | `static int weight/encumb/max_encumb`；`query_encumbrance()`/`over_encumbranced()`；`add_encumbrance(w)`；`set_weight(w)`；`move(dest, silently)`（装备卸下→找目标→负重检查→`move_object`→玩家自动 look）；`remove(euid)`；`move_or_destruct(dest)` |
| `cmds/std/go.c` | 289 | **玩家移动命令**（exits 驱动） | `mapping default_dirs`（22 方向别名）；`main(me,arg)`；`day_event()` 调 `NATURE_D->outdoor_room_event()`；`do_flee(me)` |
| `feature/team.c` | 127 | 队伍/跟随/lord | `static object leader, lord, *team`；`set_leader(ob)`/`query_leader()`；`set_lord(ob)`/`query_lord()`；`follow_path(dir)`→`GO_CMD->main`；`follow_me(ob,dir)`；`add_team_member`/`join_team`/`dismiss_team` |
| `feature/message.c` | ~75 | 消息接收与户外/天气过滤 | `static string *msg_buffer`；`receive_message(msgclass,msg)`（解析 `outdoor:`/`weather:`/`channel:` subclass 过滤）；`write_prompt()`；`receive_snoop()` |
| `adm/daemons/natured.c` | 193 | Nature daemon（昼夜循环） | `#define TIME_TICK`；`static int current_day_phase`；`mapping *day_phase`；`string *weather_msg`（**未使用**）；`read_table(file)`；`init_day_phase()`；`update_day_phase()`；`event_sunrise()`（存档）；`event_common()`；`outdoor_room_description()`；`outdoor_room_event()`；`game_time()` |
| `adm/etc/nature/day_phase` | 65 | 8 时段数据表 | 字段 `length:time_msg:desc_msg:event_fun`；数据行 dawn/sunrise/morning/noon/afternoon/evening/night/midnight |
| `inherit/room/ferry.c` | 157 | 渡口房间 inherit（call_out 渡船周期） | `inherit ROOM`；`setup()`；`init()` add `yell`；`do_yell(arg)`；`check_trigger()`；`on_board()`；`arrive()`；`close_passage()` |
| `inherit/room/ship.c` | 591 | 海船房间 inherit（玩家船导航） | `inherit F_CLEAN_UP; inherit ROOM`；`long_desc()`；`init()` add start/go/stop/lookout/locate；`time_out()`；`valid_leave(me,dir)`；`do_start()`；`navigate()`；`do_go(arg)`；`do_stop()`；`do_lookout()`；`do_locate()`；`is_owner(ob,me)`；`shipweather()`；`niceweather()`；`do_drop()`；`do_ready()` |
| `inherit/room/harbor.c` | ~140 | 港口房间 inherit（yell 唤船 + 登船收费） | `inherit ROOM`；`#define SHIP /clone/ship/seaboat`；`setup()`；`init()` add `yell`；`do_yell(arg)`；`valid_leave(me,dir)`（收 1000 钱）；`do_ready(ship)` |
| `clone/ship/harbor.h` | ~25 | 港口/海岛坐标数据 | `mapping harbors`（4 大陆港：beijing/tanggu locy=0、jiaxing/zhoushan -200、quanzhou/yongning -280、quanzhou/anhai -300）；`mapping islands`（3 海岛港：shenlong/beach [30,20]、island/icefire1 [100,600]、taohua/haitan [20,-210]）；`string *wildharbors`（荒岛 island/icefire1） |
| `clone/ship/seashape.h` | ~20 | 暗礁坐标数据 | `mixed *jiaos`（10 处暗礁 {x,y}） |
| `clone/ship/seaboat1.c` | ~25 | 海船实例（inherit SHIP） | `inherit SHIP`；`create()` set short/long(:long_desc:)/cost=5/`invalid_startroom`；exits down→cabin<num> |
| `clone/ship/cabin1.c` | ~35 | 船舱实例（sleep/no_fight） | `inherit ROOM`；`resource/water`；`objects`（yugan 鱼干+larou 腊肉）；`sleep_room`/`no_fight`；exits up→seaboat<num> |
| `clone/horse/horse.h` | ~85 | 通用马匹体力/吃草/命令 | `condition_check()`（jingli<=10 坠骑）；`init()`（吃草恢复 + add look/ting/stay/fang/release/gen/come） |
| `clone/horse/baima.c` | ~50 | 普通马匹样例（含 horse.h） | `inherit NPC_TRAINEE`；`#include horse.h`；`set("ridable",1)`；`set("max_jingli",630)`；`chat_msg` 随机触发 `condition_check`；`return_home()` 返回 1（不回家） |
| `clone/horse/bailong.c` | ~110 | 特殊马匹（白龙马，能渡河，**不含 horse.h**） | `inherit NPC_TRAINEE`；自实现 init 体力检查；`do_duhe()`（渡河命令，硬编码 6 处渡口点）；`do_tame()` 拒绝驯服 |
| `inherit/char/trainee.c` | 232 | 可驯服动物基类（lord/leader/rider） | `inherit NPC`；`train_it(ob,me,pts)`（>100 分 set_lord）；`do_gen`（跟随 set_leader）；`do_ting`（停留 set_leader(0)）；`do_fang`（释放 set_lord(0)+set_leader(0)+清 rider/rided）；`do_yao`（攻击）；`do_stop`（停止战斗）；`is_trainee()` |
| `cmds/std/qi.c` / `cmds/std/ride.c` | 59 / 59 | 骑乘命令（二者内容**完全相同**，别名 ride|qi） | `main(me,arg)`：校验 busy/character/ridable/living/lord；`me->set("rided",ob)`；`ob->set("rider",me)`；`ob->set_leader(me)` |
| `cmds/std/xia.c` | 35 | 下马命令（别名 unride|buqi） | `main(me,arg)`：清 `me->delete("rided")`；`ob->delete("rider")` |
| `cmds/std/train.c` | 151 | 驯服命令 | 调 `trainee->train_it()` |
| `d/REGIONS.h` | ~40 | 区域中文名映射 | `mapping region_names`（34 键） |
| `include/room.h` | ~10 | 门状态位常量 | `#define DOOR_CLOSED 1`；`DOOR_LOCKED 2`；`DOOR_SMASHED 4`（位标志） |

---

## 3. 调用链与数据结构

### 3.1 房间 exits mapping 如何驱动移动（核心调用链）

**数据结构**：房间通过 `set("exits", ([ "方向": "目标文件路径", ... ]))` 声明出口 mapping。目标路径支持 `__DIR__"xxx"`（同区相对）或绝对路径 `"/d/city/beimen"`（跨区）。证据：`d/village/alley1.c`（`"east":__DIR__"sroad3"`）、`d/village/hsroad1.c`（`"south":"/d/city/beimen"` 跨区到扬州北门）。

**玩家移动调用链**（`cmds/std/go.c:main`，289 行）：
1. 校验：`over_encumbranced()`（行 ~60）、`is_busy()`、`cannot_move` temp、战斗中逃跑检定（`5+random(dex) <= random(enemy dex)` 则 `start_busy(1)` 阻止）、`jingli < max_jingli/10` 精疲力尽阻止（行 ~80）。
2. 取出口：`env = environment(me)`；`exit = env->query("exits")` mapping；`exit[arg]` 取目标（行 ~88-90）。
3. 门校验：`env->valid_leave(me, arg)` → `inherit/room/room.c:valid_leave` 检查 `doors[dir]["status"] & DOOR_CLOSED` 则阻止（行 ~95）。`valid_leave` 可通过 `me->set_temp("new_valid_dest", dest)` 改写目标（行 ~98）。
4. 加载目标：`obj = load_object(dest)`（行 ~103）。
5. **骑乘校验**（行 ~120-135，关键）：
   - 若玩家骑乘（`rided = me->query("rided")`）且目标是人类：目标 `!outdoors` 则拒绝"不能骑著X进去"（**骑马不能进室内**）。
   - `obj->query("cost") > rided->query("ability")` 则拒绝"到了这地方好像走不动了"（**马的 ability 属性 gating 地形难度**）。
   - 日间商店校验：`obj->query("day_shop")` 且 `day_event()` 为 night/midnight 则"晚上不开"。
   - 出口阻挡校验：`env->query("exit_blockers/"+dir)` 另一玩家挡路，dex 检定通过或骑马 combat_exp 撞开。
6. **消耗 jingli**（行 ~225-240，关键）：
   - 骑乘：`random(5)==0` 玩家 -2 jingli；`rided->add("jingli", -env->query("cost")*2)`（**马付 cost×2**）；马 jingli<=0 则 `unconcious()`。
   - 步行（userp）：`me->add("jingli", -env->query("cost")*2)`（**玩家付 cost×2**）；<=0 则 `unconcious()`。
   - 即 **room.cost 是 jingli 消耗基数，每步消耗 cost×2**。
7. 搬迁：`me->move(obj)`（调 `feature/move.c:move`，行 ~250）→ 卸装备检查→负重检查→`move_object(ob)`→玩家自动 `command("look")` 或 brief 模式。
8. **触发跟随**（行 ~255）：`all_inventory(env)->follow_me(me, arg)`——原房间所有对象收到跟随通知。

**跟随调用链**（`feature/team.c:follow_me`，行 37）：
- `follow_me(ob, dir)`：若 `ob==leader`（玩家是马的 leader）或 pursuer 杀 leader：调 `follow_path(dir)`。
- `follow_path(dir)`（行 25）：`remove_all_enemy()` + `GO_CMD->main(this_object(), dir)`——**跟随者递归调用 go 命令走同一方向**。
- 移动技能检定：`random(ob->query_skill("move")) > this_object()->query_skill("move")` 则 `call_out("follow_path", 1, dir)` 延迟跟随（leader move 技能高则 follower 跟得慢），否则立即跟随。
- 这就是**马匹跟随骑手移动的机制**：骑手 go→马 leader=骑手→马 follow_me→马 GO_CMD 走同向→马同样付 cost×2 jingli。

### 3.2 natured.c 的 day_phase 循环与广播通道

**初始化**（`natured.c:init_day_phase`，行 30-50）：
- `local = localtime(TIME_TICK)`；`t = hour*60 + minute`（当天分钟数）。
- 遍历 `day_phase[]`，用 `length` 累减定位当前时段 `current_day_phase`。
- `call_out("update_day_phase", day_phase[(current_day_phase+1)%size]["length"] - t)` 调度下一次切换。

**循环**（`natured.c:update_day_phase`，行 52-80）：
- `remove_call_out("update_day_phase")`；`current_day_phase = (++current_day_phase) % sizeof(day_phase)`。
- 重新 `call_out("update_day_phase", day_phase[current_day_phase]["length"])` 调度下一时段。
- **广播**：`message("outdoor:vision", day_phase[current_day_phase]["time_msg"] + "\n", users())`（行 71）——发给全体在线玩家。
- 回调：若 `event_fun` 已定义则 `call_other(this_object(), event_fun)`（实际仅 `event_sunrise` 有效）；总是调 `event_common()`。

**广播通道过滤**（`feature/message.c:receive_message`，行 11-35）：
- `msgclass = "outdoor:vision"` → `sscanf` 拆 `subclass="outdoor"` + `"vision"`。
- `switch(subclass)`：`case "outdoor": if(!environment() || !environment()->query("outdoors")) return;`（行 25-27）——**玩家所在房间无 outdoors 标记则丢弃消息**。
- `case "weather"`：同理按 `query("weather")` 过滤（行 28-31）。
- `case "channel"`：按 `query("channels")` 过滤。
- 另有 `block_msg/all` 与 `block_msg/<class>` 临时屏蔽、`blind` 状态随机丢弃、BIG5 繁体转换、输入/编辑时缓存到 `msg_buffer`（上限 500）。

**房间接入 Nature 的两种方式**（`grep outdoor_room_description/outdoor_room_event`）：
- 描述拼接：`d/em/duguang1.c:73,85`、`d/em/jinding.c:71,82`、`d/em/ddddd.c:73,84` 等 em 区房间在 long 里 `desc += NATURE_D->outdoor_room_description()`（取当前时段 desc_msg）。
- 事件分支：`d/xingxiu/muding.c:90` `if(NATURE_D->outdoor_room_event()=="event_dawn" ...)`（按时段触发房间特有行为）；`d/huashan/square.c:6`、`d/huashan/buwei1.c:6`、`d/taohua/guanchao.c:16`、`d/xingxiu/jaderoom2.c:14` 定义 `day_event()` 包装。
- `d/city/npc/kexiu.c:251` 用 `NATURE_D->game_time()` 取中文时间戳。

### 3.3 ferry.c 的 call_out 渡船周期

**数据结构**（渡口房间配置，见 `d/shaolin/hanshui1.c`）：
- `set("name", "江")`：水域名（用于文案"X 面上"）。
- `set("boat", __DIR__"duchuan")`：渡船房间文件路径。
- `set("opposite", __DIR__"hanshui2")`：对岸房间文件路径。
- 动态出口：`set("exits/enter", boat)`（岸→船）、船的 `set("exits/out", shore)`（船→岸）。
- 船状态：`set("yell_trigger", 1)`（船忙碌标志）。

**渡船周期调用链**（`inherit/room/ferry.c`）：
1. `init()`：`add_action("do_yell", "yell")`。
2. `do_yell(arg)`：玩家喊 "boat"/"船家"（文案按 age/neili 分级）；调 `check_trigger()`。
3. `check_trigger()`：若 `exits/enter` 已存在（船已靠岸）→"正等着你呢"；否则 `load_object(boat)`，设 `yell_trigger=1`，**双向出口连通**（`exits/enter`=boat 于岸、`exits/out`=shore 于船），文案；`call_out("on_board", 15)`。
4. `on_board()`（**15 秒后**）：收踏脚板，删 `exits/enter`（岸）+船 `exits/out`（船），文案"驶向 X 心"；`call_out("arrive", 20)`。
5. `arrive()`（**再 20 秒后**）：设船 `exits/out = opposite`（船→对岸），文案"到啦，上岸吧"；`call_out("close_passage", 20)`。
6. `close_passage()`（**再 20 秒后**）：删船 `exits/out`，清 `yell_trigger`（船空闲，等下次喊船）。

**总周期**：yell → 15s 靠岸可登 → 20s 开船 → 20s 到对岸可下 → 20s 离开。对岸侧的 `exits/enter` 代码被注释（`ferry.c:143-155`），即**只单向主动唤船，对岸靠 `opposite` 房间也配 FERRY 才能双向**（如 hanshui1↔hanshui2 都 inherit FERRY）。

### 3.4 ship.c 的 call_out 周期（海船导航）

**数据结构**（`clone/ship/harbor.h` + `clone/ship/seashape.h`）：
- 坐标系：`locx` 东西（+东 -西，海岸在 locx<1 即西边）、`locy` 南北（+北 -南）。
- `mapping harbors`：大陆港 filename→locy（4 港，locx 隐含 0）。
- `mapping islands`：海岛港 filename→`({x, y})`（3 岛）。
- `string *wildharbors`：荒岛（island/icefire1，无法 yell 唤船，须留人守船）。
- `mixed *jiaos`：10 处暗礁 `{x, y}`，navigate 时碰撞即沉船。

**海船状态机**（`inherit/room/ship.c` + `inherit/room/harbor.c`）：
- **唤船登船**（harbor.c）：玩家在港口 `yell chuan` → `do_yell` 找空闲 seaboat（无 `trigger`）→设 `trigger=1`、双向出口（港 `exits/enter<i>`→船、船 `exits/out`→港）→`call_out("do_ready", 20, ship)`（20s 后自动开船踢人下船）。登船时 `valid_leave` 收 1000 钱（`harbor.c:valid_leave`），并重置 `do_ready` 为 10s。
- **开船**（ship.c:do_start）：校验无更高 combat_exp 玩家（`is_owner`）；删 `exits/out`（离港）；从港口复制 `navigate/locx/locy`；`call_out("shipweather", 1)` + `call_out("navigate", 2)`。
- **导航循环**（ship.c:navigate，**每 2 秒一次**）：
  - 暗礁碰撞：坐标命中 `jiaos` 随机抖动范围 →沉船 `do_drop()`。
  - 风暴沉船：weather=2 且远海（locx>50||locy>50）`!random(100)` →沉。
  - 随机事件 `!random(40)`（1/40）：10 种（海怪/财宝/海盗/神迹/泰坦尼克幽灵船/火鸟/海妖歌声/海中巨眼/美人鱼/极光）。
  - 无方向（`navigate/dir` 未设）：`!random(100)` 累 `navigate/wait`，>5 则 `do_drop()`（船夫把人扔海里）；继续 `call_out("navigate", 2)`。
  - 移动：按 dir 改 locx/locy（东+1x 南-1y 西-1x 北+1y）。
  - 回港判定：`locx<1` 且 locy 命中某大陆港 locy →靠岸（设 `exits/out`、`call_out("do_ready", 20)`、设港口 `exits/enter<i>`）。
  - 到岛判定：locx/locy 命中某 island 坐标 →靠岛（同上）。
  - 否则文案"往X方向前进"，`call_out("navigate", 2)` 继续。
- **天气循环**（ship.c:shipweather，每 1 秒）：`!random(6)` →weather=1（阴天）；`!random(24)` →weather=2（暴风）；`call_out("niceweather", 5+random(10))` 转晴。
- **瞭望**（do_lookout）：找最近岛（dist<=72 可见），报 8 方向；locx<6 报"西面不远就是岸边"。
- **定位**（do_locate）：找最近大陆港，报海哩数；非巫师坐标加随机抖动（`9/10 + random`）。
- **超时**（time_out，`call_out 900+random(500)` 即 15-23 分钟）：闲置过久"狂风大作船翻了"→`do_drop()`。
- **沉船**（do_drop）：所有玩家 `unconcious()`、清光物品（除 id="tie lian" 铁链）、随机冲上某大陆港。
- **离船**（valid_leave + do_ready）：最后一人 `out` 时 `call_out("do_ready", 5)` 开船；荒岛须等 100s（`waited` 标志）让人守船。

### 3.5 horse 的 rider/rided 与 condition_check

**关系数据结构**：
- 马上：`me->query("rided")` = 骑的马对象（玩家身上）。
- 马上：`ob->query("rider")` = 骑手对象（马身上）。
- `ob->query_lord()` / `set_lord(ob)`：所有权（谁驯服的，`feature/team.c`）。
- `ob->query_leader()` / `set_leader(ob)`：跟随目标（leader 移动则 follower 跟随）。
- `ob->query("ability")`：马匹地形能力值，gating 可通行房间的 `cost` 上限。
- `ob->query("max_jingli")` / `query("jingli")`：体力/最大体力。

**骑乘调用链**（`cmds/std/qi.c:main`）：
- 校验：busy、ob 是 character 且 race≠人类、`ridable`、living、`ob->query_lord()==me`（**必须先驯服为 lord 才能骑**）。
- 建立关系：`me->set("rided", ob)` + `ob->set("rider", me)` + `ob->set_leader(me)`（马跟随玩家）。

**体力衰减调用链**（`clone/horse/horse.h:condition_check`，由马匹 `chat_msg` 随机触发，见 `baima.c` `set("chat_msg", ({ (: condition_check :) }))`）：
- `my_jingli = query("jingli")`；`my_mj = query("max_jingli")`。
- `jingli <= 10`：**坠骑**——`ob=me->query("rider")`，`ob->delete("rided")`、文案"一头从$n上栽下来，跌掉两颗门牙"、`ob->receive_wound("qi", 150, ...)`（骑手受伤）、`me->delete("rider")`、`me->set_leader(0)`（停止跟随）、`me->unconcious()`（马昏厥）。
- `jingli <= 30 && > 20`：文案"只在喘气，渐渐地快跑不动了"。
- `jingli <= my_mj/3`：文案"大口大口地喘着粗气"。
- `init()` 里的**吃草恢复**：若房间 `query("resource/grass")` 且马未吃饱，`add("food", max_food/4)` + `add("jingli", (my_mj-my_jingli)/2)`（恢复一半缺口）、文案"低下头在草地上吃起草来"。

**特殊马匹白龙马**（`clone/horse/bailong.c`，**不 include horse.h，自实现**）：
- `do_duhe()` 渡河命令：`switch(environment(who)->query("short"))` 硬编码 6 处渡口点（汉水南/北岸↔shaolin/hanshui2|hanshui1、古长城/宣和堡↔xixia/xhbao|oldwall、解脱坡/报国寺西墙↔emei/baoguoxi|jietuo），`me->move(dest)`+`who->move(dest)` 直接过河（**不需渡船**）。
- `do_tame()` 拒绝驯服（"白龙马已脱兽籍"）。

---

## 4. 关键回调与状态变量汇总

### 4.1 地图/房间
| 变量/回调 | 定义位置 | 含义 |
|----------|---------|------|
| `query("exits")` mapping | 房间 `set("exits", ...)`；go.c:88 | 方向→目标文件路径 |
| `query("outdoors")` string | 房间；message.c:26 | 户外标志（值如 "village"/"wudang"），决定收 outdoor 广播 |
| `query("cost")` int | 房间；go.c:229 | 移动 jingli 消耗基数（实际 ×2） |
| `query("objects")` mapping | 房间；room.c:reset | NPC/物品文件→数量，reset 时生成 |
| `query("no_clean_up")` int | 房间 | 是否参与 cleanup |
| `static mapping doors` | room.c:13 | 门表，键=方向，值=name/id/other_side_dir/status |
| `doors[dir]["status"]` 位标志 | room.h；room.c | DOOR_CLOSED=1/DOOR_LOCKED=2/DOOR_SMASHED=4 |
| `valid_leave(me, dir)` 回调 | room.c | 门关阻止离开；可被房间 override |
| `query("item_desc")` mapping | 房间 | 景物细节 key→描述/函数 |
| `query("resource/grass")`/`resource/water` | 房间 | 草地/水源，马匹吃草、饮水 |
| `query("day_shop")` | 房间；go.c:120 | 日间商店标志，夜晚关门 |
| `query("exit_blockers/"+dir)` | go.c:210 | 出口阻挡者对象 |
| `query_temp("new_valid_dest")` | go.c:98 | valid_leave 改写目标 |
| `query("invalid_startroom")` | duchuan.c/seaboat | 非合法起始房（船/渡船） |
| `query_max_encumbrance()` | room.c | 返回 100000000000（房间无限承重） |

### 4.2 Nature
| 变量/回调 | 定义位置 | 含义 |
|----------|---------|------|
| `current_day_phase` int | natured.c:7 | 当前时段索引（0-7） |
| `day_phase` mapping array | natured.c:8 | 从 day_phase 文件加载的 8 时段表 |
| `weather_msg` string array | natured.c:11 | **5 档天气文案，未使用（死代码）** |
| `update_day_phase()` | natured.c:52 | call_out 驱动的时段切换主循环 |
| `event_sunrise()` | natured.c:83 | 日出回调：全体玩家自动存档 |
| `event_common()` | natured.c:100 | 每时段：清理无 environment 的 livings、`UPDATE_D->inventory_check` |
| `outdoor_room_description()` | natured.c | 返回当前时段 desc_msg（房间 long 拼接用） |
| `outdoor_room_event()` | natured.c | 返回当前时段 event_fun 名（房间行为分支用） |
| `game_time()` | natured.c | 返回中文游戏时间 |
| `TIME_TICK` macro | natured.c:3 | `time()*60`，现实 1 秒=游戏 1 分钟 |

### 4.3 渡口/海船/骑乘
| 变量/回调 | 定义位置 | 含义 |
|----------|---------|------|
| `query("boat")` | ferry.c; hanshui1.c | 渡船房间文件路径 |
| `query("opposite")` | ferry.c; hanshui1.c | 对岸房间文件路径 |
| `query("name")` | ferry.c | 水域名（文案"X 面上"） |
| `yell_trigger` | ferry.c | 渡船忙碌标志 |
| `exits/enter` / `exits/out` | ferry.c; harbor.c | 动态岸↔船双向出口 |
| `navigate/locx`/`navigate/locy` | ship.c | 海船坐标（+东/北） |
| `navigate/dir` | ship.c | 当前航向（东/南/西/北） |
| `navigate/weather` int | ship.c | 0=晴/1=阴/2=暴风 |
| `navigate/wait` | ship.c | 无方向等待计数（>5 踢人） |
| `trigger` | ship.c; harbor.c | 海船被唤标志 |
| `waited` | ship.c | 荒岛等待标志（100s） |
| `exits/enter<i>` | harbor.c | 港口→第 i 艘船出口（多船编号） |
| `query("rider")` | 马对象；qi.c | 骑手对象 |
| `query("rided")` | 玩家；qi.c | 所骑马对象 |
| `query_lord()`/`set_lord()` | team.c | 所有权（驯服者） |
| `query_leader()`/`set_leader()` | team.c | 跟随目标 |
| `query("ridable")` int | 马对象；qi.c | 可骑标志 |
| `query("ability")` int | 马对象；go.c:131 | 地形能力（gating 可通行 cost 上限） |
| `query("jingli")`/`max_jingli` | 马/玩家 | 体力/最大体力（<=0 昏厥） |
| `query("wildness")`/`loyalty` | trainee.c | 野性/忠诚度（影响驯服难度） |
| `condition_check()` | horse.h | 马体力衰减/坠骑回调（chat_msg 触发） |
| `follow_me(ob, dir)` | team.c:37 | 跟随回调（leader 移动后触发） |
| `do_duhe()` | bailong.c | 白龙马渡河命令 |

---

## 5. 待深入文件清单（后续细读代表）

以下文件在本次盘点中确认承载关键机制或存在特例，值得后续角色（机制抽象组/现代评审组/engine 对照）细读：

### 5.1 地图/移动核心（必读）
- **`cmds/std/go.c`**（289 行）：玩家移动的完整逻辑——exits 解析、门校验、骑乘 gating、cost×2 jingli 消耗、出口阻挡/撞开、follow_me 触发、do_flee。是移动机制的总枢纽，尚未充分剖析 exit_blockers、riding 撞人、playing（箫声魅惑）等支线。
- **`inherit/room/room.c`**（281 行）：门状态机（create_door/open_door/close_door/check_door 双侧同步）、reset 的 objects mapping 生成与 NPC return_home、no_clean_up 计数。
- **`feature/move.c`**（154 行）：对象搬迁的负重/重量链式传递（`add_encumbrance` 向上累加到 environment）、装备卸下、`move_or_destruct` 容错。
- **`feature/team.c`**（127 行）：lord/leader/team 三关系的完整语义，follow_me 的 move 技能检定与 call_out 延迟。
- **`d/village/hsroad1.c` + `d/city/beimen.c`**：跨区连接样例（华山村→扬州北门），验证绝对路径 exit 与区域边界。

### 5.2 Nature（必读 + 风险）
- **`adm/daemons/natured.c`**（193 行）：day_phase call_out 循环、`message("outdoor:vision", ..., users())` 全员广播、`event_common` 的 livings 清理与 `UPDATE_D->inventory_check`。
- **`adm/etc/nature/day_phase`**（65 行）：8 时段数据，含 ANSI 颜色码、event_fun 映射（7/8 是空操作）。
- **`feature/message.c`**（~75 行）：outdoor/weather/channel 三类 subclass 过滤、msg_buffer、blind 随机丢消息、BIG5 转换——是理解"户外广播"真实落点的关键。
- **`d/em/jinding.c` / `d/em/duguang1.c`**：峨嵋金顶/都光殿，`outdoor_room_description()` 拼接到 long 的样例，时段如何影响房间描述。
- **`d/xingxiu/muding.c:90`**：按 `outdoor_room_event()=="event_dawn"` 分支的房间特有行为（门派秘洞时段门控）。

### 5.3 交通（必读）
- **`inherit/room/ship.c`**（591 行）：海船完整状态机——navigate 坐标移动循环、暗礁/风暴/随机事件、weather 三档、lookout/locate 导航、do_drop 沉船、do_ready 离船、is_owner combat_exp 优先级。最大最复杂的交通文件。
- **`inherit/room/harbor.c`**（~140 行）：港口 yell 唤船、多船编号（enter1/2/3）、登船收费 1000、荒岛无法唤船。
- **`clone/ship/harbor.h` + `clone/ship/seashape.h`**：港口/海岛/暗礁坐标表，是海船拓扑的真实数据源。
- **`inherit/room/ferry.c`**（157 行）：渡船 call_out 周期（15+20+20+20s），双向出口动态增删，`opposite` 对岸机制。
- **`d/shaolin/hanshui1.c` + `d/shaolin/hanshui2.c`**：双向渡口对（都 inherit FERRY），验证双向唤船。
- **`clone/horse/horse.h`**（85 行）：马体力衰减三档（10/30/mj÷3）、坠骑受伤、吃草恢复。
- **`clone/horse/bailong.c`**（110 行）：白龙马特例——`do_duhe` 硬编码 6 处渡口点、不需渡船直接过河、不可驯服。是"特殊坐骑能力"的代表。
- **`clone/horse/baima.c`**（50 行）：普通马匹样例，`chat_msg` 触发 condition_check、`ability`/`max_jingli` 数值。
- **`inherit/char/trainee.c`**（232 行）：可驯服动物基类，train_it/lord/set_leader/do_gen/do_ting/do_fang 完整驯服-跟随-释放链。
- **`cmds/std/qi.c` + `cmds/std/xia.c` + `cmds/std/train.c`**：骑乘/下马/驯服命令三件套（qi.c 与 ride.c 重复，疑为别名遗留）。
- **`d/village/majiu.c`**（马厩）：马匹刷新点样例，`objects` 生成 aijiaoma/hongma + ma-fu（马夫）+ car（车）+ caoliao（草料）。

### 5.4 区域代表（可选深读，验证拓扑）
- **`d/beijing/`**（517 房间，最大区）：验证大区域内部拓扑与子目录（zijin 紫禁/beihai 北海/kangqin/west/east）。
- **`d/bwdh/`**（比武大会，192 房间）：赛事实例区，sjsz/sjsz2/sjsz3（少林之战三版本），验证"非地理区域"如何接入地图。
- **`d/taohua/maze/`**：桃花岛迷宫子目录，验证迷宫房间模式。
- **`d/kunlun/didao/`**：昆仑地道子目录，验证地下空间。
- **`d/island/icefire1`**：荒岛（wildharbors），海船可达但无法唤船回程，须留人守船。

---

## 附：盘点方法与未尽事项

- **方法**：以 brief 给定指针为起点，用 `grep -rl`/`find`/`wc -l` 做全量统计，对每个关键文件 `cat` 通读，对调用链用 `grep` 反查引用点交叉验证。所有数字均可由对应 `grep`/`find` 命令复现。
- **未细读但已确认存在**：`inherit/room/p9room.c`（17412 字节）、`inherit/room/pigroom.c`（19194 字节）、`inherit/room/bank.c`、`inherit/room/hockshop.c`（当铺）——这些是 room.c 的特化子类（赌场/猪圈/银行/当铺），属"特殊房间"机制，本次世界空间层盘点未展开，留待玩法切片/机制抽象组判断是否纳入。
- **`ship.c.c`**（20751 字节，`inherit/room/`）：疑为 ship.c 的旧版/备份，未比对差异。
- **`clone/horse/test.c`/`test.h`**：测试残留，未纳入。
- **engine 对照**：本次仅核对 engine 模块行数（nature.py 554 / world.py 280 / room_hooks.py 732 / room_details.py 112 / ferry.py 147 / directions.py 114 / transfer.py 363 / scene_loader.py 1619 / scenes.py 44，与 brief 一致），**未做内容对照**，留给 06-engine-critique 角色。
