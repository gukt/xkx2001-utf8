# MUD Engine

题材无关的核心 MUD 引擎与其官方轻量题材包所共享的领域语言。实现细节不在此文件。

## Language

### 战斗与状态

**Effect**:
挂在实体上、具有挂载 / 持续 / 衰减或到期移除生命周期的持续状态（buff/debuff 等）。归属仍是引擎机制，但不是 M2/M3 停机必须兑现的不变量（见 ADR-0007）。
_Avoid_: 把招式钩子的一次性副作用称作 Effect

**SkillBehavior**:
招式命中路径上的可选瞬时钩子（如 `hit_ob` / `hit_by` / `post_action`），在当次结算内生效，不自带持续生命周期。
_Avoid_: Effect, buff 系统, condition handler（除非特指 Effect 落地后的 handler）

**Unconscious**:
气血耗尽后的容错态 marker：无法执行会触发交战/移动的命令；退出路径包括 tick 自动苏醒，以及非免死区昏迷中再击转入死亡流程。
_Avoid_: 昏迷中只能靠再被打死才能翻篇（已否决为唯一退出路径）

### 门禁与持有

**持刃**:
门禁条件语义上的「正在持有刃器」。官方 MVP 场景在装备命令面落地前不使用该条件；背包中带 edged 标签**不等于**已对齐的持刃体验。
_Avoid_: 把「背包含 edged 物品」直接对外表述为完整持刃系统

### 运行时与创作

**Channel**:
跨房间、按订阅投递的命名广播管道；与同房间发言（`room_say`）并列。预置 `chat`（玩家可写）与 `system`（仅运行时/API 可写）两条。
_Avoid_: 把房间 say 叫频道, 把系统公告挤进玩家闲聊, rumor/门派/巫师频道表进核心, 未知命令 fallthrough 命中频道 ID, 假多人 seam 等同登录/联网

**房间 objects 放置**:
房间声明「模板键 → 数量」的物体清单；物品与 NPC 共用登记槽位——实例仍在则占名额，仅销毁后才可按 `respawn` 补齐（ADR-0010）。
_Avoid_: 以 `placed_in`/`in_room` 为权威放置字段, 把「离开地面」当成产生补刷缺口, 在房间保真 effort 重开放置模型

**房间风景**:
房间上可 `look` 的非实体描述。Polishing 拍板（K2+U+S1+N1）：YAML `details` 以**无空格英文 id** 为键，值为 `text` + `aliases`；英文 id 匹配时 `shi shi`=`shi_shi`=`shi-shi`=`shishi`（空格/`_`/`-`/全粘连同一骨架）。可见文本（`long` 与 `details.*.text`）手写 `石狮(shi shi)` 等；仅当能命中本房已登记 details 时高亮/可点；嵌套 look 目标同房扁平登记。不使用 `<d:…>`。着色在 `text` 的语义色 token 内。
_Avoid_: 风景实体, no_get 假物品, 把牌子/对联/书架放进 objects, features/scenery/item_desc 作本引擎权威字段名, 以带空格拼音作 details 主键, 强制 `<d:id>`, 见到任意括号就当可 look, 在 text 里嵌套未登记的匿名风景子树

**出口导航别名**:
玩家用以 `go`（及无动词的**英文**方向全写/简写）选中某条出口的名称集合。解析时按层合并：**出口 `aliases` → 目标房间 `name` 与 `aliases` → 该方向键的引擎内置同义词**（如 `east`/`e`/`东`）。裸 `east`/`e`/`u` 合法；**中文方位与中文地名均须带 `go`**。`look` 出口列表为中英并列（如 `东(east)`）。标准方位不必在 YAML 手写。斜向中文按英文释义（东南/西南）。多出口同名走 `Ambiguous`。
_Avoid_: 每个出口手写标准中文方位才可走, 把地名只挂在出口 aliases 而不能定义在目标房, 方向 canonical 键改成中文, 目标房只有 name、go 地名却要求必须再抄进 aliases, 裸中文方位或裸中文地名与裸英文方向同等合法（已否决）, look 出口只显示英文或只显示中文（已否决为权威展示）

