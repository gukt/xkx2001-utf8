# 世界空间层 - 通用机制抽象

> 产出角色：空间/移动机制设计师。资料来源优先级：LPC 一手源码（唯一真相源）。每条结论标注 `LPC 文件路径 + 函数/对象名`。本文只抽象「题材无关的通用机制」，不绑定具体区域内容；具体房间文案/迷宫布局不在范围内。
>
> 关键交叉发现（先列出，后文各节展开）：
> - **天气系统是「半成品/僵尸代码」**：`natured.c` 定义了 5 档 `weather_msg` 数组，`message.c` 留了 `weather:` 消息子类过滤逻辑，但全仓库无任何房间 `set("weather")`、也无任何代码 `message("weather:...")` 广播。`weather_msg` 数组被定义后从未被引用。LPC 的「天气」实际上从未上线（见 §9）。
> - **`outdoors` 标志的值是字符串标签，但引擎层只消费其布尔真假**；标签（如 `"village"`/`"shaolin"`）是区域/音效元数据，不被通用机制消费（见 §10）。
> - **8 个 `event_fun` 回调里只有 2 个有实现**（`event_sunrise` 存盘、`event_common` 清理），其余 6 个（dawn/morning/noon/afternoon/evening/night/midnight）是空调用（见 §8）。
> - **船只天气 `shipweather` 与全局 Nature 天气完全无关**，是 ship.c 内的独立局部状态机（见 §7/§9）。

---

## 1. 拓扑与出口

### 1.1 区域映射

- **LPC 出处**：`d/REGIONS.h`（`region_names` mapping，38 个键值对，但 CLAUDE.md 记 35 区域）。
- **数据结构**：`mapping region_names = ([ "baituo":"西域白驼山", "beijing":"北京", "city":"扬州", "shaolin":"嵩山少林", "village":"华山村", ... ])`。键是目录名（`d/<key>/`），值是中文显示名。
- **作用**：声明 `d/` 下区域目录到中文名的映射；房间路径用 `/d/<region>/<room>` 寻址。区域是「目录即区域」的隐式约定，无独立区域对象/边界声明。

### 1.2 房间出口 mapping

- **LPC 出处**：房间定义模式见 `d/village/alley1.c`（`create()`）；基础房间 `inherit/room/room.c`。
- **数据结构**：`set("exits", ([ <方向词>: <目标房间路径>, ... ]))`。
  - 同区域用 `__DIR__"sroad3"` 宏（相对当前目录）。
  - 跨区域用绝对路径，如 `d/village/hsroad3.c` line 18：`"south" : "/d/emei/emroad6"`（华山村 → 峨嵋）。
  - 目标路径是字符串（LPC object path），移动时由 `load_object()`/`find_object()` 解析为对象（见 §4）。
- **触发条件**：玩家执行 `go <方向>`（`cmds/std/go.c`）时，`env->query("exits")` 查表得到目标。
- **与周边交互**：门挂在出口上（§2）；`valid_leave` 在出口上做离开闸门（§3）；`look` 命令枚举可见出口（`cmds/std/look.c` line 48-61，关闭的门对应方向被置 0 后过滤掉）。

### 1.3 方向词体系

- **LPC 出处**：`cmds/std/go.c` line 10-34（`default_dirs` mapping）。
- **数据结构**：22 个方向键 → 中文显示名：
  - 基本四向：`north/south/east/west` → 北/南/东/西。
  - 斜向：`northeast/northwest/southeast/southwest` → 东北/西北/东南/西南。
  - 高低向：`northup/southup/eastup/westup` 与 `northdown/...` → 「北边/南边/...」（注意：`*up` 与 `*down` 的显示名都是「X边」，区分靠 exits 里实际挂的方向键）。
  - 竖直/特殊：`up/down` → 上/下；`out/enter/in` → 外/里/里；`left/right` → 左/右。
- **触发条件**：`go.c` line 124-127：若 `default_dirs[arg]` 有定义则用其作显示名，否则直接用 `arg`（支持自定义方向词，如 `enter1`/`enter2` 这类被 harbor.c 动态注入的出口，见 §7）。
- **与周边交互**：方向词既是 exits mapping 的键、又是门的方向键（§2）、又是 `valid_leave(me, dir)` 的参数、又是 `follow_me(me, dir)` 的跟随参数（§5）。方向词是贯穿「出口/门/导航/跟随」四子系统的共享键空间。

### 1.4 跨区连接（官道）

- **LPC 出处**：`d/*/road*.c` 与 `*road*.c` 遍布各区（如 `d/village/hsroad1-3.c`、`d/foshan/road1-4.c`、`d/hangzhou/road11/33/61/77.c` 等）。
- **机制**：官道房间就是普通 ROOM，无特殊继承；跨区靠 exits mapping 引用绝对路径实现「无缝」连接（非传送门，是步行可达）。例：`d/village/hsroad3.c`：`"north" : __DIR__"sexit"`（华山村南村口）、`"south" : "/d/emei/emroad6"`（峨嵋官道）。
- **官道的额外逻辑**：官道房间常带 `init()` 随机遇匪/劫镖（`hsroad3.c` line 27-47：检测玩家携带高价值物品 `value>=10000` 或 `biao/ma` 任务，random 触发 `new(__DIR__"npc/caokou")` 草寇拦路，并在 `valid_leave` 阻止离开）。这是「跨区移动=风险走廊」的玩法模式，非通用机制。
- **与周边交互**：官道 `outdoors` 标志 = 区域标签（`hsroad3` 为 `"wudang"`，虽在 village 目录下）；`cost` 通常为 1（最低消耗）。

---

## 2. 门（状态机）

### 2.1 状态常量

