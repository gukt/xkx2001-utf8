# 世界空间层 - 性能与可扩展性评审

> 评审范围：地图拓扑（6414 房间 / 35 区域）+ Nature（昼夜/天气广播）+ 交通（渡船 / 玩家船 / 坐骑）+ call_out 定时器密度 + 持久化 + 现有 engine 模块性能隐患。
> 约束基准：单机 1000 在线 + 100 并发（CLAUDE.md「架构不变量」第 1 条 / ADR-0009 单进程单 World）。
> 证据原则：每条结论标注 LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名。禁止凭空推断。

## 0. 评审结论速览

| 维度 | LPC 原版风险 | engine 现状 | 1000 在线下是否达标 |
|------|--------------|-------------|----------------------|
| 大世界拓扑查询 | 中（call_other + find_object 每次移动加载目标房间） | 中（无 room 索引，entities_in_room 全表扫） | 达标但需建索引；6414 房间常驻内存约 ~30–60 MB，可接受 |
| Nature 全员广播 | **高**（每相位切换 `message("outdoor:vision", msg, users())` 扫全部在线玩家） | 中（`_outdoor_player_ids` 每次 O(N) 全表扫 + 每玩家每文案一次 push） | 8 相位/日 × 户外占比 ~29% ≈ 290 户外玩家 × 每相位 1 次扫描，可接受但**无户内过滤复用** |
| 渡船并发 | 低（call_out + 临时 exit，9 处渡口） | 低（FerryState 纯内存 on_tick 翻转 exit） | 达标 |
| 玩家船 navigate | 中（每 2 秒一次 navigate + 全 islands/harbors 线性扫 + find_object 加载港口） | 未实现 | 原版在 1000 玩家各开船时**每船每 2s 一次 O(islands+harbors) 扫描**，需异步化 |
| call_out 密度 | 低（全局唯一 natured + 9 渡口 + 极少在航船） | 低（单一 on_tick 串行分发） | 达标 |
| 持久化 | **高**（event_sunrise 遍历 users() 同步双存档） | **高**（save_world 全量每实体一文件 JSON + fsync） | 1000 玩家在线时**同步 save 阻塞主循环**，是最大性能隐患 |

---

## 1. 大世界拓扑：6414 房间 / 35 区域的内存与查询开销

### 1.1 规模实测

- 35 区域映射：`d/REGIONS.h`（`region_names` mapping，35 键，含 `beijing` / `dali` / `city` / `shaolin` / `xingxiu` 等）。
- 6414 个 `.c` 房间文件（`find d -name "*.c" -type f | wc -l`）。
- 设 exits 的 3667 间（57%）、设 objects 的 1321 间（20%）、设 outdoors 的 1842 间（29%）、设 create_door 的 75 间（1.2%）。
- 最大区域：`d/dali` 285 文件、`d/shaolin` 188、`d/xingxiu` 170、`d/zhongnan` 152、`d/beijing/zijin` 142（按 `find d -name "*.c"` 分目录计数）。
- 官道（跨区连接）：164 个 `*road*.c`（`find d -name "*road*.c" | wc -l`），分布 `d/hangzhou` 36 / `d/xingxiu` 27 / `d/wudang` 24 / `d/foshan` 18 / `d/village` 12 等。
- 跨区绝对路径出口引用：676 个独立 `/d/<region>/...` 出口串（`grep -rho '"/d/[a-z]*/[a-z_0-9]*"'` 去重计数）。

### 1.2 LPC 原版开销模型

- **房间懒加载**：`move(dest)`（`feature/move.c:47-67`）中 `call_other(dest, "???"); ob = find_object(dest);`——`call_other` 触发目标房间 `.c` 首次加载（`create()` -> `setup()` -> `replace_program(ROOM)`），`find_object` 取已加载对象。**冷启动后玩家首次走某房间的成本 = LPC 编译 + create + make_inventory 全量生成 NPC/物品**（`inherit/room/room.c:52-74 make_inventory`，含 `new(file)` clone NPC）。
- **门的双向 find_object**：`open_door(dir)`（`room.c:185`）`objectp(ob = find_object(exits[dir]))` 跨房间同步开门。`create_door`（`room.c:250`）构造时 `find_object(exits[dir])` 探测对侧是否已加载，若未加载则**不双向同步**（推迟到对侧 create 时 check_door）。门的存储是 `static mapping doors`（`room.c:15`），**不进存档**（`static` 关键字在 LPC 里表示不持久化）。
- **reset 周期重建库存**：`reset()`（`room.c:76-155`）遍历 `query("objects")` + `all_inventory(this_object())`，对 `is_character` 的 NPC 调 `return_home()` 拉回，否则 `destruct`。**每次 reset 是 O(房间 objects + 当前 inventory)**。
- **usr_in() 全树扫**：`room.c:21-29 usr_in()` 用 `deep_inventory(this_object())` 深度遍历容器嵌套判定房间是否有玩家——用于 clean_up 决策，**每次 clean_up 候选判定都是 O(房间内全量物品树)**。

