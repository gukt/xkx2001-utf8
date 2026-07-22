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
房间上可 `look` 的非实体描述；YAML 字段为 `details`（键 → 文本）。不占 `objects` 槽位、不可捡取、不是背包/战斗对象。`look` 先匹配同房实体，未命中再查 `details` 键。
_Avoid_: 风景实体, no_get 假物品, 把牌子/对联/书架放进 objects, 把 LPC item_desc 当成必须等价的实体模型, 风景键优先于同房实体, features/scenery/item_desc 作本引擎权威字段名

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
房间级布尔约束（本波：`no_fight` / `no_steal` / `no_sleep_room`），任意房间可在 YAML 声明。只对**已有命令面**生效：`no_fight` 拦 `attack`/`kill`；尚无对应命令的旗标可声明并校验，但不假装已禁。藏书阁另以同房规则拦 `practice`（及日后打坐类命令）。
_Avoid_: 为让旗标「成真」而本波补齐 steal/睡眠子系统, 把旗标逻辑硬编码成单一房间特例

**藏书**:
题材包内可检索、选定并付费阅读的书档内容（顶层 `books` + 房间 `library`）；玩家主路径含书架 TOC、书名缩写解析、选书、按章付费阅读与分页展示。官方验收以扬州藏书阁为准。同房挂 `library` 即拦练功（`practice`）；房间旗标可一并声明（见「房间旗标」）。
_Avoid_: 仅用 `details` 书架文案冒充藏书子系统, 通用网文阅读器/外部 URL 拉书

**日间店铺**:
房间声明 `day_shop`（或等价一等字段）表示仅白天营业；加载期编成夜间拒入的 `entry_guard`（依赖已有 `is_night`），不是平行的第二套进房系统。
_Avoid_: 与 entry_guard 双轨各写一套夜间逻辑, 本波为日间店新建独立时间子系统

**剧情门**:
相对标准门锁的声明式扩展：可耗钥解锁、未开时无该向可走出口、可声明「某 NPC 在场则挡某向」。房间保真批验收以扬州翰林后院（或同构房）三件套为准。
_Avoid_: 与标准门平行的第二套门系统, 把 UGC/创作者契约写成可任意脚本 add_exit/remove_exit, 与「房间钩子经 ctx 改出口」混为一谈

**房间钩子**:
官方 / 题材包可信 Python 模块上的房间行为入口；经窄 `ctx` API（如增删出口、调度延时、房间播报）改世界，与 `SkillBehavior` 同信任级。UGC 内容包禁止钩子。见 ADR-0012。
_Avoid_: UGC RestrictedPython 沙箱已落地, 钩子直接摸 World 私有结构, 每玩法堆声明式原语代替钩子（本批刻意用钩子防原语膨胀）, 把房间钩子叫成创作者契约级脚本 API

**xingxiu_mechanics**:
官方机制验收切片场景（计划 `engine/data/xingxiu_mechanics.yaml`）：用同构机关证明房间钩子等能力，不是整区星宿地图移植，也不是空能力橱窗。
_Avoid_: m2_xingxiu_mechanics 命名, 把切片包当成 LPC 行为等价验证场, 与扬州 MVP 场景混成必须同一文件

### 交付窗口

**M3 停机加固**:
M3 里程碑宣布可完成后、开启 M4 之前的加固 effort：停机退出标准仅评审 P0（S0）；同一 spec 可含后续 B3 wave（选定的 P1 排期项），但 B3 **不**定义「可宣布停机」。
_Avoid_: M4, 把 P1/P2 或灵感缺口当成停机失败, 把 B3 与 S0 门闩混为一谈

**Pre-M4 引擎房间保真**:
已于 2026-07-22 **落地关闭**（仍属 M4 前窗口、非停机门闩）：硬门闩三项（房间风景 `details`、语义色 ADR-0011、完整藏书）+ 本波必做非门闩（`day_shop`、剧情门翰林三件套）+ 契约/GAP 加法回写；验收扩展官方扬州 MVP，不新建橱窗包。**后置**：液体灌装/饮用、防拐带。**放置模型不在本 effort**：兄弟批 + ADR-0010。底稿见 `.scratch/pre-m4-engine-room-fidelity/`。**不**因关闭而自动开 M4。
_Avoid_: 并入 M3 停机加固 S0/B3, 当成 post-MVP backlog, 与 GAP 台账（文档）混为一谈, 未 grill 直接实现, 重开 `placed_in`/`in_room` vs `objects`, 把仍可裁剪项或「本波必做非门闩」项升格为硬门闩, 把藏书误当成仅 `details` 文案, 缺藏书仍宣称 effort 关闭, 本波实装液体子系统, 新字段先透传不进契约, 另建房间保真橱窗包作唯一验收, 关完自动滑入 M4

**Pre-M4 频道/spawn/任务**:
已于 2026-07-22 **落地关闭**（仍属 M4 前窗口、非停机门闩）：同 World 双 `PlayerSession` 测试 seam + Channel（`chat`/`system`）；房间中心 `objects` 放置 + 物品/NPC 槽位补刷（ADR-0010）；YAML `quests.<id>` 旗标状态机（官方 `escort_delivery`）。底稿见 `.scratch/pre-m4-channels-spawn-quest/`。
_Avoid_: 当成已实现的多人联网, 升格为停机门闩, 通用任务脚本引擎, 与房间保真混为一张 spec, 保留 `placed_in`/`in_room` 为权威写法

**Pre-M4 房间钩子 / 星宿机制**:
M4 前、房间保真 **整包关闭之后** 开工的兄弟 effort：官方可信房间钩子 + `xingxiu_mechanics` 硬门闩验收（动态出口/时限、岔路随机出口、多步状态机、迷途、jump/climb、时段秘道、磁力、劫匪刷拦、杀令介入、柔丝索捕获）。骨架与 ADR-0012 已落；实现未开。底稿见 `.scratch/pre-m4-room-hooks-xingxiu/`。
_Avoid_: 并入房间保真改其实现 scope, 本批上 UGC RestrictedPython, 整区星宿移植, 未等保真关闭就 /implement, 自动开 M4, 空橱窗包冒充机制切片