- **LPC 出处**：`include/room.h`。
- **数据结构**：位掩码常量：`DOOR_CLOSED=1`、`DOOR_LOCKED=2`、`DOOR_SMASHED=4`。门的 `status` 字段是这些位的或组合（如 `CLOSED|LOCKED=3`）。注意：`DOOR_LOCKED`/`DOOR_SMASHED` 有常量但 room.c 的门逻辑只对 `DOOR_CLOSED` 做开关，锁/破坏是预留位（room.c line 272 注释 `// if ( door[dir]["status"] & DOOR_HAS_TRAP ) ....` 显示陷阱位也曾预留）。

### 2.2 门数据结构

- **LPC 出处**：`inherit/room/room.c` `create_door()`（line 227-257）+ `static mapping doors`（line 15）。
- **数据结构**：`doors` 是 `mapping`，键=方向词，值=门 mapping `([ "name":..., "id":({dir, name, "door"}), "other_side_dir":..., "status":... ])`。
- **触发条件**：房间 `create()` 里调用 `create_door(dir, data, other_side_dir, status)` 建门。例：`d/huashan/nushi.c` line 25-26：`create_door("north","木门","south",DOOR_CLOSED)` 与 `create_door("east","竹门","west",DOOR_CLOSED)`（nushi↔zoulang5 之间、nushi↔liangong2 之间各一道门）。
- **建门流程**（room.c line 227-257）：
  1. 校验 exits[dir] 存在（无出口不能建门，否则 `error`）。
  2. 紧凑模式（data 是字符串）：构造 `{name, id=[dir,name,"door"], other_side_dir, status}`；映射模式（data 是 mapping）直接用。
  3. 注册 `item_desc/<dir>` → `(: look_door, dir :)` 回调（`look <方向>` 时显示门状态）。
  4. 若对侧房间已加载，调用 `ob->check_door(other_side_dir, d)` 做双向状态同步（line 250-253）。
  5. 写入 `doors[dir] = d`。

### 2.3 门的状态机（开关/锁/方向对侧）

- **`look_door(dir)`**（room.c line 158-166）：根据 `status & DOOR_CLOSED` 返回「这个X是关着的/开着的」。
- **`open_door(dir, from_other_side)`**（room.c line 168-191）：
  - 校验门存在且当前关闭。
  - `from_other_side=1`（对侧发起）：本侧只清 `DOOR_CLOSED` 位 + 广播「有人从另一边将X打开」。
  - `from_other_side=0`（本侧发起）：先找对侧房间 `find_object(exits[dir])`，调 `ob->open_door(other_side_dir, 1)` 让对侧也开；成功后本侧清位。
  - 位操作：`doors[dir]["status"] &= (!DOOR_CLOSED)`（清关闭位）。
- **`close_door(dir, from_other_side)`**（room.c line 193-216）：对称地置 `DOOR_CLOSED` 位，`status |= DOOR_CLOSED`，同样做对侧传播。
- **`check_door(dir, door)`**（room.c line 218-225）：被对侧调用，把对侧的 status 拷到本侧（`door["status"] = doors[dir]["status"]`），实现双向状态一致性。无对侧门时默认返回 1（假设正确）。
- **`query_doors()`/`query_door(dir, prop)`**（line 259-265）：查询接口，供 look 等使用。
- **触发条件**：门开关由 `open`/`close` 命令触发（未在本次读取的文件中，但 room.c 暴露了 `open_door`/`close_door` 接口）。`look` 命令枚举出口时调用 `query_door(dirs[i], "status")` 检查 `DOOR_CLOSED`，关闭的门方向不出现在出口列表（`look.c` line 48-61）。
- **与周边交互**：
  - `valid_leave`（room.c line 267-275）：离开方向若有关闭的门，`notify_fail("你必须先把X打开！")` 阻止移动。
  - 门与出口强绑定：建门必须有 exit；开关门做对侧房间传播，要求对侧房间可加载/已加载。
  - `item_desc` 回调使 `look <方向>` 走 `look_door`（room.c line 248）。

---

## 3. 导航（valid_leave + 移动消耗 cost + 负重限制）

### 3.1 valid_leave 离开闸门

- **LPC 出处**：`inherit/room/room.c` `valid_leave(object me, string dir)`（line 267-275）；各房间可 override。
- **基础实现**：方向上有门且 `DOOR_CLOSED` → 阻止；否则放行。
- **房间级 override 模式**（从样本归纳）：
  - **任务闸门**：`d/village/sexit.c` line 40-46：`dir=="south" && me->query_condition("hz_job")` → 阻止离开（巡山任务期间不能离岗）。
  - **战斗/劫持闸门**：`d/village/hsroad3.c` line 49-57：`biao/li` 或 `rob_victim` 且场上有草寇 → 阻止离开。
  - **携带物闸门**：`d/huashan/nushi.c` line 32-47：朝 east/north 离开时若身上有其他 character → 阻止（休息室不能带人走）。
  - **载具下船触发**：`inherit/room/ship.c` line 55-71：`dir=="out"` 且船上无其他玩家时，`call_out("do_ready", 5)` 触发船离岸（最后一人下船即开走）。
- **触发条件**：`go.c` line 85：移动前 `env->valid_leave(me, arg)`，返回 0 则移动中止。
- **与周边交互**：valid_leave 是「房间级策略钩子」，挂在出口上；与门状态（§2）、任务系统、战斗系统、载具周期（§6/§7）耦合。`new_valid_dest` 临时变量（go.c line 87-93）允许 valid_leave 逻辑改写真实目的地（传送/重定向机制）。

### 3.2 移动消耗 cost（体力 jingli）

- **LPC 出处**：房间 `set("cost", N)`；`cmds/std/go.c` line 223-236 消费。
- **数据结构**：cost 是每房间的整数体力消耗基数。
- **消费规则**（go.c）：
  - 人类步行：`me->add("jingli", - env->query("cost")*2)`（line 229）；`jingli<=0` → `unconcious()`（line 230）。
  - 骑乘：马匹 `rided->add("jingli", - cost*2)`（line 226）+ 骑手 `random(5)==0` 时 `me->add("jingli",-2)`（line 225，1/5 概率骑手也损耗 2）；马 `jingli<=0` → `unconcious()`（line 227）。
  - 非人类（家畜/野兽自行移动）：`me->add("jingli", - cost*2)`（line 234）。
