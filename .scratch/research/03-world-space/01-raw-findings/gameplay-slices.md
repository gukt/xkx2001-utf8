# 世界空间层 玩法切片（玩家视角 + 数据流）

> 产出角色：玩法切片策划。来源：当前仓库 LPC 一手源码（唯一真相源）。每条结论标注来源文件 + 函数/对象名。
> 选片原则：覆盖地图拓扑 / Nature 环境叠加 / 交通跨区移动 三层，且两两交互处优先。共 6 个切片。

---

## 切片 1：城内导航——门、出口与房间拓扑（地图层）

### 玩家操作步骤

1. 玩家站在扬州城某房间，输入 `look` 查看当前环境。
2. 房间描述末尾列出「明显的出口」清单；若某方向的门关着，该出口从清单中**被剔除**（看不到）。
3. 玩家想进入带门的房间（如监狱 `d/city/jail.c`），`go east` 被拦：「你必须先把铁门打开！」。
4. 玩家输入 `open 铁门`（或 `open east`）打开门；门是**双向联动**的——本侧打开时，对侧房间的同名门也同步打开。
5. 再次 `go east` 进入，触发 `look` 自动展示新房间。

### 背后数据流

| 环节 | 来源（文件:函数/对象） | 状态/数据 |
|------|----------------------|-----------|
| 房间定义模式 | `d/village/alley1.c` create()：`set("exits",...)` mapping（方向->目标房间路径）、`set("outdoors","xxx")`、`set("cost",1)`、`setup()` + `replace_program(ROOM)` | exits 是 `方向字符串 -> 目标房间文件路径` 的 mapping |
| 门数据结构 | `inherit/room/room.c:227` `create_door(dir, data, other_side_dir, status)`；`static mapping doors`（每方向一项） | 每扇门含 `name`/`id`/`other_side_dir`/`status`（位标记 DOOR_CLOSED） |
| 门开关 | `inherit/room/room.c:168` `open_door(dir, from_other_side)` / `:193` `close_door(...)`；`from_other_side=1` 时跳过对侧再调用，避免递归 | 改 `doors[dir]["status"]` 位标记 |
| 双向联动 | `room.c:185` `open_door` 内 `find_object(exits[dir])` 后调 `ob->open_door(doors[dir]["other_side_dir"], 1)` | 两侧房间共享 door 状态语义，靠 other_side_dir 互指 |
| 离开校验 | `inherit/room/room.c:267` `valid_leave(me, dir)`：若该方向有门且 `DOOR_CLOSED`，`notify_fail("你必须先把...打开！")` | 门关 = 出口不可用 |
| open 命令 | `cmds/std/open.c` main()：取 `query_doors()`，按 arg 匹配方向或门名/ id，调 `open_door(dir)` | 玩家可 `open <方向>` 或 `open <门名>` |
| look 展示 | `cmds/std/look.c:31` `look_room()`：`env->query("outdoors")? NATURE_D->outdoor_room_description() : ""`（第 46 行注入时段描述）；出口列表在 48-60 行，关门出口被置 0 后剔除 | 关门出口对玩家「不可见」 |
| look_door | `inherit/room/room.c:158` `look_door(dir)`：关门返回「这个X是关着的」，开门返回「是开着的」 | `item_desc/<dir>` 绑定到 look_door |

### 体验要点

- **门是房间拓扑的动态开关**：同一房间 exits 不变，但可见出口随门状态变化，制造「探索-解锁」节奏（`look.c:51-53` 过滤关门出口）。
- **双向联动是关键设计**：一侧开门对侧同步（`room.c:185-186`），避免「这边开了那边还关」的割裂感；但联动依赖 `other_side_dir` 字段正确配置，是 UGC 创作易错点。
- **门无锁/钥匙机制**：`room.c` 的 door 只有 CLOSED 开关位，无锁定/钥匙/破坏等扩展（代码注释 `// if ( door[dir]["status"] & DOOR_HAS_TRAP ) ....` 暗示曾设想陷阱但未实现，`room.c:272`）。对现代引擎是扩展缺口。
- **exit_blockers 拦路**：`cmds/std/go.c:182` `env->query("exit_blockers/"+dir)` 允许 NPC/玩家挡住出口，骑乘者可撞开（`go.c:194-219`），是城内 PvP/劫镖的拓扑层基础。

