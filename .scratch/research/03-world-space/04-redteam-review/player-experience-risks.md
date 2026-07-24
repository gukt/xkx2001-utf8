# 红队：世界空间层玩家流失风险与必须保护机制

> 角色：玩家体验风险挑战者（03-world-space 红队 Phase 2）。
> 质疑对象：`03-engine-insights/player-psychology.md` 为主，旁及 `modern-design-review.md`、`gameplay-slices.md`、`mechanisms.md`、`commercialization.md`、`06-engine-critique/engine-comparison.md`。
> 证据规则：每条结论标注被质疑文件与段落 + LPC/`engine` 证据来源（文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。禁止凭空推断。
> 立场：player-psychology 对风险的**定性大致正确**（D1 高危、移动疲劳三重叠加、惩罚烈度不匹配），但对**保护机制的优先级与充分性过于乐观**：6 条「底线」被框成「建议」，其中至少 3 条在 engine 现状下是 MVP 阻塞级必须项；且评估未对齐 `source-inventory.md` 的事实校正、未覆盖 engine 已移除的恢复回路、未评估自身建议（天气接线为机制）会引入的新流失点。

---

## 0. 摘要：5 条质疑 + 1 张优先级表

1. **「6414 房间」是未对齐的事实错误**：`source-inventory.md §0` 已校正真正房间 = 3684（6414 是 `.c` 文件总数含 NPC/obj），但 `player-psychology.md` 全文（摘要、§1.1、§2.2、§2.3）仍用 6414。更要紧的是：**MVP 场景只有 36 间房**（`engine/data/m2_mvp_scene.yaml` `rooms:` 实测），D1 迷路断崖在 MVP 不会触发——但 engine 必须为题材包放大到 3684 规模预留保护，评估混淆了「MVP 风险」与「引擎必须项」。
2. **「走累了昏迷」被严重低估**：`jingli` 不是移动专属资源，而是被战斗技能、练功、挖陷阱、乞讨共用的池子。`go.c:72-73` 的移动阻断发生在玩家打完架、练完功之后，`unconcious()`（`feature/damage.c:105-126`）把 jing/qi/jingli 同时归零。player-psychology §3 把它当成「单走累了」的惩罚失配，实则是「跨系统资源被掏空后的最后一击」。
3. **马匹体力在 engine 里没有恢复回路**：`engine-comparison.md N6` 确认 `RoomResources`「grass 未打通」；MVP 场景 0 间 grass 房（实测）。player-psychology §3.4 提到吃草是「被动缓解」，但其 6 条底线**没有一条要求补恢复回路**——底线 3（可视化）只解决「看得见」，不解决「回不来」。
4. **渡船在单机 + engine 去 yell 化后，玩家彻底无代理权**：`engine-comparison.md N4` 确认 engine `ferry.py` 把 LPC 的 `yell` 触发改成定时自动翻转、且删了船房实体。player-psychology §5.1 仍按 LPC 的 55s 喊船周期讨论「社交停留失效」，未察觉 engine 已让渡船变成「玩家只能干等计时器」的纯被动门，搁浅风险（玩家过岸后被计时器甩下）未被评估。
5. **「天气接线为机制」的建议本身会制造新的迷路流失点**：`modern-design-review.md §3.3` 与 player-psychology 底线 6 都建议把天气升级为「影响视野/移动」的机制变量。但 LPC 从未让夜间/天气影响导航（`natured.c` 无视野修正，`weather_msg` 是死代码），若按建议接线「夜间视野惩罚」，在一个本就无地图的世界里等于叠加「看不清路」→ 迷路风险被新引入而非消除。评估未做这一层反身性检查。

---

## 1. 质疑一：「6414 房间大世界」未对齐事实校正，且 MVP 规模让 D1 断崖被高估

### 被质疑段落
- `player-psychology.md` 摘要：「6414 房间的大世界是一把双刃剑」
- `player-psychology.md §1.1`：「35 个区域命名差异极大……最大区域 beijing 625 / dali 467 / city 441……」
- `player-psychology.md §2.3`：「新手从华山村（33 房间）进入扬州城（134 房间）是典型的从『可记忆规模』跨入『不可记忆规模』的临界点……D1 高危」