**1000 在线下评估**：
- 内存：6414 房间 × 每房间 short/long/exits/objects/outdoors/cost ≈ 2–8 KB/房间（含 mapping 与 string）→ **总 ~15–50 MB 常驻**，加上 NPC/物品对象图，整体 **~50–150 MB**，单机内存充裕。
- 移动查询：`find_object` 在 LPC driver 里是哈希表查找（O(1)），但首次 `call_other` 编译/执行 `create()` 是 ms 级；1000 玩家分散移动时总体可控，**冷启动后头几分钟集中踩点会触发批量房间加载**。
- **风险点**：`make_inventory` 在 `reset` 时同步 `new(file)` clone NPC，若某房间 objects 列表长（如扬州集市），单房间 reset 会卡主循环；原版无异步 spawn。

### 1.3 engine 现状对照

- 房间无单独 room 索引：`World._components`（`engine/src/openmud/world.py:52`）按组件类型索引，房间查询靠 `entities_with(Description)` / `entities_with(Exits)` 全表扫（`world.py:210-215 entities_with` 用 `set.intersection`）。
- 唯一空间索引：`World.room_ids: dict[str, EntityId]`（`world.py:97`），由 `scene_loader._build_rooms` 填充（`scene_loader.py:129, 469-492`），**仅按 room_key 字符串查 entity id**，无反向（entity id -> room_key）原生索引——`_resolve_ferry_refs` 现场构造 `key_by_id = {eid: key for key, eid in room_ids.items()}`（`scene_loader.py:1402`），**每次加载全表反转一次**。
- 房间内实体遍历：`World.entities_in_room`（`world.py:217-232`）逐个 `entities_with(Position)` 过滤 room 字段，**O(全部 Position 实体)**，无 `room -> [entities]` 反向索引。1000 玩家 + NPC + 物品时，每次 `look` / `go` / 命令解析都触发一次全表扫。
- 出口存储：`Exits.by_direction: dict[str, Exit]`（`components.py:122`），方向字符串 -> Exit.target(EntityId)。查询方向出口是 O(1)，但**解析玩家输入方向时** `directions.merge_exit_match_names` 仍需遍历整个 by_direction（`directions.py` 114 行）。

**engine 性能隐患**：
1. `entities_in_room` 无反向索引——`commands.py`（行 363、1627、1674、1710、1761、1774）、`parsing.py`（615、628、645）、`messaging.py`（62）、`quest.py`（170）、`combat_system.py`（297）、`room_hooks.py`（468、546）、`ai.py`（249）共 15+ 处调用，**每个命令路径至少一次全表扫**。1000 玩家并发时这是 N² 级风险（每玩家每命令 O(N)）。
2. `_resolve_ferry_refs`（`scene_loader.py:1402`）每次加载全量反转 room_ids dict——加载期一次性 O(N)，可接受，但** Ferry 组件本身的 room 互指校验又扫一遍 `entities_with(Ferry)`**（行 1425），两次 O(Ferry 数)。
3. 无 `find_object` 等价物的延迟加载——`scene_loader.load_scene`（`scene_loader.py:81-152`）一次性 `_build_rooms` 全量建 6414 房间，**冷启动加载全图**，与 LPC 懒加载模式相反。MVP 场景清单（华山村 + 扬州子集 + 少林 + 官道）房间数 < 500 暂无压力，但 UGC 题材包做大时**加载时间随房间数线性增长**。

---

## 2. Nature 全员广播开销

### 2.1 LPC 原版广播路径

`adm/daemons/natured.c`：

- 8 时段循环（`adm/etc/nature/day_phase`）：dawn 240 / sunrise 120 / morning 180 / noon 180 / afternoon 180 / evening 180 / night 120 / midnight 240 游戏分钟。1 真实秒 = 1 游戏分钟（`natured.c:6` `#define TIME_TICK (time()*60)` + `init_day_phase` 注释行 47-48）。
- 相位切换分发（`natured.c:54-77 update_day_phase`）：
  1. `message("outdoor:vision", day_phase[current_day_phase]["time_msg"] + "\n", users())`（行 71）——**直接对 `users()` 全体在线玩家发 message**，由 driver 的 `message()` efun 按消息 class `outdoor:vision` 过滤（只投给订阅该 class 的对象，即户外玩家）。
  2. `call_other(this_object(), event_fun)`（行 72-73）触发 `event_sunrise` / `event_noon` 等。
  3. `this_object()->event_common()`（行 75）每个相位都跑。