---

## 切片 2：跨区官道骑乘——华山村→扬州北门沿途（地图层 + 交通层）

### 玩家操作步骤

1. 玩家在华山村驯服一匹马（`clone/horse/baima.c` 白马，`max_jingli=630`），先 `set` 马的主人为自己，再输入 `qi bai ma`（`cmds/std/qi.c`）骑上。
2. 骑乘后沿官道移动：从 `d/village/hsroad1.c`（碎石路）`go south` 直达 `/d/city/beimen`（扬州北门）——**单步跨区**，exits 值直接指向另一区域文件路径。
3. 每次移动消耗坐骑 `jingli`（精力）：`go.c:226` `rided->add("jingli", -env->query("cost")*2)`，房间 `cost` 字段决定消耗（官道常为 1-2）。
4. 马力衰减到 `jingli<=30` 时 `clone/horse/horse.h:32` 打印「只在喘气，渐渐地快跑不动了」；`<=max_jingli/3` 打印「大口大口地喘着粗气」。
5. `jingli<=10` 时 `horse.h:18` 触发坠骑：骑手 `receive_wound("qi",150)`（掉两颗门牙）、马 `unconcious()`、`set_leader(0)`（马不再跟随）。
6. 骑乘者想进室内（非 outdoors 房间）被拦：`go.c:116-117`「你不能骑着X进去」；目标房间 `cost > 马->ability` 也被拦（`go.c:118-119`）。

### 背后数据流

| 环节 | 来源 | 状态/数据 |
|------|------|-----------|
| 跨区 exits | `d/village/hsroad1.c:19` `"south":"/d/city/beimen"`；`d/village/eexit.c:18` `"east":"/d/huashan/hsstreet1"` | exits 值用绝对路径跨区域，无「区域边界」抽象——跨区=普通移动 |
| 房间 cost | `d/village/alley1.c:21` `set("cost",1)`；`d/village/eroad1.c` cost=1 | 移动消耗基数 |
| 骑乘关系 | `cmds/std/qi.c:33-35` `me->set("rided",ob)` / `ob->set("rider",me)` / `ob->set_leader(me)` | 双向引用：人记 rided、马记 rider；`set_leader` 使马跟随人移动 |
| 骑乘移动消耗 | `cmds/std/go.c:225-227`：骑乘时 `random(5)==0` 额外扣人 jingli -2；`rided->add("jingli",-cost*2)`；`jingli<=0` 马昏迷 | 马 jingli 是跨区长途移动的核心消耗资源 |
| 步行消耗 | `cmds/std/go.c:229-230` 无马时 `me->add("jingli",-cost*2)`；`jingli<=0` 人昏迷 | 步行同样耗 jingli，骑乘优势是马替你扛消耗+速度文案 |
| 室内禁骑 | `cmds/std/go.c:116` `!obj->query("outdoors")` 时拒绝骑乘进入 | outdoors 标志决定可骑区域 |
| 体力衰减回调 | `clone/horse/baima.c:36` `set("chat_msg",({(:condition_check:)})` + `chat_chance=50`；`clone/horse/horse.h:7` `condition_check()` | 马的随机 heart_beat 触发 condition_check，自主衰减/吃草恢复 |
| 草地恢复 | `clone/horse/horse.h:48` 房间 `query("resource/grass")` 时马吃草恢复 food/jingli | 环境资源点支持坐骑续航 |

### 体验要点