### 证据
1. **房间数事实错误**：`source-inventory.md §0 重大事实校正 #1` 明确「『6414 房间』实为 6414 个 .c 文件总数（含 NPC/obj），真正房间（`inherit ROOM`）只有 3684 个」。`player-psychology.md` 全文未同步此校正，摘要、§1.1、§2.2、§2.3 仍用 6414。3684 仍是大世界，但评估的量化基底是错的。
2. **MVP 实际只有 36 间房**：`engine/data/m2_mvp_scene.yaml` `rooms:` 段实测 36 个房间键（`huashan_birth`/`yangzhou_guangchang`/`yangzhou_beidajie`/`road_huashan_yz`/`ferry_west`/`ferry_east`/`wild_forest` 等），其中扬州相关约 12 间（`yangzhou_*`）。`commercialization.md §4.3` 与 `creator-perspective.md §3.2` 亦确认 MVP 小切片。CLAUDE.md 架构不变量第 7 条的 MVP 场景是「华山村+扬州子集+少林+沿途」，**不是 134 间的完整扬州**。
3. **player-psychology §2.3 的「33→134」临界点是按完整 LPC 扬州算的**：`d/city/` 实测 124 间房（`source-inventory.md §1.1` 表，city 124），MVP 扬州子集约 12 间，跨不到「不可记忆规模」。

### 质疑结论
D1 高危的**定性成立**（无地图+无导航在任何规模都会迷路），但**定量被高估**：MVP 36 间房不会触发「33→134」式断崖。真正的问题是**评估未区分两件事**：
- (a) MVP 阶段：36 间房，迷路风险低，但 engine 必须把保护机制**建进引擎**，否则官方武侠包放大到 3684 间时再补就来不及；
- (b) 题材包放大阶段：6414/3684 规模，D1 断崖真实存在，所有导航保护此时才生效。

player-psychology 把 (b) 的风险当成 MVP 的风险来论证「底线」的紧迫性，论据错位；但结论（engine 必须有保护）反而因为论据错位而被低估了「为什么必须是引擎级、不是题材包可选」。

---

## 2. 质疑二：「走累了昏迷」被低估——jingli 是跨系统共享池

### 被质疑段落
- `player-psychology.md §3.1`：「三条消耗条 + 一条马匹条 + 出口试错成本，玩家在长途移动时需要同时管理多个数值」
- `player-psychology.md §3.3`：「对玩家而言，体力耗尽（`go.c` line 230 `jingli<=0 -> unconcious()`）等同于一次小型死亡……玩家不是战败，只是走累了」
- `mechanisms.md §3.2`：「jingli 同时被战斗/练功等其他系统消费」

### 证据
`jingli`（精力）不是移动专属资源，而是被多系统共用的池子（全仓 `grep jingli` 实测）：
- 移动：`cmds/std/go.c:225-234`（步行 `-cost*2`、骑乘马 `-cost*2`、骑手 1/5 概率 -2）
- 练功：`cmds/std/train.c:56` `me->add("jingli", - cost)`
- 挖陷阱：`cmds/std/trap.c:159` `me->receive_damage("jingli", depth*cost/10, "挖陷阱累死了")`
- 乞讨：`cmds/std/beg.c:91-93`（按 con 计算 jingli_cost 并扣）
- **战斗技能**：`kungfu/skill/pixie-jian.c:321,331,342,349`（辟邪剑每招 `-20+random(20)`）、`kungfu/skill/murong-shenfa.c:125,135,142,149`（慕容身法吸对手 `-20`）、`kungfu/skill/huashan-shenfa.c:137,147,154,161`（华山身法吸对手 `-20`）、`kungfu/skill/feiyu-bian.c:63`（飞雨鞭 `-5`）——**战斗中 jingli 被双方互相抽干**
- 恢复（仅缓慢被动）：`feature/damage.c:310-316` 心跳回 jingli，按 `(str+dex)/12`（战斗中）或 `/4`（非战斗）；上限 `max_jingli*2`；或靠吃喝 `feature/food.c:26`、`feature/liquid.c:51`
- 昏厥后果：`feature/damage.c:122-126` `unconcious()` 把 `jing`/`qi`/`jingli` **同时归零** + `block_msg/all` + `disable_player(" <昏迷不醒>")` + 30~120 秒后才 `revive`（`damage.c:126` `call_out("revive", random(100-query("con"))+30)`）