- **门槛**（go.c line 72-73）：`me->query("jingli") < me->query("max_jingli")/10` → 「精疲力尽，动弹不得」，移动前即拒绝。
- **骑乘能力闸门**（go.c line 118-119）：`obj->query("cost") > rided->query("ability")` → 马匹能力不足以进入该房间（cost 越高地形越难行）。`ability` 是马匹属性（baima.c `set("ability",4)`）。
- **与周边交互**：cost 耦合到 jingli（精力）属性；jingli 同时被战斗/练功等其他系统消费；耗尽触发 `unconcious()`（昏迷系统，进入 §5 马匹昏厥、§7 船难落水）。

### 3.3 负重限制（encumbrance）

- **LPC 出处**：`feature/move.c`（weight/encumb 模型，line 8-45）+ `cmds/std/go.c` line 49-50。
- **数据结构**：
  - `weight`：物体自身重量（`set_weight(w)`）。
  - `encumb`：所携带物体的累计重量（`add_encumbrance(w)` 累加）。
  - `max_encumb`：最大负重（`set_max_encumbrance(e)`）。
  - `weight()`（line 45）：返回 `weight + encumb`（总重量，用于移动时负重检查）。
- **房间负重上限**：`inherit/room/room.c` line 17：`query_max_encumbrance() { return 100000000000; }`（房间容量极大，实际不限制）。
- **触发条件**：
  - 移动前：`go.c` line 49：`me->over_encumbranced()` → 「负荷过重，动弹不得」。
  - 移入时：`move.c` line 76-82：`ob->query_encumbrance() + weight() > ob->query_max_encumbrance()` → 「X 对你/它而言太重了」。**例外**：若目标 ob 是当前对象的祖先环境（如从背包取物），跳过检查（line 74-75，因为能背背包就能背里面的东西）。
- **负重的环境传播**：`add_encumbrance(w)`（move.c line 16-23）：累加后若超上限调 `over_encumbrance()`（仅对 interactive 提示，line 25-29），并 `environment()->add_encumbrance(w)` 向上传播（容器嵌套时父容器也增重）。
- **与周边交互**：负重的环境传播使「房间→玩家→背包→物品」形成重量链；`set_weight` 改变时同步更新环境负重（move.c line 32-40）。

---

## 4. 移动机制（move 调用链）

- **LPC 出处**：`feature/move.c` `varargs int move(mixed dest, int silently)`（line 47-121）。
- **调用链**（按顺序）：
  1. **卸装备**（line 55-56）：若 `query("equipped")` 且 `unequip()` 失败 → 拒绝移动（「没有办法取下这样东西」）。装备中的物品不能直接 move。
  2. **解析目标**（line 59-66）：dest 是 object 直接用；是 string 则 `call_other(dest, "???")` 触发加载 + `find_object(dest)`；解析失败拒绝。
  3. **负重检查**（line 74-82）：若目标不是当前对象的祖先环境，做负重上限检查（见 §3.3）。
  4. **更新负重账本**（line 85-86）：旧环境 `add_encumbrance(-weight())`、新环境 `add_encumbrance(weight())`。
  5. **执行迁移**（line 87）：`move_object(ob)`（driver 内置，实际改变 environment）。
  6. **迁移后健壮性检查**（line 89-96）：`move_object` 后 `this_object()` 可能在 destruct 中被销毁，或被移到别处（日志 `move.bug`）。
  7. **到达后自动 look**（line 99-118）：若 `interactive` + `living` + `!silently`：
     - `env/brief` 模式：构造 `short + "\n" + 房间内可见对象 short 列表`（跳过自己与不可见对象）。
     - 否则：`command("look")`（触发 look.c 完整渲染，含 outdoor 描述 §10、出口列表 §2.3、门状态）。
- **相关方法**：
  - `remove(euid)`（line 123-146）：destruct 时回调，卸装备 + 环境负重 `-weight`；限制非 ROOT_UID 销毁 user 对象（安全）。
  - `move_or_destruct(dest)`（line 148-154）：紧急重定位，user 被移到 `VOID_OB`（「一阵时空的扭曲将你传送到另一个地方」）。
- **触发条件**：被 `go.c` line 238 `me->move(obj)` 调用；也被 `make_inventory`（room.c line 66，NPC 生成入房）、`return_home`（NPC 回巢）、载具 `move`（渡船/船把玩家 move）等调用。
- **与周边交互**：
  - **silently 参数**：渡船 `auto_clean_up`/`do_drop` 等场景 move 玩家时常需控制是否触发 look（载具内迁移）。
  - **go.c 的 move 后处理**（line 239-258）：`remove_all_enemy()`（脱离战斗）、`follow_me(me, arg)`（触发跟随者 §5）、清理失效的 `rided`/`rider` 关系（不同步则删除）、清理 `exit_blockers`（拦路解除）。
  - **move 与负重链**：move 是负重账本更新的唯一入口（§3.3）。

---

## 5. 坐骑（mounts）

### 5.1 rider/rided 关系

- **LPC 出处**：`cmds/std/ride.c`、`cmds/std/unride.c`（与 `cmds/std/xia.c` 内容相同，疑似重复文件）、`clone/horse/*.c`。
- **数据结构**：双向引用，存在玩家与马匹各自身上：
  - 玩家：`me->set("rided", ob)`（我骑的马）。
  - 马匹：`ob->set("rider", me)`（骑我的人）。
  - 马匹同时 `ob->set_leader(me)`（跟随主人，见 §5.3）。
- **骑乘前置条件**（ride.c line 12-44）：
  - 目标在场（`present(arg, environment(me))`）。
  - 玩家不忙（`!me->query_busy()`）。
  - 目标是 character 且 `race != "人类"`（只能骑非人）。
  - 目标 `query("ridable")` 为真（马匹 `set("ridable",1)`，baima.c line 24）。
  - 目标活着（`living(ob)`）。
  - **所有权**：`ob->query_lord() == me`（必须是马的主人；主人由驯服 `train_it` 获得，见 trainee.c）。
  - 马匹当前无骑手或骑手就是自己；玩家当前未骑。