- **跨区无过渡**：`hsroad1.c` exits 直接写 `/d/city/beimen`，玩家一步从华山村进入扬州城，无加载/动画/过场——是 LPC 时代「无缝大世界」的朴素实现，现代引擎可考虑加过渡叙事但需警惕移动疲劳。
- **jingli 是空间层的体力门**：长途骑乘消耗坐骑 jingli（`go.c:226`），低 jingli 触发分级警告（`horse.h:32-40`），坠骑有伤害惩罚（`horse.h:22`）。这给了「补给点/换马点」设计空间——官道沿途的草地（`resource/grass`）即是天然补给。
- **outdoors 是骑乘的硬边界**：室内不可骑（`go.c:116`），意味着城内密集室内区是步行区，官道/野外是骑乘区——形成两种移动节奏。
- **set_leader 跟随链**：骑乘时马 `set_leader(me)`（`qi.c:35`），`go.c:243` `all_inventory(env)->follow_me(me,arg)` 让坐骑随人移动；坠骑后 `set_leader(0)`（`horse.h:27`）断链——这是「跟随」机制的复用。

---

## 切片 3：渡口过江——汉水南岸→北岸周期（交通层）

### 玩家操作步骤

1. 玩家在 `d/shaolin/hanshui1.c`（汉水南岸，`inherit FERRY`）看到 item_desc：「近岸处有一叶小舟，也许喊(yell)一声船家就能听见。」
2. 输入 `yell boat`（或 `yell 船家`）。若玩家 neili>500，文案为「中正平和地远远传了出去」（`ferry.c:39-42`）；年龄<16 则「使出吃奶的力气」。
3. 渡船驶来：岸边房间出现 `exits/enter`（上船出口），船房间出现 `exits/out`（上岸出口），15 秒后 `on_board()` 收起踏板开船。
4. 玩家须在 15 秒内 `go enter` 上船，否则被留在岸上。
5. 开船后 20 秒 `arrive()`：对岸船侧出现 `exits/out`，玩家 `go out` 上岸到 `opposite` 房间。
6. 再 20 秒后 `close_passage()` 清理 exit，渡船周期结束；`yell_trigger` 标志清除，可再次召唤。

### 背后数据流

| 环节 | 来源 | 状态/数据 |
|------|------|-----------|
| 渡口继承 | `d/shaolin/hanshui1.c:6` `inherit FERRY`；`d/taihu/matou.c:3` 同 | 渡口房间继承 `inherit/room/ferry.c` |
| 渡口配置 | `hanshui1.c:37-39` `set("name","江")` / `set("boat",__DIR__"duchuan")` / `set("opposite",__DIR__"hanshui2")` | 三个关键字段：水面名、船房间路径、对岸房间路径 |
| yell 命令 | `inherit/room/ferry.c:25` `add_action("do_yell","yell")`（init 注册）；`:28` `do_yell(arg)` | arg=="boat" 转为「船家」；非船家只回声 |
| check_trigger | `ferry.c:55`：若已有 exits/enter 则「正等着你呢」；否则 `room->set("yell_trigger",1)`、双侧 set exits、`call_out("on_board",15)` | yell_trigger 防重入；15 秒上船窗口 |
| on_board | `ferry.c:93`：删岸边 exits/enter、删船 exits/out，`call_out("arrive",20)` | 船「离岸」状态，玩家被困在船房间 |
| arrive | `ferry.c:114`：船设 `exits/out = opposite`，「到啦，上岸吧」；`call_out("close_passage",20)` | 20 秒下船窗口 |
| close_passage | `ferry.c:141`：删船 exits/out、`delete("yell_trigger")` | 周期复位 |
| 周期总长 | 15(on_board) + 20(arrive) + 20(close_passage) = 55 秒/单程 | 用 call_out 串接，非状态机 |

### 体验要点