- `event_sunrise`（`natured.c:83-97`）：**遍历 users()，每个玩家同步 `link_ob->save()` + `ob->save()` 双存档**——每日 sunrise 是全量同步存档点。
- `event_common`（`natured.c:100-142`）：
  1. `ob = livings()`（行 106）——**全部活物**（含 NPC），逐个检查 environment，无 env 的非 user 直接 destruct，user 被强制 move 到 `/d/city/wumiao.c`。这是**全局 O(所有活物)** 扫描。
  2. `ob = users(); count = sizeof(ob); i = random(sizeof(ob)); while (count-- > 0) UPDATE_D->inventory_check(ob[i]); i = (i+1) % sizeof(ob);`（行 132-141）——**从随机起点起，遍历所有玩家做 inventory_check**，每相位切换触发全量库存校验。

**1000 在线下评估**：
- 相位切换频率：8 相位 × 平均 180 游戏分钟 = 每 180 真实秒一次相位切换（约 3 分钟）。每日 8 次。
- 单次切换成本：`message()` 对 1000 玩家发文案——driver 层面 `users()` 是数组，`message(class, msg, targets)` 按 class 过滤，**实际只给户外玩家投递文案**，但**遍历是 1000 人**。文案是单条 string，开销可忽略。
- `event_common` 的 `livings()` 扫描：1000 玩家 + N 个 NPC（NPC 远多于玩家，数千量级）→ 每相位切换 **O(数千)** 次环境检查，每次 `environment()` 是 O(1)，整体 ~ms 级，**可接受**。
- `event_common` 的 `inventory_check` 循环：`count = sizeof(ob)` 即 1000，每相位切换**对 1000 玩家全量 inventory_check**——若 `UPDATE_D->inventory_check` 较重（负重/装备校验），每相位 ~1000 次调用，8 相位/日 = 8000 次/日，**中等开销**。
- **最大风险**：`event_sunrise` 的全量同步双存档——1000 玩家 × 2 次 save = 2000 次磁盘写，**同步阻塞主循环**（见第 5 节持久化）。

### 2.2 engine 现状对照

`engine/src/openmud/nature.py`：

- 相位推进靠 `on_tick`（`nature.py:452-457 _on_tick_nature`），`NatureState.advance_tick`（行 279-318）每 tick 累加 `game_minutes_per_tick`（默认 1），跨相位时收集 `phase_msgs`（行 291-295），分发 `ON_NATURE_CHANGE` 事件（行 306-318）。
- 广播订阅者 `_broadcast_nature_change`（`nature.py:517-535`）：
  1. `_outdoor_player_ids(world)`（`nature.py:502-514`）——**遍历 `entities_with(PlayerSession, Position)` 全表**，对每个玩家 `get_component(room, Description)` 查 outdoors 标记。**O(玩家数) × 每次相位切换**。
  2. 双层循环：`for player_id in outdoor_players: for msg in messages: world.push_message(player_id, msg)`（行 532-535）。
- 与 LPC 差异：LPC 的 `message(class, msg, users())` 把过滤下沉到 driver（按消息 class 投递），engine 是**应用层全扫 + per-player push**。1000 玩家时每相位切换扫 1000 实体 + 最多 push 1000 × 文案数。
- `_outdoor_player_ids` 重复调用问题：每相位切换**只调一次**（在 `_broadcast_nature_change` 入口），但**没有缓存户外玩家集合**——若同一 tick 多个订阅者都要户外玩家列表，会重复扫。目前只有 `_broadcast_nature_change` 一个订阅者，暂无问题。

**engine 性能隐患**：
1. `entities_with(PlayerSession, Position)`（`nature.py:509`）用 `set.intersection`（`world.py:214-215`）——每相位切换构造两个 set 求交，1000 玩家时**临时 set 分配 + 交集计算**，单次 ~ms 级，可接受但**每相位切换都重建**。
2. 天气翻转概率 `DEFAULT_WEATHER_CHANGE_CHANCE = 0.1`（`nature.py:133`）——每 tick 10% 概率翻转天气，触发额外 `ON_NATURE_CHANGE` 分发 + 广播。极端情况下连续 tick 翻转会**每 tick 广播一次**，但默认 1 tick = 1 命令，100 并发下每秒最多 100 次广播扫描，**勉强可接受**。
3. **未实现 LPC `event_common` 的 livings() 清理与 inventory_check**——engine 把「无 environment 的活物清理」推迟到 NPC 子系统（`ai.py`），但**无对应相位切换触发的全量扫描**。这是设计简化，性能上更优，但功能上缺失（无 env 玩家不会被自动 move 到 wumiao）。