### 质疑结论
player-psychology §3.3 把「走累了昏迷」定性为「惩罚烈度与行为严重性不匹配——玩家不是战败，只是走累了」。这个定性**错了**：玩家在 MVP 官道/野外打完一场架（jingli 被武功技能互抽至低），然后试图 `go` 走回城镇恢复，此时 `go.c:72-73` 的 `jingli < max_jingli/10` 阈值一卡就「动弹不得」，再走几步 `go.c:230` `jingli<=0` 直接 `unconcious()` 三属性归零。**这不是「走累了」，是「战斗的后置惩罚通过移动系统结算」**——玩家会把这次昏迷归因于「刚才那场架」，产生「打完架不能走」的二次挫败，而非「我走太远了」。

player-psychology §3.1 的「三重消耗叠加」只数了移动层内部的负重/人体力/马匹/出口试错，**漏了 jingli 的跨系统竞争**——这是移动疲劳被低估的核心。底线 2（耗尽不直接昏迷、分级提示）是对的方向，但**必须连同「移动消耗不应复用战斗资源池」一起设计**，否则分级提示只延缓了归零，不解决「打完架走不动」的根因。

---

## 3. 质疑三：马匹体力在 engine 无恢复回路——底线 3 不充分

### 被质疑段落
- `player-psychology.md §3.4`：「`horse.h init()` 里有一处缓解：房间有 `resource/grass` 时马匹吃草恢复 jingli（line 48-56），但这是被动触发且依赖房间配置，不是玩家可控的休息机制」
- `player-psychology.md 底线 3`：「骑手应能查询马匹体力（至少分档：充沛/疲惫/危险），并在『危险』档拒绝继续骑乘或强制下马」

### 证据
- LPC 唯一的马匹体力恢复回路：`clone/horse/horse.h:48-56` `init()`——马进入 `query("resource/grass")` 房间时 `add("jingli", (max_jingli-jingli)/2)` 回一半缺口。`source-inventory.md §1.1` 实测 grass 房 59 个。
- engine 完全未接此回路：`engine-comparison.md N6` 明确「`components.py:577` `RoomResources` 明注『grass 未打通』」；`abstraction-options.md §2.2`「`RoomResources`（`components.py:573`）注释明说『grass / 坐骑喂食未打通』」。
- **MVP 场景 0 间 grass 房**：`m2_mvp_scene.yaml` 实测 `resource/grass` 命中 0 间（`grep grass` 在 rooms 段无命中）。
- engine 坠骑阈值比 LPC 更宽容但更无回路：`abstraction-options.md §2.2`「engine 坠骑阈值是 `jingli==0`（`commands.py:515`），LPC 是 `jingli<=10`（`horse.h:18`）」；engine 移动时扣（`commands.py:513`），LPC 是 chat_tick 随机衰减（站着也掉）。

### 质疑结论
player-psychology 底线 3 只要求「看得见 + 危险档拒绝骑乘」，**但没要求恢复回路**。在 engine 现状下：
- 马匹 jingli 只减不回（无 grass、无吃草、`RoomResources` 未接线）；
- 一旦 jingli 触底，马匹 `unconcious()`（`commands.py:515-521`）、骑手摔下；
- 玩家即使「看得见」体力条到危险档，也**没有任何动作能让它回升**——只能弃马步行。

这把坐骑从「可管理资源」降级为「一次性消耗品」。player-psychology §3.4 把吃草写成「被动缓解的次要机制」，但它其实是**LPC 唯一的恢复通道**，engine 把它砍了之后整条资源回路就断了。**底线 3 不充分**，必须补一条：「坐骑体力必须有恢复回路（grass 或等价休息机制）」——这是 P0 必须项，不是「post-MVP 再评估」。`commercialization.md §2.1` 还把「付费买续航恢复速度」列为可接受付费方向，但前提是恢复回路存在，当前 engine 连免费恢复都没有。

