# 模式研究·WebSocket 网关与会话层（XKX MUD 重构：Python+WebSocket 后端）

## 概述
XKX 现以 MudOS 单进程管 Telnet 长连接，F_MESSAGE 做消息分发、F_DBASE 路径键值存储、heart_beat 2s 驱动战斗、InterMUD 以 UDP+白名单跨服。重构：aiohttp/websockets+uvloop 承载海量 WS 长连接，FastAPI 司 REST 与 JWT 签发；协议 MsgPack 为主、JSON 兜底 UGC 动态内容；心跳用 WS Ping/Pong 叠加应用层心跳与序号断线重连；状态同步复用 F_DBASE 路径键做 snapshot+delta；水平扩展靠 Redis 会话路由表+消息总线转发跨节点 tell/频道；过渡期以 receive_message 抽象为缝，Telnet 渲染 ANSI、WS 发结构化事件。

## 模式
- **连接层选型与分层**：网关连接层用 asyncio+websockets/aiohttp（配 uvloop 加速、SO_REUSEPORT 多 worker 进程）专司海量 WS 长连接与背压管理；FastAPI 仅做 REST/JWT 签发/UGC 管理 API。职责分离，避免 ASGI 框架为超大规模长连接调优不足。对应原 MudOS 驱动单进程管 8888 端口 Telnet 的职责，但拆出独立可扩缩的连接层。
  - 适用性：高并发长连接承载、万级以上并发、网关与业务 API 需独立扩缩容
- **会话认证升级（JWT）**：复刻 LOGIN_OB→BODY_OB 的 exec() 升级语义：连接后先建预认证会话，验密（argon2 替代原 crypt()）后签 JWT（RS256，access 5-15min + refresh 7d），session_id 入 Redis 路由表；token 载 user_id/character_id/roles/world。net_dead() 映射为会话挂起而非销毁。
  - 适用性：多角色多题材、跨分片会话、无状态网关水平扩展
- **心跳保活与断线重连**：WS Ping/Pong（约 20s）保活，叠加应用层心跳携带 last_seq；超时挂起会话，60-300s 重连窗口内凭 token+seq 恢复，服务端 ring buffer 重放错过的 delta。客户端指数退避重连。对应原 heart_beat 2s tick + InterMUD ping 30min/3 retries 的分布式强化版。
  - 适用性：移动弱网、断线恢复、防止误判下线丢失进度
- **消息协议双轨（MsgPack+JSON）**：统一帧封装 {type,version,seq,payload}；结构化游戏消息（命令/战斗/状态）用 MsgPack（紧凑快速、schemaless），UGC/DSL 动态剧情用 JSON（无需 codegen、可读、前端易调）。仅高频战斗在压测瓶颈后局部升级 Protobuf。原 @@@svc||k:v||...@@@ 文本协议与 F_DBASE mapping 天然映射到 JSON/MsgPack。
  - 适用性：兼顾性能与 UGC 灵活、多题材 schema 演进、前端易调试
- **状态同步 snapshot+delta**：直接复用 F_DBASE 路径键（如 family/master_name 式）作为 delta 寻址；进场景/重连发全量 snapshot，变更发 JSON-Patch 风格 {path,op,value}；每会话单调 seq，客户端 ack 版本。dbase 对应持久 snapshot、tmp_dbase 对应易失 delta，语义对齐。
  - 适用性：房间/角色/背包状态同步、断线重放、降低带宽
- **水平扩展与会话路由**：无状态网关节点 behind LB，粘性路由 session_id→gateway；Redis 存 session_id→{node,user,character,world} 映射。跨节点 tell/tell_room/频道经 Redis Pub/Sub 或 NATS 转发，替代单进程 users() 与 tell_object 直调。世界按题材分片。
  - 适用性：大规模分布式部署、跨节点实时消息、多题材世界隔离
- **Telnet 兼容适配层**：保留 receive_message(msgclass,msg) 为渲染抽象缝：Telnet 适配器拼 ANSI 文本流兼容老客户端，WS 适配器序列化为结构化事件；可设桥接器旁路连 MudOS 旁车过渡。这是迁移风险最低的接缝。
  - 适用性：过渡期老客户端、ANSI 与结构化双轨、渐进迁移