**语义色**:
内容文本中的着色以 `<c:name>…</c>` token 表达；本波允许色名仅 `red`/`green`/`yellow`/`blue`/`magenta`/`cyan`/`white`（无背景/闪烁/粗体/嵌套）。引擎可校验；权威消息带 token，客户端渲染（官方 CLI：TTY/`--color` 映亮色 ANSI，管道/测试剥为纯文本）。YAML 不含原始 ANSI / LPC 色宏名。见 ADR-0011。
_Avoid_: ANSI 进 YAML, 服务端直接出转义序列作唯一真源, 把 Telnet 着色当成题材包格式, `[c:name]`/`%name%` 作权威语法, 本波引入 dim/bright 双轨或背景色 token, CLI 无开关始终染 ANSI

**Quest（声明式旗标任务）**:
题材包 YAML `quests.<id>` 声明的可接取任务；完成条件仅交物与旗标，到房只作前置；`ask` 不接任务。
_Avoid_: 通用对话树/脚本任务引擎, 用 ask 接任务作本批唯一入口, 把踩房本身列为一等完成类型

**单进程单 World**:
单机阶段的运行时约定：一个进程只承载一个 `World`；进程级全局注册表与该假设绑定（见 ADR-0009）。
_Avoid_: 假定已支持同进程多 World / 世界实例隔离已落地

**GAP 台账**:
声明式创作面「已知表达不了什么、推荐如何降级」的清单；用于防止把「示例包未撞墙」误读为「任意玩法皆可纯 YAML」。
_Avoid_: 能力橱窗包（与 GAP 台账不同交付物）, 空脚本沙箱接缝

**房间旗标**:
房间级布尔约束（本波：`no_fight` / `no_steal` / `no_sleep_room`），任意房间可在 YAML 声明。只对**已有命令面**生效：`no_fight` 拦 `attack`/`kill`；`no_sleep_room` 拦 `sleep`；尚无对应命令的旗标可声明并校验，但不假装已禁。藏书阁另以同房规则拦 `practice`（及日后打坐类命令）。
_Avoid_: 为让旗标「成真」而本波补齐 steal 子系统, 把旗标逻辑硬编码成单一房间特例

**客店**:
房间声明 `hotel: true` 表示客店房：须先 `pay <同房店家>` 付固定房钱（`HOTEL_RENT_COST`，当前 10 两）获得 `RentPaid` 后才能 `sleep`；离开该房经 `on_leave_room` 清除已付状态。挂 `HotelRoom` 的房间同房拦 `practice`（与 `LibraryRoom` 并列、不共用组件）。普通房间默认允许 `sleep`（拉满气血/精力，内力不变），除非 `no_sleep_room: true`。
_Avoid_: 复用 buy/give 付房钱, 用 LibraryRoom 拦客店练功, 付一次钱可无限回来睡

**条件 DSL**:
`entry_guard` / `day_shop`（派生 `is_day`）/ `skills.*.learn_condition` / `npcs.*.behaviors[].when` 共用的结构化条件表达式（`predicate` / `field`+`value` / `gte` / `and`/`or`/`not`）。创作者可读规格见 `docs/condition-dsl.md`。不开放背包任意物、任务旗标、局部天气等查询面。
_Avoid_: 在条件里发明 has_item/任务旗标/房间局部天气谓词, 为单个玩法往通用 DSL 堆专用查询面（贵重物等走官方 hooks params）

**液体与进食**:
房间 `resource.water` 为真时可 `fill` 液体容器；`drink` 清空灌装并一次性恢复精力；`consumable` 可 `eat`（一次性恢复气血/精力，`uses` 递减耗尽销毁）。效果均为当次结算，不挂持续 Effect。`resource.grass` / 坐骑喂食未打通。
_Avoid_: 把 drink/eat 当成 Effect 生命周期, 假设草场喂马已可用, 醉酒/持续中毒

**藏书**:
题材包内可检索、选定并付费阅读的书档内容（顶层 `books` + 房间 `library`）；玩家主路径含书架 TOC、书名缩写解析、选书、按章付费阅读与分页展示。官方验收以扬州藏书阁为准。同房挂 `library` 即拦练功（`practice`）；房间旗标可一并声明（见「房间旗标」）。
_Avoid_: 仅用 `details` 书架文案冒充藏书子系统, 通用网文阅读器/外部 URL 拉书