---

## 4. 质疑四：渡船在单机 + engine 去 yell 化后，玩家彻底无代理权

### 被质疑段落
- `player-psychology.md §5.1`：「55 秒同步等待窗口是天然的社交停留点……单机语境：无其他玩家，社交停留失效。55 秒等待退化为纯等待……需要用环境叙事或机制填补」
- `player-psychology.md 底线 4`：只针对**船难**（`do_drop` 全损）要求分级，未涉及渡船本身的等待与搁浅

### 证据
- LPC 渡船是玩家主动 `yell` 触发：`inherit/room/ferry.c:28` `do_yell` -> `:55` `check_trigger` -> `:90` `call_out("on_board",15)` -> `:111` `call_out("arrive",20)` -> `:138` `call_out("close_passage",20)`。玩家**有召唤权**，错过窗口能立刻再 `yell`（`ferry.c:60`「正等着你呢」可重入）。
- engine 删了 yell 与船房实体：`engine-comparison.md §5 / N4`「engine `ferry.py` 纯定时翻转，无 yell/无船房实体/无登船」；`ferry.py:102-113` `_on_ferry_tick` 按 `cross_interval` 自动翻转 `at_bank_a`，`_apply_crossing_exits`（`ferry.py:123-132`）直接改两岸 `Exits.by_direction`。
- MVP 场景确认渡船在路径上：`m2_mvp_scene.yaml` 有 `ferry_west`/`ferry_east` 两间。
- 搁浅场景：玩家 `go across` 过岸后探索对岸，若 `ticks_until_flip` 到期翻转，对岸 `Exit` 被删——玩家在对岸**没有召唤权**（engine 无 yell），只能干等下一次自动翻转。`ferry.py:53-71` `ferry_status_line` 只提示「约 N 个时辰后到达」，不提供「立即召回」。

### 质疑结论
player-psychology §5.1 仍按 LPC 的「55s 喊船周期 + 社交停留」框架讨论单机，**未察觉 engine 已经把渡船从「玩家可召唤的载具」降级为「玩家只能等计时器的门」**。后果：
1. **代理权归零**：LPC 玩家错过船能立刻 `yell` 再叫；engine 玩家错过窗口只能等下个 `cross_interval` 周期，无任何主动操作可缩短。
2. **搁浅无自救**：玩家过岸后被计时器甩下，对岸无 yell，干等。
3. player-psychology 底线 4 只处理「船难全损」，**完全没覆盖渡船的等待/搁浅**——因为评估还停在 LPC 的 yell 模型上，没对齐 engine 的自动翻转模型。

**必须补的保护**：渡船在单机下要么恢复玩家召唤权（`yell` 或等价 `wait`/`call` 命令）、要么允许玩家付费/消耗道具即时召回、要么过岸后保留回程出口直到玩家主动离开。这是 MVP 路径上的体验阻塞点（`ferry_west`/`ferry_east` 在 `m2_mvp_scene.yaml`），不是 post-MVP 议题。

---

## 5. 质疑五：「天气接线为机制」的建议本身会引入新的迷路流失点

### 被质疑段落
- `modern-design-review.md §3.3`：「天气**应从纯文案升级为机制变量**（至少影响视野/移动消耗/特定 NPC 出没）」
- `player-psychology.md 底线 6`：「把 `weather_msg` 接线（让天气真正变化）以补回环境沉浸维度」
- `player-psychology.md §4.3 风险一`：「当前 daemon 没有动态天气……玩家永远不会遇到下雨、起雾」

### 证据
- LPC 从未让夜间/天气影响导航或视野：`adm/daemons/natured.c` 全文无视野修正、无移动惩罚；`weather_msg`（`natured.c:11-17`）是死代码（`source-inventory.md §0 #3`、`mechanisms.md §9.1` 双重确认）；`outdoor_room_description()`（`natured.c:144-147`）只返回时段 `desc_msg`，不含天气。`source-inventory.md §0 #4` 进一步指出 8 个 `event_fun` 里 7 个是空操作。
- 唯一影响可达性的是 `day_shop` 夜间关门：`cmds/std/go.c:101-103` 在 `event_night`/`event_midnight` 拒进 `day_shop` 房间，返回「X 晚上不开，请天亮了再来」——但这是**商店可达性** gating，不是**导航视野** gating，玩家仍能走、能看出口。
- engine 现状对齐 LPC 的「天气不影响机制」：`engine-comparison.md §1.2`「engine `nature.py:38` docstring 明注『不做对玩家机制影响（视野/移动等）』」；但 `nature.py:517` `ON_NATURE_CHANGE` 已留事件点「为未来天气玩法预留接线位」（`modern-design-review.md §3.2`）。