---

## 3. 交通并发：渡船 / 玩家船 / 坐骑

### 3.1 渡船（LPC）

`inherit/room/ferry.c`（157 行，9 处渡口实例化：`d/xixia/oldwall.c` / `d/taihu/matou.c,matou2.c` / `d/heimuya/shuitan1.c,shuitan2.c` / `d/shaolin/hanshui1.c,hanshui2.c` / `d/taihu/taihu.c` / `d/xixia/xhbao.c`）：

- 单渡船周期：`do_yell("船家")` -> `check_trigger()`（行 55-91）-> `call_out("on_board", 15)`（行 90）-> `call_out("arrive", 20)`（行 111）-> `call_out("close_passage", 20)`（行 138）。**总周期 ~55 秒，期间动态增删 `exits/enter` 与 `exits/out`**。
- 并发 yell：`room->query("yell_trigger")`（行 74）做互斥——**首个 yell 的玩家触发周期，后续 yell 直接返回 "别急嘛"**。这是乐观锁，无并发风险。
- 状态：`exits/enter` / `exits/out` / `yell_trigger` 都挂在 room 上，**房间对象是单例**，多玩家共享同一渡口实例。无 per-player 状态。
- `find_object(this_object()->query("boat"))`（行 66）加载对岸船房间——**两岸共享同一 boat room 对象**，exit 双向同步。

**1000 在线下评估**：9 个渡口 × 每渡口最多 1 个活跃周期 = 9 个并发 call_out，**完全可忽略**。即使 1000 玩家同时挤在 9 个渡口 yell，`yell_trigger` 互斥保证只有 9 个周期在跑。

### 3.2 玩家船（LPC）

`inherit/room/ship.c`（591 行，3 艘 seaboat：`clone/ship/seaboat1-3.c`）：

- 导航循环：`do_start` -> `call_out("shipweather", 1)` + `call_out("navigate", 2)`（`ship.c:103-106`）。`navigate()`（行 112-282）每 2 秒递归 `call_out("navigate", 2)`（行 195、216、232、279）。
- **每 navigate 周期的开销**：
  1. `for(i = 0; i < sizeof(jiaos); i++)`（行 126）——10 个暗礁点（`clone/ship/seashape.h`），线性扫判定触礁。
  2. `filenames = keys(islands); for(i = 0; i < sizeof(filenames); i++)`（行 254-275）——3 个岛屿港口（`harbor.h` islands mapping 3 键），线性扫判定靠岸。
  3. `find_object(filenames[i])` / `load_object(filenames[i])`（行 236-237、264-265、369-370、415-416、452-453）——**每次靠岸判定都尝试加载港口房间**，已加载则 O(1)，未加载则触发 `create()`。
- `do_lookout`（行 341-421）：`keys(islands)` 遍历 3 岛屿 + `find_object` + 距离判定 + 8 方向枚举——**O(3) + 8 方向分支**，单次 ~ms。
- `do_locate`（行 423-473）：`keys(harbors)` 遍历 4 大陆港口（`harbor.h` harbors mapping 4 键）+ 距离判定——**O(4)**。
- `shipweather`（行 484-505）每 1 秒递归 `call_out("shipweather", 1)`——**天气判定每秒一次**，`niceweather` 5-15 秒后翻转回。
- `time_out`（行 46 + 49-53）：`call_out("time_out", 900+random(500))`——**每船 15-23 分钟无操作自动翻船**，防止僵尸船常驻。

**1000 在线下评估**：
- 同时在航船只上限：3 艘 seaboat（`seaboat1-3.c`），但**每船可载多玩家**（`all_inventory(this_object())` 判定 is_owner 行 475-482）。最坏 3 船在航。
- 每船 navigate 每 2 秒一次 O(10 暗礁 + 3 岛屿 + 4 港口) = O(17) 线性扫，3 船 = 每秒 ~25 次线性扫，**可忽略**。
- **真正风险**：`find_object` / `load_object` 在靠岸判定时**反复尝试加载港口房间**——`navigate` 行 236-237、264-265 在 `locx < 1` 或命中岛屿时 `find_object`，已加载则 O(1)，但 `do_lookout`（行 369、415）与 `do_locate`（行 452）**每次玩家输入都 find_object + 可能 load_object**。3 船 × 多玩家 × 高频 lookout/locate 会**重复触发 load_object**——LPC driver 有缓存，加载过的不重复 create，但 `find_object` 调用本身是每次 O(1) 哈希查。
- **致命隐患**：`do_drop`（行 513-537）翻船时 `inv[i]->move(keys(harbors)[random(sizeof(harbors))])`——**随机选一个港口把玩家 move 过去**，move 会触发目标房间加载 + look。批量翻船时 N 玩家同时 move 到随机港口，**瞬时 N 次 call_other + 房间加载**。

