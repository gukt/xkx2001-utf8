# 世界空间层 玩家故事（Player User Stories）

> 产出角色：玩法切片策划。来源：当前仓库 LPC 一手源码（唯一真相源）。每条故事标注来源（LPC 文件:函数/对象名）。
> 视角：玩家在世界空间层会做什么、遭遇什么。格式 `作为<角色>，我希望/遇到<行为/情境>，以便<价值>`。证据列于每条之后。

---

## US-1：城内探索与门禁

**作为** 新入城的玩家，**我希望** `look` 时看到当前房间的出口清单并知道哪些门关着，**以便** 规划城内导航路线而不走死路。

- 玩家 `look` 时，关门方向的出口从可见清单中剔除（`cmds/std/look.c:48-53`：遍历 exits，`query_door(dir,"status") & DOOR_CLOSED` 的方向置 0 后 `dirs -= ({0})`）。
- 玩家可通过 `open <门名或方向>` 开门（`cmds/std/open.c`：匹配 doors 的 dir/name/id 后调 `open_door(dir)`）。
- 门是双向联动的：一侧开门对侧同步（`inherit/room/room.c:185-186` `ob->open_door(other_side_dir,1)`）。

**验收**：关门出口不可见；`open` 后双侧门状态同步更新；`go <关门方向>` 被拦且提示门名（`room.c:267-271` `valid_leave`）。

---

## US-2：跨区骑乘长途旅行

**作为** 想从华山村去扬州的玩家，**我希望** 骑马沿官道长途移动、马替我承担体力消耗，**以便** 快速跨区且不用自己走断腿。

- 骑乘后移动时坐骑消耗 jingli 而非玩家（`cmds/std/go.c:225-227`：`rided->add("jingli",-cost*2)`，骑手仅 `random(5)==0` 额外扣 2）。
- 马力低时分级警告（`clone/horse/horse.h:32-40`：`<=30` 喘气快跑不动、`<=max/3` 大口喘气）。
- jingli<=10 坠骑受伤（`horse.h:18-23`：骑手 `receive_wound("qi",150)`、马昏迷、`set_leader(0)` 断跟随）。
- 跨区靠 exits 绝对路径，一步跨区（`d/village/hsroad1.c:19` `"south":"/d/city/beimen"`）。
- 室内禁骑、cost>ability 禁行（`go.c:116-119`）。
- 草地可恢复马力（`horse.h:48`：房间 `resource/grass` 时马吃草补 food/jingli）。

**验收**：骑乘移动扣马力不扣（或少扣）人力；马力 3 档预警；坠骑有伤害；官道沿途有草地补给点可续航。

---

## US-3：骑马撞开挡路者

**作为** 骑马赶路的玩家，**我遇到** NPC 或玩家挡住出口（exit_blockers），**我希望** 骑乘冲撞能突破封锁，**以便** 不被无故卡住。

- 挡路机制：房间 `exit_blockers/<dir>` 记录挡路者（`cmds/std/go.c:182`）。
- 骑乘者冲撞：若骑手 `combat_exp >= 挡路者`，可撞下挡路者的坐骑或撞翻（`go.c:194-208`）；若骑手战力远低（`< 挡路者/2`）则被停住（`go.c:210-214`）。
- 步行遇挡路：比 dex，`me.dex < ob.dex+5+random(5)` 被挡（`go.c:186-189`）。

**验收**：骑乘冲撞有战力判定与撞翻效果；步行者靠敏捷检定突破；被挡有明确反馈文案。

---

## US-4：渡口喊船过江

**作为** 站在汉水南岸想过江的玩家，**我希望** 喊一声船家就有渡船驶来、限时上船，**以便** 跨越大江这种 exits 无法直达的地形。

- `yell boat` 触发渡船周期（`inherit/room/ferry.c:28` `do_yell`）。
- 15 秒上船窗口（`ferry.c:90` `call_out("on_board",15)`），期间岸设 exits/enter、船设 exits/out。
- 开船后 20 秒到对岸（`ferry.c:111` `call_out("arrive",20)`），船设 exits/out=opposite。
- 20 秒下船窗口后复位（`ferry.c:138` `close_passage`）。
- yell 文案随 neili/age 变化（`ferry.c:36-44`）。

**验收**：喊船后渡船限时出现；错过窗口被留岸；到对岸限时下船；周期结束后可再次召唤。

---

## US-5：体验昼夜变化与夜间商店关门

**作为** 户外活动的玩家，**我希望** 感知昼夜时段切换、夜间商店关门让我规划白天办事，**以便** 沉浸在世界时间节律中。

- 时段切换全户外广播（`adm/daemons/natured.c:71` `message("outdoor:vision",time_msg,users())`）。
- 8 时段循环（`adm/etc/nature/day_phase`：dawn/sunrise/morning/noon/afternoon/evening/night/midnight）。
- look 户外房间追加时段描述（`cmds/std/look.c:46` `NATURE_D->outdoor_room_description()`）。
- night/midnight 时段 day_shop 商店拒进（`cmds/std/go.c:101-103`；day_shop 房间见 `d/city/chaguan.c` 等）。
- sunrise 自动存档（`natured.c:83` `event_sunrise()`）。

**验收**：户外玩家同时收到时段广播；look 显示当前时段；夜间指定商店进不去且提示「晚上不开」；日出时自动存档。

---

