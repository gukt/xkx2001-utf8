# 模式研究·Actor 模型与分布式游戏服务器（XKX/LPC MUD 重构为 Python+WebSocket 分布式后端）

## 概述
XKX 的 LPC 对象世界与 Actor 模型高度同构：每个房间/NPC/玩家/物品天然是封装状态(dbase)与行为(feature)的 Actor，call_other/find_object 用路径寻址即位置透明的雏形，previous_object() 即消息发送者，heart_beat/call_out 即定时自消息，tell_room/message 即位置相关广播，move() 即对象迁移，Daemon 单例即服务 Actor，master.c 的 connect/error_handler/valid_* 即驱动层 supervisor 与安全边界，save_object/.o+autoload+clean_up 即虚拟 actor 的钝化/激活。已有架构文档明确指出 Daemon 单例模式“无法简单分布到多进程/服务器”、MAX_USERS 230 上限——这正是 Actor 模型要解决的：位置透明、supervision 容错、跨节点分布与节点迁移。InterMUD(I3/UDP)已是站点级 federation 先例，但单 MUD 内仍单进程单地址空间，需把“站点间 federation”与“集群内 actor 分布”分层。落地建议以 Python asyncio 自研轻量 actor 运行时为主干，借鉴 Orleans 虚拟 actor 语义，Ray 作为可选执行后端；战斗回合的强一致与 random() 随机性是分布式化的关键难点。

## 模式
- **虚拟 Actor（Virtual Actor / Grain）：每实体一 Actor，按 ID 寻址、按需激活**：把每类游戏实体建模为虚拟 Actor（借鉴 Orleans Grain）：按稳定 ID 寻址、按需激活、空闲钝化、崩溃后重建。XKX 已具备雏形——对象通过文件路径（base_name）标识，clean_up/swap/reset 三机制（config.xkx: time to clean up=180, time to swap=120, time to reset=1800）本质就是钝化与重置；save_object/restore_object 的 .o 文件 + autoload 就是状态落盘与恢复。重构时把 LPC 路径（如 /d/hangzhou/village）升格为 Actor address（如 world://hangzhou/village#<clone-uuid>），LPC 的 default_ob 原型模式对应 Actor 的'蓝图+实例'。
  - 适用性：XKX 房间出口用路径字符串连接（如 /home/gukt/github/xkx2001-utf8/d/hangzhou/village.c 的 set("exits", __DIR__"haidi")），NPC 经 set("objects", path) 由 make_inventory 克隆。直接迁移为 world://zone/room#obj 形态：本地调用与跨节点调用同形，房间图天然可分片。
- **位置透明通信：以地址替代指针，call_other/find_object 升级为 Actor 引用**：XKX 的 call_other(dest,"??") 加载并返回对象、find_object(path) 按路径定位——这已是位置透明的雏形，对象引用本质是路径而非指针。Actor 天然延续此模型：所有交互经消息投递到 address，运行时决定本地直投还是跨节点转发。重构要点：禁止在 Actor 间传递裸对象指针，只传 address 或值快照（对应 LPC '对象引用不持久化，save 时变 0' 的限制恰好吻合）。
  - 适用性：直接复用 call_other/find_object 的语义契约。跨节点时把 find_object(path) 改为 ask(address) 解析到节点位置；缓存无效时由 placement service 重定向。
- **Supervision 树：把 master.c 的 error_handler 与 Daemon 预加载提升为分层容错**：XKX 的 /adm/daemons/ 全是单例服务对象，由 master.c 的 epilog()/preload 预加载、create() 初始化、error_handler() 兜底——这已是 supervision 树的雏形。Actor 模型将其形式化：玩家/NPC Actor 挂在 region supervisor 下，region 挂在 world root 下；Daemons 映射为顶层 Service Actor（LOGIN/COMBAT/CHANNEL/NATURE/CHAR/MONEY/SECURITY）。父 Supervisor 决定子 Actor 失败时的重启策略（one-for-one / all-for-one），把 LPC '一个对象 error 由 error_handler 收尾'升级为'崩溃隔离 + 自动恢复'。
  - 适用性：把 LOGIN_D/COMBAT_D/CHANNEL_D/NATURE_D/SECURITY_D 映射为顶层单例 Service Actor。SECURITY_D 的 valid_write/valid_read/valid_cmd 对应 Actor 的 capability 检查，可前置到消息网关。