- **时间窗口压力**：15 秒上船 + 20 秒下船，玩家必须及时操作，错过就被「困在岸/船」（`ferry.c:60` 已有 enter 则提示「正等着你呢」可重入）。这制造轻度紧张感，但对 AFK/网络延迟玩家不友好——现代引擎应考虑宽限或排队。
- **双侧房间协同**：渡口靠 `set("exits/enter",boat)` + `boat->set("exits/out",岸)` 双房间互写 exits 实现「上船/上岸」，无独立「载具容器」抽象——载具就是一个房间，移动=跨房间 exits。这是 LPC 交通的统一模式（船、渡口皆然）。
- **yell 文案随玩家属性变化**：neili>500 文案不同（`ferry.c:39-44`），是「属性影响世界反馈」的轻量设计，非数值效果。
- **无费用、无容量**：渡船不收费、无人数上限（船房间是普通 ROOM），任何玩家可反复召唤——简单但缺商业化/稀缺性钩子。

---

## 切片 4：昼夜时段对户外的影响（Nature 层 + 地图层交互）

### 玩家操作步骤

1. 玩家在户外房间（`set("outdoors","xxx")`，如 `d/village/alley1.c:19`）。
2. 时段切换时（如 dawn→sunrise），**所有在线户外玩家**同时收到一条广播：「太阳从东方的地平线升起了。」（`adm/etc/nature/day_phase` time_msg）。
3. 玩家 `look` 时，房间 long 描述后追加当前时段描述（`look.c:46` `NATURE_D->outdoor_room_description()`），如「太阳刚从东方的地平线升起」。
4. 到 event_night/event_midnight 时段，带 `day_shop` 标志的商店关门：玩家 `go` 进商店被拦「X 晚上不开，请天亮了再来！」（`go.c:101-103`）。
5. event_sunrise 触发时，**全体在线玩家自动存档**（`natured.c:83` `event_sunrise()` 遍历 `users()` 调 `link_ob->save()` + `ob[i]->save()`）。

### 背后数据流

| 环节 | 来源 | 状态/数据 |
|------|------|-----------|
| 8 时段定义 | `adm/etc/nature/day_phase`：dawn(240)/sunrise(120)/morning(180)/noon(180)/afternoon(180)/evening(180)/night(120)/midnight(240)，单位「分钟」 | 每段 length/time_msg/desc_msg/event_fun |
| 时段驱动 | `adm/daemons/natured.c:50` `call_out("update_day_phase", next_length - t)`；`:54` `update_day_phase()` 递增 `current_day_phase` 并再次 call_out | call_out 自循环驱动时间流逝 |
| 全户外广播 | `natured.c:71` `message("outdoor:vision", day_phase[..]["time_msg"]+"\n", users())` | 广播给 users()，由 `outdoor:vision` 消息类型过滤到户外玩家 |
| look 注入 | `cmds/std/look.c:46` `env->query("outdoors")? NATURE_D->outdoor_room_description():""`；`natured.c:144` `outdoor_room_description()` 返回 `day_phase[current]["desc_msg"]` | 户外房间 look 额外显示时段描述 |
| event_fun 回调 | `natured.c:72-73` `call_other(this_object(), day_phase[..]["event_fun"])`：event_dawn/sunrise/noon... + `:75` `event_common()` | 每时段触发对应事件函数 |
| 昼夜商店 | `cmds/std/go.c:101-103` `obj->query("day_shop") && (day_event()=="event_night"\|\|"event_midnight")` 拒绝进入；`day_shop` 房间如 `d/city/chaguan.c`/`shuyuan.c`/`jujinge.c`/`dangpu.c`/`datiepu.c` | 时段影响房间可达性 |
| 自动存档 | `natured.c:83` `event_sunrise()`：遍历 `users()`，`link_ob->save()` + `ob[i]->save()` | sunrise = 全服存档点 |
| event_common | `natured.c:100`：清理无 environment 的 livings（非 user 直接 destruct，user 丢到 `/d/city/wumiao.c`）；随机 `UPDATE_D->inventory_check` | 时段切换=清理/校验时机 |