### 3.3 坐骑（LPC）

`clone/horse/horse.h`（83 行，22 匹马：`clone/horse/*.c`）：

- `condition_check()`（horse.h:7-41）：每次骑乘移动后检查 `jingli` 体力，<=10 昏厥坠骑 + `receive_wound("qi", 150)`，<=30 喘气，<= mj/3 喘粗气。**O(1) 单马检查**。
- `init()`（horse.h:42-65）：马匹进草地形 `resource/grass` 时恢复体力 + food——**每次马匹进房间触发**，O(1)。
- `set_leader` 跟随：随主人移动，无独立 call_out（靠主人 move 链式触发）。

**1000 在线下评估**：1000 玩家若半数骑马，每移动一次触发 500 次 `condition_check`，**O(500) 每移动周期**，可接受。

### 3.4 engine 现状对照

- **渡船**：`engine/src/openmud/ferry.py`（147 行）`FerryState` 纯内存 + `on_tick` 翻转 exit（`ferry.py:102-113 _on_ferry_tick`）。每 tick 全部 crossing 各减 1 计数，到 0 翻转 `at_bank_a` + `_apply_crossing_exits`（行 123-132）增删 `Exits.by_direction`。**无 yell 触发，无玩家交互**——纯定时翻转，简化了 LPC 的 yell 互斥周期。
- **玩家船**：**engine 未实现**（`ship.py` 不存在，`ferry.py` 只覆盖渡口）。导航/天气/瞭望/所有权均缺失。
- **坐骑**：engine 有 `Mount` capability（`components.py` 引用，`scene_loader._validate_shop_inventories` 行 1444-1452 校验），但**无 `condition_check` 等价物**——体力衰减与坠骑未实现。

**engine 性能隐患**：
1. `_on_ferry_tick`（`ferry.py:102-113`）每 tick 遍历全部 `state.crossings`——渡口数少（MVP 1-2 对），O(crossings) 可忽略。
2. `_crossing_for_room`（`ferry.py:135-139`）线性扫 crossings 找 room 对应的 crossing——`ferry_status_line`（行 53-71）每次 look 渡口房间都扫一次，O(crossings) 可忽略。
3. **缺玩家船是功能缺口非性能问题**，但若未来按 LPC 模式实现，**navigate 每 2 秒 O(islands+harbors) 线性扫 + find_object** 需异步化，不能在 on_tick 主循环里同步跑 3 艘船的导航。

---

## 4. call_out 周期与 tick 密度

### 4.1 LPC 定时器清单

| 来源 | call_out 数量 | 周期 | 全局唯一性 |
|------|---------------|------|------------|
| `natured.c` `update_day_phase` | 1 | 120-240 游戏分钟（=真实秒） | 全局单例（NATURE_D daemon） |
| `ferry.c` 9 渡口 × 3 阶段（on_board/arrive/close_passage） | 最多 27 | 15-20 秒 | 每渡口独立 |
| `ship.c` 3 船 × navigate/shipweather/niceweather/time_out | 最多 12 | 1-2 秒（navigate/shipweather） | 每船独立 |
| `horse.h` | 0 | — | 无 call_out，靠 move 触发 |

**总定时器密度**：常态 ~1（nature）+ 0-27（渡口活跃期）+ 0-12（在航船）= **最多 ~40 个并发 call_out**。LPC driver 的 call_out 用最小堆调度，O(log N) 每次，**40 个完全无压力**。

### 4.2 engine 现状

- 单一 `on_tick` 事件（`events.py ON_TICK`），`TickLoop.advance` 串行分发所有订阅者（nature / ferry / ai / combat / room_hooks）。
- **无 call_out 等价物**——所有定时器都靠 on_tick 计数推进（`FerryCrossing.ticks_until_flip` 递减、`NatureState.elapsed` 累加）。
- **风险**：若未来加玩家船 navigate 每 2 秒一次，要么挂 on_tick（每 tick 跑，但 tick 节奏由命令驱动，1 tick = 1 命令，**无人输入时船不动**），要么引入独立定时器（偏离单 on_tick 模型）。LPC 的 call_out 是墙钟驱动，engine 是命令驱动——**这是根本性差异**，玩家船异步导航在 engine 现有模型下无法直接复刻。

---

## 5. 持久化开销

### 5.1 LPC 存档路径