- **位置迁移：move() 对应 Actor relocation / 引用代理**：玩家走房间、物品被拾取、坐骑/船只移动都是对象在容器间迁移。XKX move()（/home/gukt/github/xkx2001-utf8/feature/move.c）会改环境、更新负重链、触发新房间 init。Actor 模型下，玩家 Actor 可随其物理位置迁移到承载目标 region 的节点（迁移），或保持不动、仅其'位置引用'指向新房间 Actor（代理）。前者降低后续交互延迟、适合长期停留；后者实现简单、适合频繁切换。
  - 适用性：迁移与 LPC move() 行为一致（room.c 的 move 触发 add_encumbrance 链、进入触发 init/look）。建议把玩家 Actor 与其当前 region 强绑定，跨 region 时先在目标节点激活再注销源节点，保证消息不丢。
- **区域分片（Region Sharding）：虚拟世界跨节点拓扑**：房间图按区域（zone/region）分片到不同节点，区域内房间 Actor 同节点亲和以减少跨节点往返。XKX 房间经 exits 路径串成图，地理上天然分区（d/hangzhou/、d/village/ 等子目录已是边界）。节点宕机时该 region 的房间 Actor 在其他节点重新激活（虚拟 Actor 的核心优势——无状态丢失感知，因状态来自持久层）。
  - 适用性：按地理大区切分（d/ 下已有 hangzhou/village/hengshan 等天然分区）。同一 region 房间/玩家同节点，跨 region 移动时迁移玩家 Actor 或走代理。UGC 多题材世界每个题材=独立 region 子树，天然多租户隔离。
- **消息广播与位置相关路由：tell_room/message 的 Actor 化**：XKX 的 tell_room/message（/home/gukt/github/xkx2001-utf8/adm/simul_efun/message.c）向房间内 inventory 广播，receive_message 按 subclass（channel/outdoor/weather）过滤、in_input 时暂存 msg_buffer——这是'位置相关广播+订阅过滤'。Actor 模型下房间 Actor 维护 occupants 集合，广播即遍历 occupants 各发一条消息；玩家 Actor 持订阅兴趣（在哪些 channel、是否户外），收消息时自过滤。同节点广播高效，跨节点则房间 Actor 向远端玩家 Actor 逐条投递（或批量）。
  - 适用性：对应 tell_room/tell_object/message_vision。跨节点时房间 Actor 转发消息给远端玩家 Actor 的 WebSocket 会话 Actor。注意原 LPC message 的 subclass 路由（channel/outdoor/weather）可保留为消息标签。
- **回合仲裁集中化：COMBAT_D 作为协调 Actor，避免分布式事务**：XKX 战斗由各 char 的 heart_beat 调用 COMBAT_D->fight/do_attack（/home/gukt/github/xkx2001-utf8/adm/daemons/combatd.c），一回合内多次 random() 判定且双向改 me/victim 状态——这是强一致、有副作用的串行计算。Actor 化后，战斗回合应交给单个仲裁 Actor（如 region 的 combat coordinator，或战斗发起方所在节点）串行裁决，避免双端 Actor 分布式来回。即：战斗是'会话'而非'无状态请求'。
  - 适用性：COMBAT_D→CombatCoordinator actor（按 region 或战斗实例）；CHAR_D→种族/属性计算 service actor；CHANNEL_D→跨节点 pub/sub 总线。注意战斗大量 random() 需确定性 RNG（见 tradeoffs）。