**日间店铺**:
房间声明 `day_shop: true` 表示仅白天营业；加载期编成白天放行的 `entry_guard`（谓词 `is_day`），不是平行的第二套进房系统。
_Avoid_: 与 entry_guard 双轨各写一套夜间逻辑, 本波为日间店新建独立时间子系统

**剧情门**:
相对标准门锁的声明式扩展：可耗钥、未开无向、NPC 在场挡向。挡向可声明可选 `deny_message`（自定义拒走文案）；未声明或空串回退默认「{名}挡住了{方向}方向的去路。」。房间保真批验收以扬州翰林三件套为准。创作者契约路径止于此；运行时改出口走「房间钩子」。
_Avoid_: 与标准门平行的第二套门系统, 把 UGC/创作者契约写成可任意脚本 add_exit/remove_exit, 与「房间钩子经 ctx 改出口」混为一谈

**步行地形精力**:
玩家非骑乘移动时，按目标房 `Terrain.cost`（缺省 1）以 `cost * 2` 扣 `Vitals.jingli_current`；不足则拒走（不因步行引入昏迷）。骑乘时只走坐骑精力/`ability` 规则，与步行消耗互不叠加。无 `Vitals` 的最小场景不扣。
_Avoid_: 步行与骑乘精力双重扣减, 步行耗尽触发 Unconscious, 把步行公式写成契约新字段

**随机 objects 槽位**:
房间 `objects` 槽位可写 `{ random_of: [模板…], count? }`（`count` 缺省 1）；初始生成与 `spawn_scan` 补刷均按 rng 独立抽签（可连抽同一模板）。与出口加载期一次性 `random_of`（落地为固定 `to`）正交，不共用求值函数。
_Avoid_: 把出口 random_of 改成运行时重抽, 与固定「模板键→数量」混写同一槽位, 候选混用物品与 NPC

**场景 includes**:
场景顶层可选 `includes: [<相对路径>, ...]`；加载期先合并被引用文件的 `items`/`npcs` 再解析本文件。路径相对场景文件目录且不得穿出（内容包轨另不得穿出包根）；禁止嵌套 include；被 include 文件仅允许 `items`/`npcs`；合并后模板 id 全局唯一。官方轨与内容包轨均可用。
_Avoid_: 嵌套 include, 用 includes 合并 rooms/player, 跨文件重复模板 id 静默覆盖, 绝对路径或穿出包/场景目录的裸文件系统引用

**房间钩子**:
官方 / 题材包可信 Python 模块上的房间行为入口（`RoomHook` 协议 + 全局注册表）；房间 YAML 只引用 `hooks.hook_id`（+ 可选 `params`）。改世界必须经窄 `ctx`（`RoomHookContext`：增删/隐藏揭示出口、`schedule`、播报、房间自由状态、`move_entity` / `relocate_entity` 等），与 `SkillBehavior` 同信任级。UGC 内容包禁止 `hooks`（加载 / `--validate` / `--strict` 一致失败）。见 ADR-0012。刷怪贵重物门槛等玩法条件走钩子 `params`（如 `bandit_ambush.min_item_value`），不进通用条件 DSL。
_Avoid_: UGC RestrictedPython 沙箱已落地, 钩子直接摸 World 私有结构, 每玩法堆声明式原语代替钩子（本批刻意用钩子防原语膨胀）, 把房间钩子叫成创作者契约级脚本 API, 为贵重物往 conditions.py 加谓词

**窄 ctx（RoomHookContext）**:
只服务房间钩子的轻量外观：绑定当前房间 / 触发实体与只读时段快照，不透出 `World` 私有组件存储。钩子改世界只经其上有限方法。
_Avoid_: 把整个 World 传给钩子, 在钩子里直接摸组件字典

**房间自由状态（RoomFreeState）**:
挂在房间上的自由 `data` / `schedules` 袋；钩子自定义存什么（多步进度、迷途计数、到期戳等），引擎不假设结构。`ctx.schedule` 落在 `schedules`，由钩子 `on_tick` 自查，不新建引擎级通用调度服务。
_Avoid_: 为每个机关新建专用 ECS 组件, 引擎级通用 call_out 调度器（本批未建）