- **触发条件**：`ride|qi <动物>` 命令。`unride|buqi <动物>` 解除（unride.c：delete rided/rider）。
- **关系失效清理**：`go.c` line 245-253：每次移动后检查 `rided`/`rider` 是否仍在同一环境，不在则 delete（骑手与马分离后关系自动断）。

### 5.2 jingli 体力衰减与昏厥坠骑

- **LPC 出处**：`clone/horse/horse.h` `condition_check()`（line 7-41）。
- **触发机制**：`condition_check` 注册为 NPC 的 `chat_msg` 条目（`baima.c` line 34-37：`set("chat_chance",50)` + `set("chat_msg",({ (: condition_check :) }))`）。`chat()` 调度器在 `inherit/char/npc.c` line 99-130：按 `chat_chance` 概率（百分比/回合）随机执行一条 chat_msg（可为函数指针）。**这是马匹体力的自动周期检查，非定时 call_out，而是挂在 NPC 心跳上的概率触发。**
- **状态/阈值**（horse.h）：
  - `my_jingli <= 10`（line 18-30）：**昏厥坠骑**。骑手 `delete("rided")`、`receive_wound("qi",150,...)`（跌伤 150 气）、马 `delete("rider")`、`set_leader(0)`（停止跟随）、马 `unconcious()`。
  - `my_jingli <= 30 && > 20`（line 32-35）：「只在喘气，渐渐地快跑不动了」（警告，未坠骑）。
  - `my_jingli <= max_jingli/3`（line 37-40）：「大口大口地喘着粗气」（早期警告）。
- **移动中的损耗**（go.c line 223-231，§3.2）：骑乘移动时马 `jingli -= cost*2`，马 `jingli<=0` 直接 `unconcious()`（不同于 condition_check 的 10 阈值，这里是 0 阈值，移动场景更宽容）。
- **马匹吃草回血**（horse.h init()，line 42-65）：马在 `query("resource/grass")` 为真的房间（如 `d/city/beijiao4.c`、`d/city/nanjiao4.c`、`d/xixia/hytan.c` 等城郊草地）且未吃饱时，`add("food", max_food/4)` + `add("jingli", (max_jingli-jingli)/2)`（回复一半缺口）。
- **与周边交互**：jingli 是马匹与玩家共用的精力属性；坠骑触发 `receive_wound`（受伤系统）+ `unconcious`（昏迷系统）；`resource/grass` 是房间级资源标志（与 `resource/water` cabin1.c 同类）。

### 5.3 set_leader 跟随

- **LPC 出处**：`feature/team.c`（`set_leader`/`follow_me`/`follow_path`，line 10-49）。
- **数据结构**：`static object leader`（跟随目标）；`team` 数组（组队成员）。
- **跟随触发**（follow_me，line 37-49）：当 leader 移动时，`go.c` line 243 `all_inventory(env)->follow_me(me, arg)` 遍历同房间所有对象调用。
  - 条件：`living(this_object())` 且 `ob==leader`（或 `pursuer` 且在追杀 ob）。
  - **逃脱判定**：`random(ob->query_skill("move")) > this_object()->query_skill("move")` → 跟随者 move 技能低于 leader 时，`call_out("follow_path",1,dir)` 延迟跟随（可能跟丢）；否则立即 `follow_path(dir)`。
  - `follow_path(dir)`（line 28-35）：`remove_all_enemy()` + `GO_CMD->main(this_object(), dir)`（复用 go 命令移动）。
- **马匹跟随**：`ride.c` line 35 `ob->set_leader(me)` 使马跟随骑手；`unride` 后马仍可能跟随（直到 `set_leader(0)`）；马昏厥时 `horse.h` line 27 `set_leader(0)` 解除跟随。
- **驯兽跟随**（trainee.c line 72-75）：`train_it` 成功驯服后若 `auto_follow` 为真，`set_leader(ob)` 自动跟随。
- **跟随命令**：`gen|come <目标>`（trainee.c do_gen line 80-104、horse.h 同名）让驯服的动物跟随；`ting|stay`（trainee.c do_ting line 197-208）`set_leader(0)` 停止跟随；`fang|release`（do_fang line 210-225）解除主从关系。
- **与周边交互**：跟随复用 go 命令，因此跟随者同样受 `valid_leave`/`cost`/门/负重 约束；`move` 技能是逃脱判定的比较量；team（组队）是更高级的多对象跟随结构（`add_team_member`/`join_team`/`dismiss_team`，team.c line 51-122）。

---

## 6. 渡船周期（ferry 状态机）

### 6.1 通用渡口（inherit/room/ferry.c）

- **LPC 出处**：`inherit/room/ferry.c`（157 行）。
- **数据结构**：渡口房间设置：
  - `set("boat", <渡船对象路径>)`：绑定的渡船。
  - `set("opposite", <对岸房间路径>)`：目的地岸。
  - `set("name", ...)`：水域名（如「太湖面」）。
- **状态机**（call_out 驱动）：
  1. **`do_yell("船家")`**（line 28-53）→ **`check_trigger()`**（line 55-91）：
     - 若 `exits/enter` 已存在（船已靠岸）：「正等着你呢，上来吧」。
     - 否则 load boat，设 `boat->set("yell_trigger",1)`、`this->set("exits/enter", boat)`、`boat->set("exits/out", this)`（双向出口接通）。广播靠岸消息。`call_out("on_board", 15)`。
  2. **`on_board()`**（line 93-112，+15s）：「竹篙一点，扁舟向心驶去」。`boat->delete("exits/out")`、`this->delete("exits/enter")`（撤出口，乘客已在船上）。`call_out("arrive", 20)`。
  3. **`arrive()`**（line 114-139，+20s）：`boat->set("exits/out", opposite)`（船的出口接到对岸）。`call_out("close_passage", 20)`。
  4. **`close_passage()`**（line 141-157，+20s）：`boat->delete("exits/out")`、`boat->delete("yell_trigger")`（船离开对岸，周期结束）。