### 体验要点

- **时段是跨房间的全局节拍**：`message("outdoor:vision",...,users())`（`natured.c:71`）一次性广播给所有户外玩家，制造「世界同步呼吸感」——所有人同时看到日出。这是 LPC 最具沉浸感的设计之一，但全量 `users()` 广播在大规模在线下是性能热点（现代引擎需分区/订阅）。
- **时段影响可达性（day_shop）**：night/midnight 商店关门（`go.c:101-103`），把「时间」变成拓扑变量——夜间地图「缩水」。这给了日夜差异化玩法的钩子（夜间黑市、夜行 NPC）。
- **sunrise 自动存档**：把存档绑定到世界时间而非玩家行为（`natured.c:83`），是「世界驱动系统行为」的典型范式。
- **event_fun 是扩展点**：每时段可挂回调（`natured.c:72`），但目前仅 sunrise/noon 等少数实现，dawn/morning/afternoon/evening 的 event_fun 多为空——是未充分开发的设计空间。

---

## 切片 5：天气影响——vestigial 的 natured 天气 vs 实际的船航天气（Nature 层 + 交通层）

### 玩家操作步骤（实际可体验的部分——仅航海天气）

1. 玩家驾驶海船（`clone/ship/seaboat1.c`，`inherit SHIP`）出海，`start` 后 `navigate()` 每 2 秒推进一格。
2. `shipweather()`（`inherit/room/ship.c:484`）随机生成天气：`!random(6)` 设 `navigate/weather=1`（多云/风浪）；`!random(24)` 设 `=2`（暴风雨巨浪）。
3. 天气影响 `long_desc()`（`ship.c:30-34`）：weather=1「海船左右摇晃」；weather=2「几丈高的巨浪，随时翻船」。
4. weather=2 且远离岸边（locx>50）时，`!random(100)` 概率**翻船**（`ship.c:135-140`）：全员 `unconcious()`、背包物品销毁（保留 tie lian 铁链）、随机冲到某港口岸上。
5. `niceweather()`（`ship.c:507`）恢复 weather=0（风平浪静）。

### 背后数据流

| 环节 | 来源 | 状态/数据 |
|------|------|-----------|
| natured weather_msg（**vestigial/未使用**） | `adm/daemons/natured.c:11-17` 定义 5 档天气字符串数组，但**全仓库无任何代码引用 weather_msg 变量**（grep 确认仅定义处自身 + archive 文档 + engine 参照） | natured 的天气系统是**死代码**，从未接入广播或房间描述 |
| 船航天气状态 | `inherit/room/ship.c:491` `query_temp("navigate/weather")`：0=平静 / 1=风浪 / 2=暴风雨 | 三态，仅作用于船房间 |
| 天气生成 | `ship.c:484` `shipweather()`：`!random(6)`->1（约 1/6）、`!random(24)`->2（约 1/24）；无天气则每秒重 roll | 概率性天气切换 |
| 天气展示 | `ship.c:30-34` `long_desc()` switch(weather) | 仅在船房间 long 描述体现 |
| 天气致灾 | `ship.c:135-140`：weather==2 && drop_factor(locx>50\|\|locy>50) && `!random(100)` && 无 exits/out -> 翻船 do_drop | 远海暴风雨有翻船风险 |
| do_drop | `ship.c:513`：玩家 unconcious、销毁背包（保留铁链）、`move` 到随机港口；NPC 直接 destruct | 翻船=高惩罚失败状态 |
| time_out | `ship.c:46` `call_out("time_out",900+random(500))`：超时无人操作强制翻船 | 船有「无人驾驶超时」兜底 |

### 体验要点