**ON_BEFORE_LEAVE_ROOM**:
引擎事件总线上「离开房间前」的可否决点（镜像 `ON_BEFORE_ENTER_ROOM`）；本批由迷途等钩子的 `veto_leave` 专挂，不是 RoomHook 通用方法族的一员。
_Avoid_: 把 before_leave 做成每个钩子必实现的协议方法, 与进房守卫混成同一事件名

**xingxiu_mechanics**:
官方机制验收切片场景（`engine/data/xingxiu_mechanics.yaml`，无 `manifest`）：十类同构机关（含加载期 `random_of` 与柔丝索 `SkillBehavior`）可玩路径，不是整区星宿地图移植，也不是空能力橱窗；与 `m2_mvp_scene` 分文件、互不掺和。
_Avoid_: m2_xingxiu_mechanics 命名, 把切片包当成 LPC 行为等价验证场, 与扬州 MVP 场景混成必须同一文件

### 交付窗口

**M3 停机加固**:
M3 里程碑宣布可完成后、开启 M4 之前的加固 effort：停机退出标准仅评审 P0（S0）；同一 spec 可含后续 B3 wave（选定的 P1 排期项），但 B3 **不**定义「可宣布停机」。
_Avoid_: M4, 把 P1/P2 或灵感缺口当成停机失败, 把 B3 与 S0 门闩混为一谈

**Pre-M4 引擎房间保真**:
已于 2026-07-22 **落地关闭**的 M4 前 effort（非停机门闩）：风景 / 语义色 / 藏书为硬门闩，日间店与剧情门为本波必做；契约与 GAP 已回写。底稿见 `.scratch/pre-m4-engine-room-fidelity/`。
_Avoid_: 并入 M3 停机加固 S0/B3, 当成 post-MVP backlog, 与 GAP 台账（文档）混为一谈, 未 grill 直接实现, 重开 `placed_in`/`in_room` vs `objects`, 把仍可裁剪项或「本波必做非门闩」项升格为硬门闩, 把藏书误当成仅 `details` 文案, 缺藏书仍宣称 effort 关闭, 本波实装液体子系统, 新字段先透传不进契约, 另建房间保真橱窗包作唯一验收, 关完自动滑入 M4

**Pre-M4 频道/spawn/任务**:
已于 2026-07-22 **落地关闭**（仍属 M4 前窗口、非停机门闩）：同 World 双 `PlayerSession` 测试 seam + Channel（`chat`/`system`）；房间中心 `objects` 放置 + 物品/NPC 槽位补刷（ADR-0010）；YAML `quests.<id>` 旗标状态机（官方 `escort_delivery`）。底稿见 `.scratch/pre-m4-channels-spawn-quest/`。
_Avoid_: 当成已实现的多人联网, 升格为停机门闩, 通用任务脚本引擎, 与房间保真混为一张 spec, 保留 `placed_in`/`in_room` 为权威写法

**Pre-M4 房间钩子 / 星宿机制**:
已于 2026-07-22 **落地关闭**的 M4 前 effort（非停机门闩）：官方可信房间钩子 + `xingxiu_mechanics` 十类机关切片；契约 / GAP / CONTEXT 已回写。底稿见 `.scratch/pre-m4-room-hooks-xingxiu/`。关完仍**不**自动开 M4。
_Avoid_: 并入房间保真改其实现 scope, 本批上 UGC RestrictedPython, 整区星宿移植, 空橱窗包冒充机制切片, 关完自动滑入 M4

**Polishing（打磨抛光）**:
Pre-M4 三批关闭之后、开启 M4 之前的可选命名 effort（与三批 Pre-M4 同级，**不是**新的 M 编号，也**不是** M4 的一部分）：对照 LPC/创作体验收束缺口，经 grill 逐项纳入 scope；**一旦纳入本 effort，不论体量，落地时必须实现**（可拆更细 ticket，不得再悄悄后置出本阶段）。不确定是否纳入时由架构师拍板。关完仍**不**自动开 M4。
_Avoid_: M3.5 / 新里程碑编号, 把打磨项并入 M4 商业化叙事, 未 grill 先改契约或加载器, 纳入后以「太大」为由踢出本阶段, 关完自动滑入 M4