- **房间不存档**：`inherit/room/room.c` 的 `doors` 是 `static mapping`（`room.c:15`），LPC `static` 关键字表示**不进 .o 存档文件**。房间状态（门开关、NPC 生成）靠 `reset()` 周期重建。
- **玩家存档**：`event_sunrise`（`natured.c:83-97`）每日 sunrise 遍历 `users()` 同步双存档：`link_ob->save()` + `ob[i]->save()`（行 92-93）。
- **船所有权**：`ship.c` 的 `exits/out` / `navigate/*` 都用 `set_temp` / `query_temp`（行 100-101、118-119、318、491-493）——**temp 数据不进存档**，重启后船回到港口、navigate 状态清空。
- **马匹**：`jingli` / `food` / `rider` 等挂在 clone 对象上，**clone 不进存档**（只有 master .o 存档），重启后马匹重置。

**1000 在线下评估**：
- 每日 sunrise 同步双存档 1000 玩家 = 2000 次 `save()`，LPC `save_object` 写 .o 文件——**同步阻塞主循环**。若每玩家 .o ~10 KB，总 20 MB 磁盘写，HDD 上**数秒级阻塞**，SSD 上仍 **数百 ms**。**这是原版最大性能瓶颈**。
- 房间/NPC/物品不存档，靠 reset 重建——**重启后世界状态丢失**（门全开、NPC 回 startroom、物品重生成），但**重启快**（无需反序列化世界）。

### 5.2 engine 现状

`engine/src/openmud/save.py`（583 行）：

- **全量存档**：`save_world`（`save.py:351-385`）遍历 `world.all_entities()`（行 370），**每个实体写一个独立 JSON 文件** `entity_<id>.json`（行 372），`_write_json_atomic` 做 tmp + fsync + os.replace 三步原子写（行 526+）。
- **每实体 fsync**：`_write_json_atomic` 对每个 entity 文件 fsync——1000 玩家 + NPC + 物品 + 房间 = **可能数万实体**，每实体一次 fsync = **数万次磁盘 flush**。SSD 上每 fsync ~0.1-1ms，**数万次 = 数秒到数十秒**。**比 LPC 的同步双存档更慢**。
- **staging 快照 + 原子发布**（行 364-385）：写新快照目录 -> `_publish` symlink 切换 -> `_cleanup_old_snapshots` 保留旧快照。**CRDT 式防崩溃**，但**全量重写**无增量。
- **三态过滤**（`save.py:449-466 _strip_transient`）：瞬时字段不进存档——`FerryState` / `NatureState` / `AISystem` / `CombatSystem` 等纯内存态（`world.py:75-101` 一系列 `| None` 字段）**不进存档**，restore 后靠 `wire_runtime` 重建（`scene_loader.py:151`）。这与 LPC `static` 语义一致。

**engine 性能隐患**：
1. **每实体一文件 + fsync 是致命瓶颈**：6414 房间 + 1000 玩家 + N NPC/物品，即使只存「有可变态的实体」（房间门、玩家、NPC 进度），也是**数千次 fsync**。1000 在线下**存档一次可能阻塞数十秒**。
2. **无增量存档**：LPC 每日 sunrise 只存玩家（房间靠 reset 重建），engine 全量存所有可变态实体——**存档量远超 LPC**。
3. **restore 全量读**：`restore_world`（`save.py:388-433`）遍历快照目录所有 `entity_*.json` 逐个 `json.load`——**数千次文件 I/O + JSON 解析**，启动慢。
4. **无 LPC 的 reset 重建机制**：engine 房间状态进存档（门、RoomFreeState），**重启后保留状态**（比 LPC 强），但**代价是存档量大**。

---

## 6. 现有 engine 模块性能隐患汇总

仅评估方向（不深读实现细节），按风险等级排序：

### 6.1 高风险

1. **`save_world` 全量 + 每实体 fsync**（`save.py:351-385`）：1000 在线下存档阻塞数十秒。**建议方向**：批量写（单文件多实体 JSON 数组）+ 异步 fsync + 增量存档（只存脏实体）。
2. **`entities_in_room` 无反向索引**（`world.py:217-232`）：15+ 处调用方每命令路径 O(N) 全表扫。**建议方向**：`World` 维护 `dict[EntityId, set[EntityId]]` room -> entities 反向索引，`Position` 组件增删时同步更新。
3. **`_outdoor_player_ids` 每相位切换重建**（`nature.py:502-514`）：1000 玩家全表扫。**建议方向**：维护户外玩家集合的增量索引（玩家移动进出户外房间时更新），或缓存 + invalidation。

### 6.2 中风险