- **仿真 tick 保留与解耦**：保留 2s heart_beat 作为确定性仿真步进驱动战斗/回血/NPC；call_out 映射 asyncio 定时任务；网关与仿真解耦后由仿真 worker 按 tick 推进，网关仅转发事件。
  - 适用性：战斗/状态时序一致性、可重放仿真、与原 LPC 心跳语义对齐

## 适用性
- 海量长连接高并发承载（万级以上 WS 并发，网关与业务 API 独立扩缩容）
- 多题材世界分布式分片部署（武侠/大航海/书院/穿越/现代各一 shard，按题材路由）
- UGC 平台动态剧情与 DSL（schema 不固定的用户内容，需 JSON 兜底与无 codegen 协议）
- 断线重连与会话恢复（移动弱网、序号重放、挂起窗口而非直接销毁）
- 跨节点实时消息分发（tell/房间广播/频道订阅需替代单进程 users() 直调）
- Telnet 老客户端平滑过渡（保留 ANSI 文本入口，与结构化事件双轨渐进迁移）

## 权衡
- websockets 库最轻但需自建 HTTP/REST；aiohttp 一体但 WS 调优与超大连接数管理弱于专用库，需取舍
- MsgPack 灵活 schemaless 但无强类型约束；Protobuf 最省带宽但需 codegen，UGC 动态内容难用
- JWT 无状态便于水平扩展但难以即时吊销，需维护 Redis 黑名单/会话注销表
- snapshot+delta 降低带宽与重连开销，但需序号管理、ring buffer 与重放窗口，复杂度上升
- 水平扩展解耦单进程 users()/tell_object 直调，引入消息总线带来延迟与最终一致性代价（频道消息跨节点非瞬时）
- 粘性会话简化路由，但网关节点故障需会话迁移或重放，故障转移复杂
- Telnet 兼容保留老客户端入口，但渲染层双轨维护、ANSI 与结构化事件需长期同步，技术债
- 仿真 tick 与网关解耦提升吞吐，但跨 tick 的命令时序需严格排序，否则战斗结果可重放性受损

## 推荐
- 网关与 API 分离：WS 网关用 aiohttp 或 websockets+uvloop（SO_REUSEPORT 多 worker，单机数万连接），REST/JWT/UGC 用 FastAPI，独立扩缩容
- 会话认证：argon2 验密替代 crypt()，签 JWT（RS256，access 5-15min + refresh 7d），session_id 入 Redis 路由表，吊销走黑名单；token 载 character_id/world 便于跨分片
- 消息协议：默认 MsgPack，UGC/DSL 用 JSON，仅高频战斗压测瓶颈后局部 Protobuf；统一 {type,version,seq,payload} 帧封装，前端按 type 路由
- 心跳重连：WS Ping/Pong 20s + 应用心跳带 last_seq，60-300s 挂起窗口，ring buffer 重放 delta，客户端指数退避（1s→2s→4s→上限 30s）
- 状态同步：复用 F_DBASE 路径键，进场景/重连发 snapshot，变更发 JSON-Patch 风格 delta + 单调 seq；dbase=持久 snapshot、tmp_dbase=易失 delta
- 水平扩展：Redis 存 session_id→{node,user,character,world}，跨节点 tell/频道/房间广播经 Redis Pub/Sub 或 NATS；按题材分世界 shard（武侠/大航海/书院各一）
- Telnet 过渡：以 receive_message(msgclass,msg) 为渲染缝，Telnet 适配器拼 ANSI、WS 适配器发结构化事件；过渡期可桥接器旁路连 MudOS 旁车，降低迁移风险
- 仿真解耦：保留 2s heart_beat 为确定性 tick，仿真 worker 推进、网关转发，断线挂起而非销毁会话；call_out 映射 asyncio 定时任务
- 安全增强：保留 InterMUD 白名单+地址验证思想，网关层加 WS origin 校验、速率限制、per-session 消息配额，防刷屏（原 channel_msg_cnt 防刷机制的分布式版）