- **定时与心跳：call_out/heart_beat 作为 Actor 的定时自消息**：XKX 的 call_out(func, delay) 与 set_heart_beat(1) 是定时自消息。Actor 模型用周期性 self-message（定时器）或全局 tick 调度器向活跃 Actor 投递 tick 消息。condition 系统（feature/condition.c 的 update_condition 经 find_object(CONDITION_D(...)) 动态加载外部守护进程、返回 CND_CONTINUE 标志）天然映射为'状态效果 Actor'挂在角色下，按 tick 自衰减。
  - 适用性：F_CONDITION 的 find_object(CONDITION_D(cnd)) 动态加载、返回 CND_CONTINUE 控制——天然就是按需激活与生命周期标志。F_AUTOLOAD 的 base_name+param 恢复物品是引用重建。
- **InterMUD federation 先例：站点级分布 vs 进程内分布的分层**：XKX 的 dns_master（/home/gukt/github/xkx2001-utf8/adm/daemons/dns_master.c）实现 I3 协议，跨 MUD 用 UDP 包 @@@service||k:v@@@ 路由到 services/ 目录处理——这是站点级 federation 先例。但单 MUD 内仍是单进程单地址空间，不解决进程内分布。重构时把'站点间 federation'（I3，保留为跨集群/跨 UGC 世界互通）与'集群内分布'（Actor 集群，节点间 actor 消息）分层。
  - 适用性：I3 的 federated 模型可演进为跨集群/跨 UGC 世界的 federation，复用其服务路由与白名单安全思路。但单集群内部不应再走 I3，改用 Actor 内部消息。

## 适用性
- 最契合：房间/区域、NPC、玩家、物品这类有状态、可寻址、需按需激活与持久化的实体——LPC 的 dbase+call_other+save_object+clean_up 已是其半成品
- 契合：跨节点移动的实体（玩家、坐骑、船只 inherit/room/ship.c）——迁移天然映射 Actor relocation
- 契合：UGC 多题材世界——每份用户 DSL 剧情=一个独立 region 子树+独立 supervision，天然隔离与回收
- 需谨慎：高频强一致双写交互（同房间多人战斗 COMBAT_D 回合）——应保证参与者同节点亲和或集中到 region actor，避免分布式事务
- 不适用：纯无状态请求/回复（Web 登录、静态查询、排行榜）——这类走传统微服务/HTTP+缓存更简单，避免过度 Actor 化
- 不适用：海量低状态对象的批量离线计算（地图生成、剧情编排）——用 Ray task 或批处理管道，而非长生命周期 actor
- 前提条件：必须先确立确定性的随机源与可回放的事件日志，否则分布式下调试与反作弊不可行

## 权衡
- 位置透明带来延迟：跨节点 actor 消息有网络往返（毫秒级），而 LPC 单进程 call_other 是纳秒级。需用区域亲和把高频交互（同房间战斗/聊天）钉在同节点，跨节点仅用于移动与全局广播。
- 战斗一致性与分布式事务：combatd.c 一回合内多次 random() 且双向改 me/victim 状态。若双方 actor 分处不同节点，回合需分布式锁或两阶段提交，代价高。权衡：保证战斗参与者同节点亲和，或将整场战斗托管到单一 coordinator actor 串行裁决（牺牲并行换一致）。
- 随机数确定性：分布式下 random() 来源不一致会导致回放/反作弊失效。需为每场战斗或每个 region 注入 seeded RNG，回合事件写日志可回放；LPC 原生 random 无此约束，是新增复杂度。
- 自研 vs Ray：自研 asyncio actor 掌控游戏语义（tick 顺序、消息优先级、确定性）但需自建 supervision/placement/迁移/持久化，工作量大；Ray 开箱即用分布式与容错，但偏向 ML 工作负载，actor 延迟与调度策略对实时游戏需实测，且其 actor 模型偏粗粒度（远程对象而非游戏实体）。建议主循环自研、重计算/UGC 生成用 Ray。
- Akka/Orleans 非 Python：Orleans 的 Virtual Actor(Grain) 语义最贴合 MUD（按需激活、placement、内置持久化），但 .NET 栈；Akka 成熟但 JVM。引入它们意味着跨语言运维与团队栈分裂，不适合纯 Python 目标。可用 Proto.Actor 等跨语言方案折中，但生态不及原生。
- 虚拟 actor 激活抖动：按需激活首次访问有冷启动（加载状态、重建引用），LPC 的 clean_up/swap 也有此问题但单进程内开销小。需预热热点 region、缓存活跃玩家状态。
- 迁移 vs 代理：迁移 Player Actor 到目标节点降低延迟但迁移期间消息需缓冲重放；保持代理则长期多一跳。频繁移动场景（如连续跑图）宜迁移+批量，静态场景宜代理。
- UGC 多租户隔离：每个用户 DSL 世界是独立 region 子树+supervision，崩溃不影响他人——但需要严格的资源配额（actor 数、tick 预算、内存），否则一个失控剧情拖垮节点。LPC 原生无此隔离，是新增能力也是新增运维负担。