4. **`scene_loader.load_scene` 全量建图**（`scene_loader.py:81-152`）：冷启动加载全部 6414 房间，UGC 大题材包加载慢。**建议方向**：分区域懒加载（按玩家所在区域动态加载），但需解决跨区 exit 引用。
5. **`_resolve_ferry_refs` 全表反转 + 二次扫描**（`scene_loader.py:1402-1434`）：加载期 O(N) 两次，可接受但可优化为单次扫描。
6. **`NatureState.advance_tick` 每 tick 调用**（`nature.py:279-318`）：100 并发下每秒 100 次 advance_tick，每次可能触发 `ON_NATURE_CHANGE` 分发 + 广播。**风险**：天气翻转概率 10% 时高频广播。**建议方向**：广播节流（同相位内最多广播一次天气变化）。

### 6.3 低风险

7. **`_on_ferry_tick` 每 tick 遍历 crossings**（`ferry.py:102-113`）：crossings 数少，可忽略。
8. **`_crossing_for_room` 线性扫**（`ferry.py:135-139`）：crossings 数少，可忽略。
9. **`components_of` 扫全类型表**（`world.py:238-247`）：存档序列化用，M1 组件类型 ~30 个，O(30) per entity，可接受。
10. **`EventBus.register` 无去重靠 `handlers_for` 查重**（`nature.py:443-446`、`ferry.py:47-48`）：每次 `attach_*` 扫 handler 列表，次数少可忽略。

---

## 7. 跨维度风险交叉

### 7.1 存档 × Nature 广播

LPC `event_sunrise`（`natured.c:83-97`）把**全量同步存档**挂在相位切换上——1000 玩家每日 sunrise 一次同步双存档阻塞。engine 若把 `save_world` 挂在 `on_nature_change`（或某个相位事件），**同样会阻塞相位切换**。**建议**：存档与 Nature 解耦，存档走独立定时器或脏标记，不绑相位。

### 7.2 玩家船 × call_out 模型差异

LPC 玩家船 navigate 是墙钟 call_out 每 2 秒一次，**与玩家输入解耦**（玩家不输入船也在动）。engine 单 on_tick 模型是命令驱动，**无人输入时 tick 不推进**——玩家船在 engine 下要么「玩家不输入就不动」（破坏 LPC 体验），要么引入独立墙钟定时器（破坏单 on_tick 简洁性）。**这是设计决策点，非纯性能问题**，但影响可扩展性。

### 7.3 大世界 × 懒加载差异

LPC 房间懒加载（`call_other` 触发首次 create），engine 全量加载（`load_scene` 一次性建全部房间）。1000 在线时：
- LPC：内存只占已访问房间（可能 < 1000 间），但**首次移动有 create 延迟**。
- engine：内存占全图（6414 间常驻），但**移动无加载延迟**。

UGC 题材包做大时，engine 全量加载**启动时间与内存随房间数线性增长**，LPC 懒加载更优。**建议**：engine 引入懒加载或分区域加载，但需解决跨区 exit 引用与存档一致性。

### 7.4 reset × 存档语义差异

LPC reset 重建房间库存（门、NPC、物品），**世界状态不持久化**，靠 reset 周期「自愈」。engine 房间状态进存档（门、RoomFreeState），**无 reset 重建机制**——存档损坏的实体无法靠 reset 恢复。**这是可靠性差异，非性能**，但影响运维策略。

---

## 8. 给后续 engine 设计的性能输入（非接口草案）

> 仅方向性输入，不输出接口契约（遵循 brief 第 1.4 条「不输出 engine 接口草案」）。

1. **必须建 room -> entities 反向索引**：`World.entities_in_room` 是 15+ 处调用的热路径，1000 在线下 N² 风险。反向索引在 `Position` 组件 add/remove/move 时增量维护。
2. **存档必须从「每实体 fsync」改为批量 + 增量**：1000 在线下全量 fsync 不可接受。考虑单文件多实体 + 周期性增量快照。
3. **Nature 广播应缓存户外玩家集合**：相位切换是低频事件（每 ~180 秒），但若未来天气高频翻转，缓存收益显著。
4. **玩家船导航若实现，必须异步化**：不能在 on_tick 主循环同步跑 O(islands+harbors) 扫描 + find_object，应走独立协程或异步任务。
5. **懒加载或分区域加载**：UGC 大题材包下全量 load_scene 不可扩展，但需解决跨区 exit 与存档一致性——这是架构决策，需 ADR。
6. **存档与相位切换解耦**：LPC `event_sunrise` 把存档绑在 Nature 上是历史包袱，engine 不应复刻。

---

## 9. 未决问题（交评审委员会）