- **触发条件**：玩家在渡口房间 `yell 船家`。整个周期 15+20+20=55s 由 call_out 串行驱动。
- **与周边交互**：靠岸期间通过动态增删 `exits/enter`（岸→船）与 `exits/out`（船→岸）实现「船是可进可出的临时房间」；玩家 `go enter` 上船、`go out` 下船。对岸不自动接通（ferry.c 的 arrive 注释掉了对岸同步逻辑，line 126-135）。

### 6.2 太湖变体（d/taihu/ferry.h + duchuan2.c）

- **LPC 出处**：`d/taihu/ferry.h`（被 `d/taihu/taihu2.c` 等 `#include`）+ `d/taihu/duchuan2.c`（渡船对象）。
- **与通用 ferry.c 的差异**：
  - **昼夜门禁**：`check_trigger()` 检查 `day_event() == "event_midnight"` → 「夜色已深，船家歇息」（ferry.h line 41-45）。耦合 Nature 时段（§8）。
  - **门派限制**：`family_name != "桃花岛"` → 「船家来来往往，一无反应」（line 47-50）。
  - **动态克隆船**：`room = new(myboat)` 每次喊船新建一艘（而非复用单例），`exits/enter = file_name(room)`。
  - **船对象自管理周期**：`duchuan2.c` 的 `arriving()`（line 116-123）→ `call_out("arrive",20)` → `auto_clean_up()`（line 74-114，把乘客赶下船后 destruct 船）。
  - **`do_anchor|tingbo`**（duchuan2.c line 155-185）：玩家可催船靠岸，按 `sail_time` 经过时长决定船夫答复（<10s「才刚离岸」、<30s「就快到了」、否则靠岸）。
  - **昼夜描述**：`look_lake()`（line 41-62）按 `day_event()` 返回不同湖景文案。
- **与周边交互**：太湖变体把渡船周期与 Nature 时段（§8）、门派系统、船对象生命周期（自动 destruct）耦合，比通用 ferry.c 更复杂。

---

## 7. 船只导航（ship.c 海船状态机）

### 7.1 两层架构：港口 + 海船

- **港口层**（`inherit/room/harbor.c`）：
  - `do_yell("chuan")`（line 35-94）：找一艘空闲 seaboat（`/clone/ship/seaboat1-3`，遍历找 `!query_temp("trigger")` 的船），设 `harbor->set("exits/enter"+i, ship)`、`ship->set("exits/out", harbor)`。`call_out("do_ready", 20, ship)`。
  - **登船收费**（harbor.c valid_leave line 96-112）：`dir` 以 "enter" 开头且本港 `navigate/locx` 为 0（大陆港口）→ 收 1000 文；荒岛（`wildharbors`）不收也不让喊船。
  - `do_ready(ship)`（line 114-152）：20s 后把船上玩家踢下船、清出口、船离岸。
- **海船层**（`inherit/room/ship.c` 591 行）：玩家上船后用 `start/go/stop/lookout/locate` 操船航海。

### 7.2 海图坐标系统

- **LPC 出处**：`clone/ship/harbor.h`（港口/岛屿坐标）+ `clone/ship/seashape.h`（暗礁坐标）+ 港口房间 `set("navigate/locx"/"locy")`。
- **数据结构**：
  - `locx`：东西轴，+ 东 - 西。大陆港口 `locx=0`（如 `d/beijing/tanggu.c` set navigate/locx=0,locy=0）；岛屿 `locx>0`。
  - `locy`：南北轴，+ 北 - 南。
  - `harbors` mapping（harbor.h）：大陆港口路径 → locy（`beijing/tanggu:0`、`jiaxing/zhoushan:-200`、`quanzhou/yongning:-280`、`quanzhou/anhai:-300`）。
  - `islands` mapping：岛屿路径 → `({locx, locy})`（`shenlong/beach:{30,20}`、`island/icefire1:{100,600}`、`taohua/haitan:{20,-210}`）。
  - `jiaos` 数组（seashape.h）：10 个暗礁坐标 `({x,y})`。
  - `wildharbors` 数组：荒岛路径（`/d/island/icefire1`），玩家无法喊船，可派人守船。

### 7.3 船只导航状态机

- **LPC 出处**：`inherit/room/ship.c`。
- **指令**（init line 38-47）：`start`/`go <e/s/w/n>`/`stop`/`lookout`/`locate`。
- **`do_start()`**（line 73-110）：
  - 前置：船上无「主人」（`is_owner` = 战斗经验高于发起者的其他玩家，line 475-482，防止抢船）；船已靠岸（`exits/out` 存在）。
  - 读港口 `navigate/locx/locy` 作为起点；`delete("exits/out")`（离岸）；`delete_temp("navigate")`；`call_out("shipweather",1)` + `call_out("navigate",2)`。
- **`navigate()`**（line 112-282，每 2s 一次）：
  1. **触礁检查**（line 126-133）：当前位置 `±1` 命中 `jiaos[]` 任一坐标 → `do_drop()`（沉船）。
  2. **风暴沉船**（line 135-141）：`!random(100)`（1%）且 `navigate/weather==2`（暴风）且远离岸（`locx>50||locy>50`）→ 沉船。
  3. **随机海事件**（line 143-183，`!random(40)`=1/40）：海怪/财宝/海盗/神迹/幽灵船(Titanic)/火鸟/海妖歌声/海中巨眼/美人鱼/极光。
  4. **无人值守超时**（line 185-197）：无 `navigate/dir` 时 `!random(100)` 累计 `navigate/wait`，>5 则「船夫把大家扔进海里」沉船。
  5. **移动**（line 202-218）：按 `navigate/dir`（东/南/西/北）增减 locx/locy。
  6. **靠岸判定**（line 223-275）：
     - `locx<1`：到大陆，按 locy 匹配 `harbors` mapping；匹配不到→「漂到荒岛」继续漂；匹配到→设 `exits/out`=港口、`call_out("do_ready",20)`、港口设 `exits/enterN`=船。
     - 否则匹配 `islands` mapping（locx,locy 精确匹配）→ 靠岛。
     - 都不匹配→`call_out("navigate",2)` 继续。