### 质疑结论
两条建议（modern-design-review §3.3 + player-psychology 底线 6）都主张把天气「接线为机制」，且 modern-design-review 明确点名「影响视野/移动消耗」。但：
- 在一个**本就无地图、无导航、无方位感**的世界里（player-psychology §2 已证），再叠加「夜间视野惩罚/雨天移动消耗 +x%」，等于在迷路风险上再压一层「看不清路 + 走得更慢更耗体力」。
- LPC 之所以「天气不影响机制」可能不是「未完成」，而是**有意的克制**：在没有地图的世界里让天气惩罚导航，等于放大 §2 的 D1 迷路风险。player-psychology 自己在 §2 论证了无地图的流失风险，却在底线 6 反手建议接线「天气影响视野」——**两节结论互相打架**，评估没做这一层反身性检查。
- `day_shop` 夜间关门已经是「夜间缩小可达地图」的实例（`go.c:101-103`），且 player-psychology §4.2 把它当正面心流素材；若再给夜间加视野/移动惩罚，就是把「夜间地图缩水」从商店层面推广到全导航层面。

**不是反对天气接线**，而是要求评估补一步：**接线前必须先建好 §2 的导航保护（区域归属 + 主干道渐进提示 + 地图概览），否则天气机制会乘在没有安全网的世界上**。底线 6 应改为「导航保护就位后，才可考虑天气影响视野」——这是时序约束，不是并列建议。

---

## 6. 质疑六：genmap.c 既有 BFS 基础设施被当成「未决问题」而非现成资产

### 被质疑段落
- `player-psychology.md §2.1`：「存在一个后台地图生成器 `clone/obj/genmap.c`（BFS 从 `/d/beijing/kedian` 出发遍历，`start_mapping()`），以及查询接口 `clone/obj/mapdb.c`……但二者都是系统/任务侧的寻路数据库……没有任何玩家命令暴露这套地图」
- `player-psychology.md 附 未决问题 #3`：「`genmap.c`/`mapdb.c` 是否应作为『玩家可查的地图』对玩家暴露？……影响第五条底线的可行性判断」

### 证据
- `genmap.c` 注释（player-psychology §2.1 引用）：「since it is really expensive and may cause server crash, we try to be very prudent here」，`MAX_NODE=5`，每次 `call_out` 只处理 5 个房间。即 **LPC 作者明知需要寻路、也建了 BFS，但因 1990s driver 性能/崩溃风险主动限流**。
- `mapdb.c` 提供 `query_room_exits()`/`query_map()` 查询接口（player-psychology §2.1）。
- 消费者是 NPC/任务的局部 BFS：`d/city/npc/ftb_zhu.c`、`d/beijing/gulou2.c`、`d/wudang/sheshenya.c`（player-psychology §2.1）。

### 质疑结论
player-psychology 把「是否对玩家暴露 genmap」列为**未决问题**交委员会，是低估了现成资产：
- LPC 限流的根因是 driver 性能（`MAX_NODE=5` 防崩），**这个约束在现代 engine 不存在**——`performance-review.md §1` 实测 6414 房间常驻内存仅 ~30-60MB，BFS 距离计算在加载期一次性预算完全可行。
- 「渐进提示（距离 + 方向到地标）」正是底线 5 的内容，而 player-psychology §2.1 自己承认「`genmap.c` 已证明 BFS 距离可算，数据层面可行，缺的是对玩家的呈现」。
- 把一个「LPC 已验证可行、仅因时代性能被限流」的能力降级为「未决」，等于让一个本可低成本解锁的导航保护悬空。