1. **单 on_tick 模型 vs 墙钟 call_out**：玩家船 / 自动巡逻 NPC 等「时间驱动」需求在 engine 单 on_tick（命令驱动）模型下如何实现？是否需要引入独立墙钟定时器层？（影响可扩展性架构）
2. **全量存档 vs LPC reset 重建**：engine 选择存档所有可变态实体（含房间门），LPC 只存玩家靠 reset 重建世界。哪种更适合 1000 在线 + UGC 题材包横向扩展？（影响存档策略与重启体验）
3. **懒加载 vs 全量加载**：UGC 大题材包下，engine 是否应回归 LPC 懒加载模式？跨区 exit 引用如何解？（影响启动时间与内存）
4. **`entities_in_room` 反向索引的维护成本**：反向索引在 `Position` move 时更新，但 `destroy_entity` / 组件 remove 路径多，如何保证一致性？（影响实现复杂度）

---

## 附录：证据来源索引

### LPC 一手源码

| 文件 | 关键函数/对象 | 用途 |
|------|---------------|------|
| `d/REGIONS.h` | `region_names` mapping（35 键） | 区域映射 |
| `d/` 全目录 | 6414 `.c` 房间文件 | 规模实测 |
| `inherit/room/room.c` | `make_inventory`（52-74）/ `reset`（76-155）/ `usr_in`（21-29）/ `open_door`（168-191）/ `create_door`（227-257）/ `doors`（15 static） | 房间基础 |
| `d/village/alley1.c` / `d/village/sroad3.c` / `d/city/wdroad1.c` | 房间定义模式 + 跨区 exit | 房间示例 |
| `feature/move.c` | `move(dest, silently)`（47-121）/ `add_encumbrance`（16-23） | 移动机制 |
| `adm/daemons/natured.c` | `update_day_phase`（54-77）/ `event_sunrise`（83-97）/ `event_common`（100-142）/ `message("outdoor:vision", msg, users())`（71） | Nature 广播 |
| `adm/etc/nature/day_phase` | 8 时段数据 | 相位配置 |
| `inherit/room/ferry.c` | `do_yell`（28-53）/ `check_trigger`（55-91）/ `on_board`（93-112）/ `arrive`（114-139）/ `close_passage`（141-157） | 渡船周期 |
| `inherit/room/ship.c` | `do_start`（73-110）/ `navigate`（112-282）/ `do_lookout`（341-421）/ `do_locate`（423-473）/ `shipweather`（484-505）/ `do_drop`（513-537）/ `time_out`（49-53） | 玩家船 |
| `clone/ship/harbor.h` | `harbors`（4 港口）/ `islands`（3 岛屿）/ `wildharbors` | 港口数据 |
| `clone/ship/seashape.h` | `jiaos`（10 暗礁） | 海图数据 |
| `clone/ship/seaboat1-3.c` | 3 艘玩家船实例 | 船数量 |
| `clone/horse/horse.h` | `condition_check`（7-41）/ `init`（42-65） | 坐骑体力 |
| 9 处 ferry 实例 | `d/xixia/oldwall.c` / `d/taihu/matou.c,matou2.c` / `d/heimuya/shuitan1.c,shuitan2.c` / `d/shaolin/hanshui1.c,hanshui2.c` / `d/taihu/taihu.c` / `d/xixia/xhbao.c` | 渡口实例化 |

### engine 模块

| 文件 | 关键位置 | 用途 |
|------|----------|------|
| `engine/src/openmud/world.py` | `World._components`（52）/ `entities_with`（210-215）/ `entities_in_room`（217-232）/ `components_of`（238-247）/ `room_ids`（97）/ 运行时态字段（75-115） | ECS 容器 |
| `engine/src/openmud/nature.py` | `NatureState.advance_tick`（279-318）/ `_outdoor_player_ids`（502-514）/ `_broadcast_nature_change`（517-535）/ `attach_nature`（398-449） | Nature 系统 |
| `engine/src/openmud/ferry.py` | `FerryCrossing`（22-33）/ `attach_ferries`（42-51）/ `_on_ferry_tick`（102-113）/ `_apply_crossing_exits`（123-132）/ `_crossing_for_room`（135-139） | 渡船系统 |
| `engine/src/openmud/scene_loader.py` | `load_scene`（81-152）/ `_build_rooms`（461-492）/ `_build_exits`（545+）/ `_resolve_ferry_refs`（1400-1434） | 场景加载 |
| `engine/src/openmud/save.py` | `save_world`（351-385）/ `restore_world`（388-433）/ `_serialize_entity`（469-485）/ `_write_json_atomic`（526+）/ `_strip_transient`（449-466） | 持久化 |
| `engine/src/openmud/components.py` | `Exit`（102）/ `Exits`（115-123）/ `Position`（91-98）/ `Description`（76-84） | 组件定义 |
| `engine/src/openmud/commands.py` / `parsing.py` / `messaging.py` / `quest.py` / `combat_system.py` / `room_hooks.py` / `ai.py` | 15+ 处 `entities_in_room` 调用 | 反向索引需求证据 |