- **`do_go(arg)`**（line 284-321）：解析 `e/s/w/n` → 设 `navigate/dir`（中文方向）。`do_stop()`（line 323-339）清 `navigate/dir`。
- **`do_lookout()`**（line 341-421）：瞭望。算最近岛屿距离（欧氏距离平方），>72「大海茫茫」；≤72 按 locx/locy 相对位置给八方位（东/西/南/北/东北/西北/东南/西南，6 格内）+ 岛屿 shape 描述。
- **`do_locate()`**（line 423-473）：定位。算最近大陆港口距离；非巫师坐标被模糊化（`locx*9/10 + random(2*locx)/10`，line 448-449）；输出「东约X海哩北约Y海哩」格式的相对位置。
- **`shipweather()`**（line 484-505）+ **`niceweather()`**（line 507-511）：独立局部天气。`!random(6)`→weather=1（阴）、`!random(24)`→weather=2（暴）；`niceweather` 复位为 0。影响 `long_desc`（line 30-34，阴/暴/平静三态描述）与沉船概率。
- **`do_drop()`**（line 513-537）：沉船善后。玩家 `unconcious()`、销毁身上物品（除 `tie lian` 铁链）、随机传送到某大陆港口、广播「被海水冲上岸」。
- **`time_out()`**（line 49-53）：`init` 时 `call_out("time_out", 900+random(500))`，超时（约 15-23 分钟无人操作）→「狂风大作船翻了」沉船。
- **`do_ready()`**（line 539-590）：靠岸后 20s 自动开船离岸，把残留玩家踢下船；荒岛额外等 100s。
- **触发条件**：玩家上船后手动操船；导航循环由 call_out 每 2s 自驱动。
- **与周边交互**：船是 ROOM（`inherit ROOM`，ship.c line 7）也是移动载具；`exits/out` 动态指向当前靠岸港口；`exits/down` 指向船舱（`cabin1-3.c`，可睡觉/取水/吃东西）；`is_owner` 耦合战斗经验（ PvP 抢船）；沉船耦合 `unconcious`/`receive_wound`/物品销毁。**shipweather 与全局 Nature 天气无关**（§9）。

---

## 8. 昼夜时段（day_phase 循环）

### 8.1 时段数据

- **LPC 出处**：`adm/etc/nature/day_phase`（数据文件）+ `adm/daemons/natured.c`（驱动）。
- **数据结构**（每段 4 字段，day_phase 文件 line 20-21 定义格式 `length:time_msg:desc_msg:event_fun`）：
  | 时段 | length(分钟) | time_msg(开始广播) | desc_msg(期间 look) | event_fun |
  |------|----|----|----|----|
  | dawn | 240 | 东方微曦 | 东方天空已逐渐发白 | event_dawn |
  | sunrise | 120 | 太阳升起 | 太阳刚从东方升起 | event_sunrise |
  | morning | 180 | 太阳高挂东方 | 太阳正高挂在东方 | event_morning |
  | noon | 180 | 正午 | 太阳高挂在头顶正上方 | event_noon |
  | afternoon | 180 | 太阳西沉 | 太阳正高挂在西方 | event_afternoon |
  | evening | 180 | 傍晚余晖火红 | 火红夕阳徘徊西方地平线 | event_evening |
  | night | 120 | 夜晚降临 | 夜幕笼罩大地 | event_night |
  | midnight | 240 | 已经是午夜 | 夜幕低垂，满天繁星 | event_midnight |
  - 总长 240+120+180+180+180+180+120+240 = 1440 分钟 = 24 小时。
- **时间比例**：`natured.c` line 46-48 注释：1 游戏分钟 == 1 现实秒（`TIME_TICK = time()*60`，line 6）。即游戏内一天 = 现实 1440 秒 = 24 分钟现实时间。

### 8.2 循环驱动

- **LPC 出处**：`natured.c` `init_day_phase()`（line 28-52）+ `update_day_phase()`（line 54-77）。
- **`init_day_phase()`**（启动时）：
  - `localtime(TIME_TICK)` 取当前现实时间换算的游戏时分（line 34）。
  - 遍历 day_phase 减去各段 length，定位当前段 `current_day_phase`（line 38-44）。
  - `call_out("update_day_phase", 下一段剩余 length - t)` 调度首次切换（line 50-51）。
- **`update_day_phase()`**（每次切换）：
  - `remove_call_out` 清旧调度（line 58）。
  - `current_day_phase = (++current_day_phase) % sizeof(day_phase)`（line 66）推进；每轮回到 0 时重新 `init_day_phase()` 同步时间（line 60-64，`synchronize=1`）。
  - `call_out("update_day_phase", day_phase[current_day_phase]["length"])` 调度下一段（line 69）。
  - **广播**（line 71）：`message("outdoor:vision", time_msg+"\n", users())` —— 向所有玩家广播时段开始消息，但只有户外玩家实际收到（§10）。
  - **event_fun 回调**（line 72-73）：`call_other(this_object(), event_fun)`。
  - **event_common**（line 75）：每次切换都调用。

### 8.3 event_fun 回调实现现状

- **LPC 出处**：`natured.c`。
- **已实现**（仅 2 个）：
  - `event_sunrise()`（line 83-97）：日出时自动存盘——遍历 `users()`，对每个玩家 `link_ob->save()` + `ob->save()`。注释提到曾用于 mudlist。
  - `event_common()`（line 100-142）：每次切换调用。① 遍历 `livings()` 清理无 environment 的对象（NPC destruct、玩家 move 到 `/d/city/wumiao.c` 武庙）；② 遍历 `users()` 调 `UPDATE_D->inventory_check(ob[i])`（`adm/daemons/updated.c`）做玩家物品检查。注意：用 `random(sizeof(ob))` 选起点但 `count=sizeof(ob)` 全量轮询。