- **natured 的 weather_msg 是「设计意图但未落地」的死代码**（`natured.c:11-17` 定义却无引用）：说明《侠客行》原计划做全局天气广播但未实现。这是给新引擎的**风险警示**——不要照搬「weather_msg 5 档」当作已验证机制；它是未完成的设计草图。现代引擎若做天气应真正接入户外广播与玩法效果。
- **实际天气只在航海**：`ship.c` 的 shipweather 是唯一功能性天气，且是局部状态（船房间 temp），非全局广播。天气=航海专属风险源，陆地无天气影响。
- **天气惩罚极重**：翻船=昏迷+丢光装备+随机流放（`ship.c:513-531`），是高风险高不确定性的设计，现代引擎需谨慎——硬核但易劝退。
- **三态过粗**：0/1/2 三档难以表达渐变天气，且天气生成纯随机无季节/区域差异——可扩展点。

---

## 切片 6：玩家船航海——导航/瞭望/触礁/到港（交通层）

### 玩家操作步骤

1. 玩家在港口房间（如 `/d/beijing/tanggu`，`harbor.h:4` harbors 映射）找到海船，`go enter1` 上船（`seaboat1.c`，exits/down 到船舱 cabin）。
2. `start` 开船（`ship.c:73`）：船删 `exits/out`、从港口删 `exits/enter1`、初始化 `navigate/locx,locy` 为港口坐标、启动 `shipweather` + `navigate` call_out。
3. `go east`（`do_go`，`ship.c:284`）设 `navigate/dir=东`；`navigate()` 每 2 秒按 dir 推进 locx±1/locy±1（`ship.c:202-218`）。
4. `lookout`（`do_lookout`，`ship.c:341`）瞭望：算到最近岛屿的方位/距离，72 距离内报「东北方向X」，否则「大海茫茫」。
5. `locate`（`do_locate`，`ship.c:423`）定位：报相对最近港口的「东约N海哩北约M海哩」（非巫师坐标有 `*9/10+random` 抖动，`ship.c:448-449`）。
6. 到达岛屿/港口坐标时（`ship.c:223` locx<1 到港口 / `:254` 命中 islands 坐标到岛）：船设 `exits/out`，港口设 `exits/enterN`，`go out` 上岸。
7. 途中可能触礁（`ship.c:126-133` 命中 `seashape.h` jiaos 暗礁坐标 -> 翻船）、遇随机事件（`ship.c:143` `!random(40)`：美人鱼/海怪/海盗/Titanic 彩蛋等 10 种，`ship.c:144-182`）。
8. `stop`（`do_stop`，`ship.c:323`）暂停推进；无人操作 900-1400 秒后 `time_out` 强制翻船（`ship.c:46`）。

### 背后数据流