## 推荐
- 核心选型：以 Python asyncio 自研轻量 Actor 运行时为主干，不直接用 Akka/Orleans（非 Python 增加跨语言成本），借鉴 Orleans Virtual Actor 语义（按 ID 寻址、按需激活、钝化/激活、placement）。Ray 可作为可选的执行后端与 ML/UGC 生成工作负载，但游戏主循环 actor 建议自研以掌控延迟、消息序与确定性。
- Actor 分层建议：顶层 Service Actor（LOGIN/COMBAT/CHANNEL/NATURE/CHAR/MONEY/SECURITY，对应 /home/gukt/github/xkx2001-utf8/adm/daemons/ 各单例）；中层 Region Supervisor（按 d/ 子目录切分，如 hangzhou/village）；底层 Room/NPC/Player/Item Actor。Supervision 策略：玩家/房间 one-for-one，region all-for-one。
- 地址与寻址：定义 world://<region>/<room>[#<obj-uuid>] 统一地址，替代 LPC 路径。本地为对象引用、跨节点为透明代理；find_object(path)→resolve(addr)。禁止 actor 间传裸引用，仅传 addr 或值快照（沿用 LPC save 不保留引用的安全特性）。
- 迁移与亲和：玩家进入新 region 时迁移其 Player Actor 到目标节点（先激活后注销，消息日志重放保证不丢）；同房间战斗参与者保持同节点亲和，把 COMBAT_D 实例化为 region/战斗级 Coordinator Actor 串行裁决回合，避免分布式事务。
- 确定性随机：为每场战斗/每个 region 分配独立 seeded RNG，回合结果写 append-only 事件日志，支持回放与反作弊审计——这是分布式下调试与公平性的前提。
- 持久化与激活：玩家状态 save_object .o→结构化存储（PostgreSQL+Redis），actor 钝化时落盘、激活时恢复，复用 autoload 机制重建物品引用；房间采用'蓝图+实例'（对应 default_ob），冷数据上对象存储热数据进内存。
- 命令系统：command_hook→Player Actor 接收输入消息，经权限 Actor（SECURITY_D 语义）校验后路由到 Command Actor；WebSocket 网关只做协议层，玩家 Actor 为唯一权威状态拥有者。
- UGC/DSL：剧情 DSL 编译生成 region 子树 + room/npc actor 蓝图，每个题材世界（武侠/大航海/书院等）独立 supervision 与资源配额，Actor 边界即租户隔离边界；AI Agent 协作创作作为向 region 投递'创作消息'的 actors。
- 迁移路径（增量）：阶段一单进程 asyncio actor 重写核心循环验证语义；阶段二加多节点 + placement + 迁移；阶段三接 Ray/对象存储做 UGC 与 ML；避免一次性全量重写，先以 actor 适配器封装现有 LPC 行为逐子系统替换。
- 不要过度 Actor 化：无状态 HTTP（登录、查询、排行榜）、批量计算（地图/剧情生成）走传统微服务/批处理；仅在'有状态、可寻址、需激活与迁移'的实体上用 actor，保持架构分层清晰。