**应改为已决**：engine 应提供「到已知地标的距离/方向」查询能力（不必是自动寻路，`modern-design-review.md §1.3` 也认同「auto-path 非必须」），数据层用加载期 BFS 预算 + 缓存。这不是「是否暴露」的问题，是「engine 必须提供导航态势感知」的具体落地路径，genmap.c 证明了它可行。

---

## 7. 质疑七：官道抢劫/exit_blockers 在必经官道上的不透明触发

### 被质疑段落
- `player-psychology.md §5.4`：「`d/village/hsroad3.c`（`init()` line 28-47）：玩家携带 `value >= 10000`……`random(3)==1` 触发草寇拦截……玩家若不知『携带贵重物会触发』，突袭式拦截会带来不公平感。触发条件对玩家不透明」

### 证据
- `d/village/hsroad3.c:28-47` `init()`：玩家携带 `value>=10000` 非货币物品 -> `set_temp("rob_victim",1)`，`random(3)==1` 生成 `new(__DIR__"npc/caokuan")` 草寇（`mechanisms.md §1.4`、`gameplay-slices.md §2` 引用）。
- `hsroad3.c:49-57` `valid_leave()`：草寇在场时阻断离开「爽快的将宝贝交出来」。
- 触发条件无任何玩家可见提示：`hsroad3.c` 只 `set_temp`，不 `tell_object` 告知玩家「你携带的财物引人注目」。
- 路径相关性：`gameplay-slices.md §2` 指出 `hsroad1`（华山村->扬州北门）是 MVP 核心跨区路径；`hsroad3` 是华山村->武当支线（`source-inventory.md §3.1`：`hsroad1->hsroad2->hsroad3->sexit` 通武当）。MVP 场景清单含「官道（跨区域连接）」与「野外」，`exit_blockers` + 随机劫匪作为**官道设计模式**会随官方武侠包扩展复现到任意官道。
- engine 已把 `exit_blockers` 数据化为 `block_exits`（`creator-perspective.md §2.1`：`scene_loader.py:612-658` `_attach_block_exits`），但同样不要求声明「触发提示文案」。

### 质疑结论
player-psychology §5.4 把它归入「社交压力变体 / PvE 压力」，评级偏低。对单机新手而言这是**必经官道上的不透明硬阻断**：
- 玩家无任何方式预知「带贵重物会触发」（无提示文案、无属性可见）；
- 一旦触发，`valid_leave` 阻断离开，玩家被锁在房间直到交物或战斗；
- 在无地图的世界里，玩家本就在靠 `long` 文案猜方向，突然被锁住会叠加「走不动 + 不知道为什么 + 不知道怎么解开」。

player-psychology 没把这条列为底线，但它满足「流失触发点」的全部特征：不透明 + 硬阻断 + 发生在必经路径。**应补一条保护**：任何 `exit_blockers`/`block_exits` 触发时，必须在触发瞬间给玩家可见的前置提示（如「你携带的财物引人注目，前方似有动静」），而非等玩家 `go` 失败才知道被拦。这是声明式即可解决的（`block_exits` 加 `warn_message` 字段），无需脚本。

---

## 8. 必须保护机制优先级表（对 player-psychology 6 条底线的裁决）

player-psychology 把 6 条底线统一框为「建议」。下表按「是否 MVP 阻塞 + engine 现状是否已满足」重排优先级，并标注其论证是否充分。