- **未实现（空调用）**：`event_dawn`/`event_morning`/`event_noon`/`event_afternoon`/`event_evening`/`event_night`/`event_midnight` 共 7 个在 day_phase 数据里声明了 event_fun，但 natured.c 未定义对应函数——`call_other` 调用不存在的函数在 LPC 里是 no-op（返回 0）。**这意味着除 sunrise 存盘外，时段切换无其他游戏效果触发。**
- **查询接口**：
  - `outdoor_room_description()`（line 144-147）：返回当前段 `desc_msg`，供 `look` 命令拼户外描述（look.c line 46）。
  - `outdoor_room_event()`（line 149-152）：返回当前段 event_fun 名（字符串），供其他模块查询当前时段——`go.c` line 36/101-103 用它判断 `event_night`/`event_midnight` 关闭 day_shop 商店；`d/taihu/ferry.h` 与 `duchuan2.c` 用它做昼夜门禁与湖景描述。
- **与周边交互**：
  - **day_shop**：`go.c` line 101-103：目标房间若 `day_shop` 标志为真且当前为 night/midnight → 「晚上不开，请天亮了再来」。时段耦合商店营业。
  - **渡船门禁**：太湖渡船夜间停运（§6.2）。
  - **户外描述**：look 自动附加当前时段 desc（§10）。
  - **自动存盘**：sunrise 触发全服存盘。

---

## 9. 天气

### 9.1 全局天气：僵尸代码

- **LPC 出处**：`adm/daemons/natured.c` line 11-17（`weather_msg` 数组）+ `feature/message.c` line 31-34（`weather:` 子类过滤）。
- **证据**：
  - `weather_msg` 5 档数组在 natured.c line 11 定义（「万里无云/几朵淡云/白云飘来飘去/厚厚云层/乌云密布」）。
  - 全仓库 grep `weather_msg`：**仅 natured.c line 11 这一处定义，无任何引用**（无 `weather_msg[i]` 取值、无广播）。
  - `message.c` line 31-34 留了 `weather:` 消息子类分支（`if( !environment() || !environment()->query("weather") ) return;`），但全仓库 grep `set("weather"` 在 `d/` 下**无任何房间设置 weather 标志**，也无任何代码 `message("weather:...")` 广播。
- **结论**：**LPC 的全局天气系统从未上线**。`weather_msg` 数组与 `weather:` 消息通道是预留但未接通的半成品。Nature 实际只驱动「昼夜时段」，不驱动「天气变化」。
- **风险警示**：新引擎若要实现「天气影响」需从零设计；LPC 这里的天气数据结构（5 档文案数组）可作灵感，但无运行时机制可参考。

### 9.2 船只局部天气（shipweather）

- **LPC 出处**：`inherit/room/ship.c` `shipweather()`（line 484-505）+ `niceweather()`（line 507-511）。
- **状态/数据结构**：`navigate/weather` 临时变量，三态：`0`（平静）/`1`（阴，彤云）/`2`（暴，巨浪）。
- **触发条件**：`do_start` 后 `call_out("shipweather",1)` 启动；每 1s 检查：`!random(6)`→置 1、`!random(24)`→置 2（暴风更稀有）；置非 0 后 `call_out("niceweather", 5+random(10))` 延时复位为 0。
- **影响**：
  - `long_desc`（line 30-34）：三态不同的海面描述（阴/暴/平静）。
  - 沉船概率（§7.3 navigate line 135-141）：暴风+远离岸+1% → 沉船。
- **与周边交互**：**与全局 Nature 天气无任何耦合**，是 ship.c 内独立的局部随机天气。可视为「载具局部环境状态」的范例。

---

## 10. 户外广播

### 10.1 outdoors 标志

- **LPC 出处**：房间 `set("outdoors", <字符串标签>)`；消费方 `feature/message.c` line 27-29、`cmds/std/look.c` line 46、`cmds/std/go.c` line 116/121/147、`cmds/std/trap.c` line 77/92。
- **数据结构**：`outdoors` 的值是字符串（如 `"xxx"`、`"village"`、`"wudang"`、`"guiyun"`、`"shaolin"`、`"shenlong"`）。
- **关键发现**：**引擎层只消费其布尔真假**。所有消费点都是 `query("outdoors")` 作真值判断，无一处取其字符串值做区域区分。标签（如 `"village"`）是区域/音效元数据，不被通用机制消费（可能是给客户端音效或区域归属用的，但 LPC 源码中无通用消费代码）。
- **outdoors 的语义作用**：
  - 是否接收户外时段广播（§10.2）。
  - look 时是否附加 `outdoor_room_description()`（look.c line 46）。
  - 移动消息文案差异（go.c line 147-156：户外「急步往X离开」/「快步走了过来」vs 室内「往X走了出去」/「走了过来」；骑乘户外「飞驰而去」/「奔驰过来」）。
  - 骑乘准入（go.c line 116-119：马匹不能进入 `!outdoors` 房间）。
  - 陷阱布置限制（trap.c：非户外不能设陷阱）。

### 10.2 outdoor:vision 消息通道

- **LPC 出处**：`adm/daemons/natured.c` line 71（广播方）+ `feature/message.c` line 11-54（消费方 receive_message）。
- **广播**（natured.c update_day_phase line 71）：`message("outdoor:vision", time_msg+"\n", users())`。
  - `users()` 返回所有 interactive 玩家对象数组——**无空间索引，广播给全服所有在线玩家**。
- **消费过滤**（message.c receive_message line 20-38）：
  - `sscanf(msgclass, "%s:%s", subclass, msgclass)` 拆 `outdoor:vision` → subclass=`outdoor`、msgclass=`vision`。
  - `case "outdoor"`（line 27-29）：`if( !environment() || !environment()->query("outdoors") ) return;` —— **玩家当前不在户外房间则丢弃消息**。
  - 即：广播是「全服推送 + 客户端按环境过滤」，非「服务端按空间筛选目标」。每个玩家对象的 receive_message 各自判断自己的 environment 是否户外。