| 环节 | 来源 | 状态/数据 |
|------|------|-----------|
| 海洋坐标系 | `clone/ship/harbor.h:9` `harbors`（大陆港口 locx=0,locy 各异）、`:18` `islands`（海岛 {locx,locy}）、`:27` `wildharbors`（荒岛列表） | 用二维 (locx,locy) 离散坐标建模海洋，locx=东西(+东)、locy=南北(+北) |
| 暗礁 | `clone/ship/seashape.h:6` `jiaos = ({...})` 暗礁坐标数组 | 命中 ±random(3)-1 范围即触礁（`ship.c:128`） |
| 船状态 | `ship.c` 全程用 `set_temp("navigate/locx"/"locy"/"dir"/"weather"/"wait"/"trigger"/"waited")` | navigate/* temp mapping 是船的完整运行态 |
| navigate 循环 | `ship.c:112` `navigate()`：每 2 秒 call_out 自调用；检查暗礁->检查翻船->随机事件->无方向则 wait 累积(>5 次踢人)->按 dir 推进->检查到港 | 单线程 call_out 驱动的航海 tick |
| 开船 do_start | `ship.c:73`：校验无「更强的船主」在场（`is_owner`，`:475` combat_exp 比较）、删双侧 exits、初始化坐标、启动 shipweather+navigate | 「江湖规矩」= 战斗经验低者不能开船（PvP 抢船机制） |
| do_go | `ship.c:284`：e/s/w/n 映射到东南西北，设 `navigate/dir` | 只设方向，navigate tick 实际推进 |
| do_lookout | `ship.c:341`：遍历 islands 算最近距离/方位，dist>72 报「茫茫」 | 72 = 6*12，6 格内可辨方位 |
| do_locate | `ship.c:423`：遍历 harbors 算最近港口，非巫师坐标抖动 10% | 定位有误差，巫师精确 |
| 到港/到岛 | `ship.c:223`（locx<1 到大陆港口）/ `:254`（命中 island 坐标到岛）：set exits/out + 港口 set exits/enterN + `call_out("do_ready",20)` | 到港=双侧 exits 互写 + 20 秒下船窗口 |
| do_ready | `ship.c:539`：把船内玩家 move 到港口、删双侧 exits | 船复位 |
| 随机事件 | `ship.c:143` `!random(40)` 触发，10 种（case 0-9）：海怪/财宝/海盗/神迹/Titanic/火鸟/海妖歌声/大海眼/美人鱼/极光 | 多为纯文案彩蛋，case 0-2 注释了但未实现 |

### 体验要点

- **离散网格 + call_out tick 的航海模型**：海洋是 (locx,locy) 整数网格，每 2 秒走一格（`ship.c:112,279`），这是最朴素的「格子地图导航」——无连续坐标/物理。现代引擎可升级为连续坐标但需保留「瞭望-定位」的探索乐趣。
- **is_owner 抢船 PvP**（`ship.c:475`）：`combat_exp` 更高者被视为「船主」，低经验者无法 start/go/stop——把船只控制权绑定到战斗等级，是强 PvP 服的设计，现代引擎应改为所有权/钥匙模型。
- **瞭望与定位的「信息获取」玩法**（`ship.c:341,423`）：lookout 给方位不给距离、locate 给距离但有 10% 误差——航海靠玩家拼凑信息找岛，是有趣的探索机制；但坐标抖动（`ship.c:448`）对新手极不友好，易迷路。
- **随机事件多为「彩蛋文案」无实际效果**（`ship.c:144-182`）：美人鱼/Titanic/极光只 tell_room 不触发机制，是氛围装饰；case 0-2（海怪/财宝/海盗）注释了但**未实现**——设计意图与落地有差距。
- **超时翻船兜底**（`ship.c:46` `time_out` 900+random(500) 秒）：防止玩家挂机占船，是资源回收机制；但翻船惩罚过重（丢装备），对正常短暂离开的玩家也不友好。

---

## 跨切片观察（供机制抽象组参考）

1. **exits mapping 是世界空间层的统一数据底座**：房间拓扑（切片1）、跨区移动（切片2）、渡口上下船（切片3）、船只到港（切片6）全部通过 `set("exits",...)` + `go <方向>` 实现，载具/门/区域边界都是「房间间 exits 的动态增删」。无独立的「传送门」「载具容器」抽象。
2. **call_out 是所有时序的驱动器**：昼夜（`natured.c:50`）、渡船周期（`ferry.c:90,111,138`）、航海 tick（`ship.c:106`）、马匹 heart_beat（`baima.c:36` chat_chance）——全是 `call_out` 自循环或 `chat_msg` 随机触发。无集中调度器。
3. **outdoors 标志是多切片的交汇点**：骑乘限制（`go.c:116`）、Nature 广播过滤（`outdoor:vision`）、时段描述注入（`look.c:46`）都依赖 `set("outdoors",...)`——它是「室内/户外」语义的唯一开关，但值是任意字符串（"xxx"/"shaolin"/"emei"），无强类型约束。
4. **「vestigial 设计」警示**：natured weather_msg（切片5）定义但未接入，说明 LPC 源码存在「半成品设计」，考古时必须区分「已落地」与「仅声明」，不能把声明当机制。