| 优先级 | 机制 | 对应 player-psychology 底线 | 裁决 | 理由 |
|---|---|---|---|---|
| **P0 必须** | **移动疲劳软着陆 + jingli 不复用战斗池** | 底线 2（部分） | **论证不足**：底线 2 只要求分级提示，未要求「移动消耗与战斗 jingli 解耦」。见质疑二：`kungfu/skill/*.c` + `train.c` + `trap.c` 共用 jingli，打完架走不动是跨系统竞争，分级提示只延缓不解决根因。 |
| **P0 必须** | **坐骑体力恢复回路** | 底线 3 未覆盖 | **缺失**：底线 3 只要「可视化 + 拒绝骑乘」，未要恢复回路。engine `RoomResources` grass 未接（`engine-comparison N6`）、MVP 0 grass 房，马匹变一次性消耗品。必须补 grass 或等价休息机制。 |
| **P0 必须** | **渡船恢复玩家代理权** | 底线 4 未覆盖 | **缺失**：底线 4 只管船难全损，未管渡船等待/搁浅。engine 去 yell 化后玩家纯被动等计时器、过岸可被甩下（质疑四）。MVP 路径含 `ferry_west`/`ferry_east`。 |
| **P0 必须** | **导航态势感知（区域归属 + 主干道渐进提示 + 地标距离查询）** | 底线 1 + 底线 5 | **优先级被压低**：底线 1（区域归属）单独不解决迷路（知道在「扬州」≠知道北门在哪）；底线 5（渐进提示）列最后且对冲「不必做自动寻路」。genmap.c 已证 BFS 可行（质疑六），应升为 P0 已决。三者须打包。 |
| **P1 强烈建议** | **坐骑体力可视化 + 危险档拒绝骑乘** | 底线 3 | **前提依赖 P0 恢复回路**：没有恢复回路时，「拒绝骑乘」只是把玩家逼下马步行，不解决问题。可视化本身是对的，但单独不充分。 |
| **P1 强烈建议** | **exit_blockers 前置提示** | 未列入底线 | **应新增**：质疑七，官道不透明硬阻断。声明式 `warn_message` 即可。 |
| **P1 强烈建议** | **交通惩罚分级（取消全损）** | 底线 4 | **MVP 相关性低**：`do_drop` 全损在玩家船（`ship.c`），engine 无 ship 模块（`engine-comparison N1`），MVP 不可达。但若 post-MVP 引入船，必须先做分级。作为 engine 设计约束保留。 |
| **P2 可迭代** | **时段广播频率调整 + 系统清理解耦** | 底线 6 | **有条件**：广播降噪是对的，但「接线天气为机制」部分（影响视野/移动）有时序前置依赖——必须 P0 导航保护就位后才可做（质疑五），否则叠加迷路风险。 |
| **P2 可迭代** | **天气真正动态化** | 底线 6 | 同上，且 engine `nature.py` 已有 2 态天气 + `ON_NATURE_CHANGE` 事件点（`engine-comparison P6`），比 LPC 强，不急。 |

### 对 player-psychology 6 条底线的整体裁决
- **底线 1、2、3、5 应升格为 P0 必须**（其中 2、3 须扩范围，见上表），不再是「建议」；
- **底线 4 拆分**：船难分级留作 P1（MVP 不可达），渡船代理权单列 P0（MVP 可达）；
- **底线 6 加时序约束**：导航保护就位前不接线天气视野机制；
- **新增**：exit_blockers 前置提示（P1）。

player-psychology 的核心风险定性（D1 高危、惩罚失配、无地图无导航）是成立的，但其「6 条建议」的**范围、优先级、充分性**三方面都需要收紧：范围上漏了恢复回路与渡船代理权，优先级上把导航保护压得太低，充分性上底线 2/3 只治标不治本。

---

## 9. 未决问题（交评审委员会）

1. **jingli 是否应拆成「移动体力」与「战斗精力」两个池**？LPC 共用 `jingli`（`kungfu/skill/*.c` + `go.c` + `train.c` 共证），这是失配惩罚的根因。engine 是否沿用单池，还是借重写机会拆分？（影响底线 2 的设计形状）
2. **MVP 36 间房是否仍需建区域归属/导航提示**，还是等官方武侠包放大时再建？player-psychology 的 D1 论证基于放大后规模；若 MVP 不建，engine 接口是否预留？（影响 P0 的交付时机）
3. **渡船在 engine 已去 yell 的前提下，是否应恢复某种玩家主动权**（召唤/等候/召回），还是接受「纯定时门」并靠 `ferry_status_line` 提示兜底？（影响质疑四的落地方案）
4. **`xiaohongma`（`clone/horse/xiaohongma.c`，value=500/ability=10/wildness=20000/独占 `do_duhe`）若作为付费坐骑设计**，`commercialization.md §2.1` 已判 ability 付费为红线——但「独占渡河技能」是否也属力量优势？player-psychology 未评估独占交通能力对「可达区域」的 gating 效应。