- **其他 outdoor 子类**：`weather:` 子类（line 31-34）同结构但如 §9.1 所述从未被使用。
- **消息缓冲**（message.c line 49-53）：玩家 `in_input`/`in_edit`（正在输入/编辑）时，消息进 `msg_buffer`（上限 500），`write_prompt` 时补发。盲状态（`query_condition("blind")`）有概率丢弃消息（line 43-44）。
- **与周边交互**：outdoor:vision 是 Nature 时段切换触达玩家的唯一通道；与 look 的 `outdoor_room_description`（拉模式）互补——推送给当前户外玩家、拉取给主动 look 的玩家。性能上，每次时段切换向全服 players 各发一条消息，规模 1000 在线时是 1000 次 receive 调用（见性能评审）。

---

## 机制间交互总览（交叉图）

```
                  ┌─────────────────────────────────────────┐
                  │  Nature (natured.c)                      │
                  │  day_phase 8 段循环 (call_out)           │
                  │  event_sunrise: 存盘                     │
                  │  event_common: 清理+inventory_check      │
                  │  outdoor:vision 广播 ────────────────┐   │
                  └──────────┬──────────────────────────┘   │
                             │ event_fun 查询                │
              ┌──────────────┼───────────────┐              │
              ▼              ▼               ▼              ▼
         day_shop 营业   渡船夜间门禁   look 户外描述   户外玩家收到
         (go.c)         (ferry.h)      (look.c)       (message.c 过滤)
                             │
                             │
  ┌──────────────────────────────────────────────────────────┐
  │  移动层 (go.c + move.c)                                  │
  │  go <dir> → valid_leave → cost 扣 jingli → move(dest)    │
  │                ↑                ↑            ↓           │
  │             门状态(§2)      负重(§3.3)   到达后 look      │
  │                                                          │
  │  骑乘: rided/leader → 跟随 follow_me (team.c)            │
  │        马匹 condition_check (chat_chance 概率触发)        │
  │        jingli<=10 坠骑 → unconcious + receive_wound      │
  └──────────────────────────────────────────────────────────┘

  ┌─────────────────────┐  ┌─────────────────────────────────┐
  │  渡船 ferry.c       │  │  海船 ship.c + harbor.c         │
  │  yell→trigger→      │  │  港口 yell→enter1-3              │
  │  board→arrive→close │  │  船上: start/go/stop/lookout/   │
  │  (call_out 串行)    │  │  locate + navigate(call_out 2s) │
  │  exits/enter 动态   │  │  海图 locx/locy + 暗礁/岛屿     │
  │  接通/断开          │  │  shipweather 局部天气(独立)     │
  └─────────────────────┘  │  沉船 do_drop→unconcious        │
                           └─────────────────────────────────┘
```

## 附：数据来源文件清单（证据索引）

| 机制 | 关键 LPC 文件 | 关键函数/对象 |
|------|--------------|--------------|
| 拓扑/出口 | `d/REGIONS.h`、`d/village/alley1.c`、`d/village/hsroad3.c`、`cmds/std/go.c` | `region_names`、`set("exits")`、`default_dirs` |
| 门 | `include/room.h`、`inherit/room/room.c`、`d/huashan/nushi.c` | `DOOR_CLOSED/LOCKED/SMASHED`、`create_door`、`open_door`、`close_door`、`check_door`、`look_door`、`valid_leave` |
| 导航 | `inherit/room/room.c`、`d/village/sexit.c`、`d/village/hsroad3.c`、`cmds/std/go.c` | `valid_leave`、`cost`、`over_encumbranced` |
| 移动 | `feature/move.c`、`cmds/std/go.c` | `move(dest,silently)`、`move_object`、`add_encumbrance`、`weight()`、`remove`、`move_or_destruct` |
| 坐骑 | `clone/horse/horse.h`、`clone/horse/baima.c`、`cmds/std/ride.c`、`cmds/std/unride.c`、`feature/team.c`、`inherit/char/trainee.c`、`inherit/char/npc.c` | `condition_check`、`rider/rided`、`set_leader`、`follow_me`、`follow_path`、`chat`/`chat_chance`、`train_it`、`query_lord`、`resource/grass` |
| 渡船 | `inherit/room/ferry.c`、`d/taihu/ferry.h`、`d/taihu/taihu2.c`、`d/taihu/duchuan2.c` | `do_yell`、`check_trigger`、`on_board`、`arrive`、`close_passage`、`arriving`、`auto_clean_up`、`do_anchor` |
| 船只 | `inherit/room/ship.c`、`inherit/room/harbor.c`、`clone/ship/harbor.h`、`clone/ship/seashape.h`、`clone/ship/seaboat1.c`、`d/beijing/tanggu.c` | `do_start`、`navigate`、`do_go`、`do_stop`、`do_lookout`、`do_locate`、`shipweather`、`niceweather`、`do_drop`、`do_ready`、`time_out`、`is_owner`、`harbors`/`islands`/`jiaos`/`wildharbors` |
| 昼夜时段 | `adm/etc/nature/day_phase`、`adm/daemons/natured.c` | `day_phase[]`、`init_day_phase`、`update_day_phase`、`event_sunrise`、`event_common`、`outdoor_room_description`、`outdoor_room_event`、`TIME_TICK` |
| 天气 | `adm/daemons/natured.c`、`feature/message.c`、`inherit/room/ship.c` | `weather_msg`(僵尸)、`weather:`子类(僵尸)、`shipweather`/`niceweather`(局部) |
| 户外广播 | `feature/message.c`、`cmds/std/look.c`、`cmds/std/go.c`、`cmds/std/trap.c` | `receive_message`、`outdoor:vision`、`query("outdoors")`、`users()` |