## US-6：驾驶海船出海远航

**作为** 想探索海外岛屿的玩家，**我希望** 在港口上船、start 开船、go 指方向航行、lookout 瞭望找岛，**以便** 到达陆路无法抵达的海外区域。

- 港口上船（`clone/ship/seaboat1.c` exits/down 到船舱；港口 exits/enterN）。
- `start` 开船初始化坐标（`inherit/room/ship.c:73` `do_start`：从港口读 `navigate/locx,locy`）。
- `go <方向>` 设航向（`ship.c:284` `do_go`：e/s/w/n -> 东/南/西/北），`navigate()` 每 2 秒推进一格（`ship.c:202-218`）。
- `lookout` 瞭望报岛屿方位（`ship.c:341` `do_lookout`：72 距离内报方向）。
- `locate` 定位报相对港口距离（`ship.c:423` `do_locate`：非巫师坐标抖动 10%）。
- 到港/到岛双侧 exits 互写（`ship.c:223,254`）。

**验收**：开船后按方向自动推进；瞭望能辨识附近岛屿方位；定位报距离（有误差）；到达后能上岸。

---

## US-7：航海遇险--触礁/暴风雨翻船

**作为** 远航海上的玩家，**我遇到** 暗礁或暴风雨导致翻船，**我希望** 知道风险来源以便规避，**但接受** 高危海域的惩罚。

- 触礁：命中 `clone/ship/seashape.h` jiaos 暗礁坐标（`ship.c:126-133`，±random(3)-1 范围）即翻船。
- 暴风雨翻船：`navigate/weather==2` 且远海（locx>50||locy>50）时 `!random(100)` 翻船（`ship.c:135-140`）。
- 翻船后果（`ship.c:513` `do_drop`）：玩家昏迷、背包销毁（保留铁链 tie lian）、随机冲到某港口。
- 无人超时翻船（`ship.c:46` `time_out` 900+random(500) 秒）。

**验收**：暗礁坐标可被瞭望/经验预判；暴风雨有 long_desc 预警（`ship.c:30-34`）；翻船后玩家被冲上岸且丢装备；超时无人操作有兜底。

---

## US-8：航海遭遇随机事件

**作为** 航行中的玩家，**我希望** 途中偶遇奇景与事件，**以便** 让远航不只是枯燥走格子。

- 每 tick `!random(40)` 触发 10 种随机事件之一（`ship.c:143-182`）。
- 已实现（纯文案）：神迹青光、Titanic 彩蛋、燃烧火鸟、海妖歌声、大海眼、美人鱼、极光（case 3-9）。
- 注释未实现：海怪/财宝/海盗（case 0-2，`ship.c:145-150` 仅注释占位）。

**验收**：航行中偶发氛围文案；但海怪/海盗/财宝等实质事件未落地（代码注释为空）--玩家不应期待战斗/奖励事件。

---

## US-9：荒岛守船

**作为** 到达荒岛的玩家，**我遇到** 荒岛无法唤船（wildharbors），**我希望** 留人守船以便后续撤离，**因为** 荒岛无渡船召唤机制。

- `clone/ship/harbor.h:27` `wildharbors = ({"/d/island/icefire1"})` 标记荒岛。
- `inherit/room/ship.c:549` `do_ready`：若船停在 wildharbor，`call_out("do_ready",100)` 延迟 100 秒（`waited` 标志），需玩家在船内触发。
- 荒岛无 yell 召唤（渡口 ferry 仅在配置了 boat/opposite 的渡口房间生效）。

**验收**：荒岛停靠后船不会立即复位；需派人守船触发 do_ready；无渡船可喊。

---

## US-10：低战力者无法夺船（船只所有权 PvP）

**作为** 低战斗经验的玩家，**我遇到** 船上有更高 combat_exp 的玩家时无法 start/go/stop，**以便** 体现「江湖规矩」--强者说了算。

- `is_owner(ob, me)`（`ship.c:475-482`）：`living(ob) && userp(ob) && ob!=me && ob.combat_exp > me.combat_exp` 返回 1，视为「船主」。
- `do_start`/`do_go`/`do_stop` 均先 `filter_array(inv,"is_owner",me)`，若 `sizeof>0` 则「长这么大连一点江湖规矩都不懂？」（`ship.c:82,294,329`）。

**验收**：船上存在更高战力玩家时，低战力者无法操作船只；只有最高战力者或独自一人时可控船。

---

## 跨故事观察

1. **空间层的「资源-风险-信息」三轴**：骑乘有 jingli 续航资源（US-2/US-3）、航海有暗礁/暴风雨风险（US-7）、瞭望/定位有信息获取玩法（US-6）--世界空间层不只是「移动」，而是资源管理 + 风险规避 + 信息探索的复合体验。
2. **时段是第三维度**：昼夜（US-5）给二维地图叠加时间维度，影响可达性（day_shop）与氛围（广播）--空间层 = 地图 + 时间 + 环境。
3. **PvP 渗透空间层**：exit_blockers 撞人（US-3）、船只所有权（US-10）--世界空间层不是纯 PvE 环境，拓扑本身承载冲突。
4. **半成品警示**：航海随机事件（US-8 case 0-2 未实现）、natured weather_msg（切片5 死代码）--玩家故事需区分「已落地可体验」与「设计意图未实现」，避免向玩家承诺未实装内容。
