# 调研：Evennia 技术架构与 mud_engine 全方位对比（2026-07-23）

> **范围**：Evennia **6.1.0**（`~/github/evennia`，`evennia/VERSION.txt`）源码 + 官方文档（`docs/source/`）第一手；本仓库 `engine/src/mud_engine/`、`docs/adr/`、`CLAUDE.md` / `CONTEXT.md` / `PROGRESS.md` / `docs/creator-contract-v0.md`。  
> **目标问题**：Evennia 作为成熟 Python MU\* 框架，其架构与实践中哪些思想可迁移到本项目的题材无关内核 + UGC 创作层，哪些必须避开（与架构不变量冲突）？  
> **非目标**：不建议「换用 / 嵌入 Evennia」；不做 LPC 行为等价；不依赖博客/二手综述；不编造性能数字。  
> **关联**：本项目不变量见 [CLAUDE.md](../../../CLAUDE.md)；单进程单 World [ADR-0009](../../../docs/adr/0009-single-process-single-world.md)；UGC 声明式创作面 [ADR-0005](../../../docs/adr/0005-m3-ugc-loop-creation-surface.md)；引擎不做编辑器 [ADR-0006](../../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)；内存 + JSON 存档（不变量 §1）；频道/登录单机阶段边界 [ADR-0008](../../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md)。  
> **第一手来源清单**：见 §9 附录。

---

## 1. 摘要（给架构师）

**Evennia 是什么**：面向任意题材的 **Python MU\* 工具箱/服务器**（非成品游戏）。默认提供 Portal+Server 双 Twisted 进程、Django ORM 持久化、Typeclass 对象模型、CommandSet、Lock DSL、Channels、Scripts/Ticker、Webclient/Website/可选 REST，以及 `mygame/` 与库代码分离的 game_template。官方自称 bare-bones：**不附带战斗规则 / 技能系统 / 种族职业**——出厂是可聊天可行走的「talker」([Evennia-Introduction.md](file:///home/gukt/github/evennia/docs/source/Evennia-Introduction.md) L16–28)。版本 **6.1.0**（`evennia/VERSION.txt`），Python ≥3.12，Django 6.x + Twisted 24.x（`pyproject.toml`）。

**对本项目最有价值的 5 个思想**（迁移形态，非抄代码）：

1. **引擎库 vs 游戏目录分离**（`evennia/` 包 + `evennia --init mygame`）→ 强化「`mud_engine` 包 vs 题材包目录」边界，避免官方场景 YAML 与引擎源码纠缠。  
2. **Session / Account / Character 三层分离** → M4/多人阶段的会话模型蓝图；当前单机 CLI 可先留 seam。  
3. **CommandSet 可合并状态机**（黑暗房间替换 `look` 等）→ 评估是否用「可叠层命令表」替代部分 `if` 丛林（昏迷/骑乘/战斗态）。  
4. **Lock 字符串 DSL + fail-closed** → 题材包可声明的权限面（门/出口/命令），与现有 `entry_guard` / 房间旗标可对照。  
5. **Prototype 字典驱动生成** → 与本仓库 `objects:` 放置 + 模板键思路同构；可借鉴「原型继承 / 标签检索」元数据形状，而不引入 OLC。

**最该避开的 5 个坑**：

1. **Django ORM 同步路径绑在游戏逻辑上**——tick/命令路径上隐式 `save()` / Attribute 读写会阻塞整个 reactor（见 Async-Process 文档对单线程幻觉的说明）。与本项目「内存权威 + 周期 JSON 快照」不变量正面冲突。  
2. **Typeclass 全局唯一类名 + DB 强耦合**——概念重、调试成本高；本项目已选 ECS-ish 组件，勿回退为「一切皆 Django 行」。  
3. **创作面默认是 Python Typeclass / 游戏内 OLC**——与 ADR-0005/0006「包外声明式 + 引擎不做编辑器」冲突；Evennia Prototype/OLC 是 builder 友好，不是 UGC 包契约。  
4. **双进程 Portal/Server + Web 全家桶**——对「单机 1000/100、不上 K8s」的 MVP 运维面过重；热重载价值在联网多人开发循环，当前 CLI 收益低。  
5. **核心无战斗/技能**——战斗在 contrib/教程（如 `turnbattle`、`evadventure`）；若「学 Evennia」意味着把战斗推到题材包自建，会与 ADR-0004「战斗流程框架归引擎」对撞。

**与当前 `mud_engine` 的结构性差异（一句话）**：Evennia 是「**联网 MU\* 运行时平台**（协议/账号/DB/Web 完整）」；`mud_engine` 是「**题材无关可玩内核 + 声明式内容包契约**（内存 World、YAML pack、战斗/技能/钩子已在引擎侧落位）」。重叠在「命令/房间/对象/定时」抽象层；分叉在持久化、创作面、进程模型与「游戏逻辑厚度」。

---

## 2. Evennia 鸟瞰与定位

| 维度 | Evennia 官方自我定位 | 证据 |
|---|---|---|
| 产品形态 | 库 + 服务器，不是游戏 | `README.md` L5–13；`AGENTS.md` L5；`.agents/docs/core-beliefs.md`「toolkit, not a game」 |
| 出厂玩法 | talker：建房、走、聊；无战斗 | `Evennia-Introduction.md` L26–28、L54–58 |
| 扩展哲学 | 游戏代码在 `mygame/`；题材系统进 `contrib/` | `game_template/`；`Contribs-Overview.md` |
| 运行时 | Portal（协议）+ Server（游戏+DB）+ 同进程 Web | `Evennia-In-Pictures.md` L11–22；`Portal-And-Server.md` |
| 持久化 | Django ORM；默认 SQLite 文件 | `Choosing-a-Database.md`；`settings_default.py` `DATABASES` |
| 版本/栈 | 6.1.0；Python≥3.12；Django≥6.0.2；Twisted≥24.11 | `VERSION.txt`；`pyproject.toml` |

Evennia 的「题材无关」是 **框架层不加规则**；本项目的「题材无关」是 **内核提供可替换战斗/技能/钩子接缝 + 官方轻量武侠包证明**（[ADR-0004](../../../docs/adr/0004-combat-effects-boundary-engine.md)、[CLAUDE.md](../../../CLAUDE.md) 一句话）。二者都「不绑死单一题材」，但厚度相反：Evennia 薄游戏逻辑、厚平台；`mud_engine` 厚可玩内核、薄联网平台。

---

## 3. 技术架构深挖（分层 + 关键路径）

### 3.1 总体分层

```
Internet
  → Portal (twistd)：Telnet / Websocket / SSH …
       ↕ AMP（同机）
  → Server (twistd)：SessionHandler → CmdHandler → Typeclassed 实体
       ↕ Django ORM
  → SQLite / PostgreSQL / MySQL
  → 同 Server 进程：Django Webserver（网站 + webclient + 可选 REST）
```

| 层 | 职责 | 关键路径 / 符号 |
|---|---|---|
| Portal | 协议、连接节流、reload 时保连接 | `evennia/server/portal/`；文档 `Components/Portal-And-Server.md` |
| AMP 桥 | Portal↔Server 会话同步 / 消息 | `sessionhandler.py` 中 `amp.SRELOAD` / `send_MsgServer2Portal` 等 |
| Server | 游戏逻辑、命令、DB | `evennia/server/server.py`、`service.py` |
| Session | 连接会话（Portal/Server 各一份） | `server/session.py`、`serversession.py`、`sessionhandler.py` |
| Account / Object | 账号 vs 世界内实体；puppet | `accounts/`、`objects/`；文档 `Evennia-In-Pictures.md` L71–79 |
| Commands | CmdSet 合并 → 解析 → `Command.func` | `commands/cmdhandler.py`（模块 docstring L7–26；`cmdhandler` L503+） |
| Typeclass / DB | `ObjectDB` 行 + `db_typeclass_path` | `objects/models.py`；`typeclasses/models.py` |
| Scripts / Tickers | 定时与系统态容器 | `scripts/`；`TICKER_HANDLER` |
| Comms | Channel、Msg | `comms/` |
| Web | website / webclient / API | `web/`；`Components/Web-API.md` |

### 3.2 运行时与并发模型

| Claim | 证据 |
|---|---|
| Portal 与 Server 是**两个** `twistd` 进程 | `Portal-And-Server.md` L17–19；`.agents/docs/architecture.md` L3–10 |
| Server 异步，基于 Twisted | `Evennia-In-Pictures.md` L20；`cmdhandler.py` import `reactor` / `inlineCallbacks` |
| 单进程多用户靠协作式切换；长同步函数会卡住所有人 | `Concepts/Async-Process.md` L28–29 |
| `run_async` **仍在同一线程**，重 CPU 仍阻塞 | `Async-Process.md` L105–107（官方 warning） |
| `utils.delay` / `@interactive` 用于异步等待 | 同文档 L32–79 |
| Portal 连接速率 / 命令速率限制 | `settings_default.py`：`MAX_CONNECTION_RATE=2`、`MAX_COMMAND_RATE=80`（约 L268–278） |

**对本项目的含义**：Evennia 的「异步」是 **Twisted 事件循环上的非阻塞 I/O**，不是多线程游戏仿真。任何在命令/ticker 路径上的同步 Django 写库，本质上与「卡住 reactor」同类风险。`mud_engine` 当前是同步单线程 CLI（`cli.run_repl` → `execute_line` → `tick_loop.advance`），刻意简单；若未来上多人网络，应先设计「内存态权威、IO 边界清晰」，而不是直接照搬 Django-on-reactor。

### 3.3 Typeclass 与 Django ORM

继承关系（文档图，`Typeclasses.md` L9–35）：

```
TypedObject
  → AccountDB / ScriptDB / ChannelDB / ObjectDB   ← Django models（表）
      → DefaultAccount / DefaultScript / … / DefaultObject
          → mygame typeclasses.Account / Character / Room / Exit …
```

| Claim | 证据 |
|---|---|
| 一行 DB ↔ 一个 Typeclass 实例；行为由 `db_typeclass_path` 决定 | `Evennia-In-Pictures.md` L45–57；`objects/models.py` 注释 L5–14 |
| `ObjectDB` 核心字段：`db_account`、`db_location`、`db_home`、`db_destination`、`db_cmdset_storage` | `objects/models.py` L214–270 |
| Attribute 存任意可序列化 Python（键值扩展） | `Evennia-In-Pictures.md` L61–67；`typeclasses/attributes.py` |
| Typeclass **全局类名唯一**；不宜随意重载 `__init__` | `Typeclasses.md` L48–66 |
| Contents 有缓存，避免 cmdhandler 频繁查库 | `objects/models.py` `ContentsHandler` L30–35 |
| idmapper 内存缓存上限（默认 400MB）与经验对象数表 | `settings_default.py` L250–267：`IDMAPPER_CACHE_MAXSIZE = 400` |
| 多进程访问时 aggressive Attribute 缓存可能不同步 | `Settings-Default.md` / settings 注释约 L645–651：`TYPECLASS_AGGRESSIVE_CACHE` |

**数据流（创建实体）**：`evennia.create_object(...)` → 插入 `ObjectDB` 行 → 按 `typeclass_path` 实例化 → `at_object_creation` 钩子。之后属性读写经 Attribute handler，常触发持久化。

### 3.4 命令解析与 CommandSet

`cmdhandler.py` 顶部 docstring 给出完整流水线（L7–26）：

1. 分析 caller 类型  
2. 收集 CmdSet：同房对象 / 自身 / Account  
3. **合并**为当前 CmdSet  
4. 空输入 / 多匹配 / 无匹配 → 系统命令  
5. `parse()` → `func()`（Twisted deferred）

| Claim | 证据 |
|---|---|
| 合并语义类似集合论，可临时覆盖（如黑暗房间的 `look`） | `Evennia-In-Pictures.md` L105–113 |
| 合并结果有 LRU 缓存 | `cmdhandler.py` L51–61；`CMDSET_MERGE_CACHE_MAXSIZE` |
| 默认命令按类目分文件 | `commands/default/`：`general.py`、`building.py`、`comms.py`… |
| 游戏侧挂载点 | `game_template/commands/` + settings 中的 cmdset 路径 |

对比 `mud_engine`：`parsing.execute_line` → `DeterministicParser` → `Intent` → `commands.execute`（动词注册表）。有命令级 before/after 与领域事件（`commands.py` 模块 docstring L21–30），**无**「按对象动态合并多 CmdSet」的一等机制；昏迷等用 `UNCONSCIOUS_BLOCKED_VERBS` 黑名单式拦截（`death_flow` / `commands`）。

### 3.5 Lock / 权限

| Claim | 证据 |
|---|---|
| 几乎所有实体经 lock 访问；默认 lockdown | `Locks.md` L3–7；`core-beliefs.md`「Fail closed」 |
| Lockstring：`access_type: lockfunc() AND/OR …` | `Locks.md` L48–55 |
| 常用 access_type：`cmd`、`control`、`get`、`view`、`traverse`… | `Locks.md` L68+ |
| 实现 | `evennia/locks/lockhandler.py`、`lockfuncs.py` |
| 与 Permissions（组/层级）配合 | `Components/Permissions.md` |

对比 `mud_engine`：尚无通用 Lock DSL；有 `entry_guard`、房间旗标（`no_fight` 等）、门 `Doors`、剧情 `block_exits`、可信钩子内条件——**按领域散落**，非统一字符串求值器。

### 3.6 Scripts / Tickers / 定时

| 机制 | 用途 | 证据 |
|---|---|---|
| Script（Typeclass） | OOC 系统态容器 + 可选 `at_repeat` 定时 | `Scripts.md` L7–11 |
| `TICKER_HANDLER` | 多对象订阅同一间隔，避免每对象一 Script | `TickerHandler.md` L12–15、L19–26 |
| `utils.delay` / TaskHandler | 单次延迟 | `Async-Process.md`；`scripts/taskhandler.py` |
| OnDemand / Monitor | 惰性/监视更新 | `scripts/ondemandhandler.py`、`monitorhandler.py` |

Evennia **没有**强制全局 heartbeat；是否 tick 由游戏自定（`TickerHandler.md` L7–8）。  
`mud_engine`：**显式** `TickLoop`（`tick.py`）——CLI 每命令 `advance()`，分发 `on_tick` 后按间隔 `save_fn`；与命令路径职责分离（模块 docstring L8–11）。

### 3.7 通讯：Channels、Msg、房间消息

| 能力 | Evennia | 证据 |
|---|---|---|
| Channel 订阅聊天 | 成熟；`channel` 命令统一入口（1.0 起不用每频道一命令） | `Channels.md` L24–27、L30–55 |
| Msg | 持久化私信/邮件类消息对象 | `Msg.md` L3–9 |
| 房间 say/emote | 默认命令集（objects 上 msg） | `commands/default/general.py`（未逐行展开） |
| Account 与 Object 都可订频道 | `Channels.md` L10–12 |

对比 `mud_engine`（`messaging.py`）：

- `room_say`：同房广播 + `on_hear_say`  
- 薄 Channel：预置 `chat` / `system`（`CHANNELS` dict L41–44）；`publish_channel`  
- **非**联网多人；ADR-0008 澄清 Pre-M4 假多人 seam ≠ 登录里程碑  

### 3.8 Prototypes / Spawner

| Claim | 证据 |
|---|---|
| Prototype = dict 模板，spawn 出 Object | `Prototypes.md` L9–17 |
| 支持 `prototype_parent` 继承、attrs/tags/locks | `Prototypes.md` L48–73 |
| 游戏内 OLC/`spawn` 供 builder | `Prototypes.md` L21–23 |
| 实现 | `evennia/prototypes/spawner.py`、`prototypes.py` |

对比：`mud_engine` 的「模板」是场景 YAML 的 `items.*` / `npcs.*` + 房间 `objects:` 数量槽（ADR-0010）；加载期实例化（`scene_loader`），另有 `spawners` / `item_spawners` 运行时补刷。无游戏内 OLC（符合 ADR-0006）。

### 3.9 Webclient / Website / REST

| 组件 | 说明 | 证据 |
|---|---|---|
| Website + Webclient | 默认随 Server 起；localhost:4001 | `README.md` L30–35；`Components/Webserver.md` / `Webclient.md` |
| REST API | 可选 `REST_API_ENABLED`；DRF；accounts/objects/… | `Web-API.md` L1–21；依赖 `djangorestframework`（`pyproject.toml`） |
| Django Admin | Web-Admin | `Components/Web-Admin.md` |

本项目：官方 CLI（`cli.py` / `__main__.py`）；创作者 Web 平台在 post-MVP backlog（ADR-0006），**引擎不做**编辑器。

### 3.10 设置与 game_template（游戏代码与引擎分离）

| Claim | 证据 |
|---|---|
| `evennia --init mygame` 生成可运行空游戏 | `Setup/Create-Game-Dir.md`；`game_template/` |
| 模板含 `typeclasses/`、`commands/`、`server/conf/`、`web/`、`world/` | `game_template/` 目录列表 |
| 默认 BASE_*_TYPECLASS 指向 `typeclasses.*` | `settings_default.py` L606–619 |
| `settings_default.py` 体量极大（~1340 行） | `wc`；游戏只 override `server/conf/settings.py` |
| `GAME_DIR` 解析 | `settings_default.py` L170+ |

这是 Evennia 对「库可升级、游戏可定制」的核心交付形态。

### 3.11 Contrib 扩展哲学

| Claim | 证据 |
|---|---|
| 核心保持通用；题材/玩法进 contrib | `core-beliefs.md` L5–7；`Contribs-Overview.md` L7–19 |
| 文档索引约 **54** 个 contrib | `Contribs-Overview.md` L10 |
| 分类：base_systems / game_systems / rpg / grid / tutorials / full_systems / utils | `evennia/contrib/` 目录 |
| 战斗相关在 contrib（如 `game_systems/turnbattle`、教程 `evadventure`） | `contrib/game_systems/`；文档 api `evadventure.combat_*` |
| 可选 ECS 式 Components **也是 contrib**，非核心 | `Contrib-Components.md`（ChrisLR, 2021） |

### 3.12 热重载 / `@reload`

| Claim | 证据 |
|---|---|
| `reload` 只重启 Server；Portal 保连接 | `Running-Evennia.md` L40–43；`Server-Lifecycle.md` L56–70 |
| 会调 `at_server_reload*` 钩子；persistent Scripts 不杀 | `Running-Evennia.md` L43 |
| cold start / shutdown / reset 钩子分离 | `Server-Lifecycle.md` |
| 部分改动需 Portal+Server 都重启（例：颜色 markup contrib） | `Contrib-Color-Markups.md`「must restart both」 |
| 新 Typeclass 模块未被 import 则 `typeclass/list` 不可见 | `Typeclasses.md` L43 |
| settings 中部分项注释写明改 parser 等需重启 | `cmdhandler.py` L68–69（COMMAND_PARSER） |

**热重载不是魔法**：代码模块重载 + 钩子保存临时态；DB 行与 Attribute 仍在。错误的持久化临时态、未 import 的模块、Portal 侧协议配置，都是常见坑。

---

## 4. 核心功能矩阵

| 能力域 | Evennia 提供什么 | 成熟度/深度（基于源码与文档） | 证据路径 |
|---|---|---|---|
| 网络协议 | Telnet/WS/SSH；Portal 隔离 | **高**（生产向） | `server/portal/`；`Protocols.md` |
| 账号/登录 | AccountDB、guest、权限组 | **高** | `accounts/`；`Permissions.md` |
| 会话/多端 | Session puppet Character | **高** | `Sessions.md`；`Connection-Styles.md` |
| 对象/房间/出口 | DefaultObject/Room/Exit + 钩子 | **高**（框架完整，玩法自建） | `objects/objects.py`（~3.7k 行） |
| 命令系统 | Command + CmdSet 合并 | **高** | `commands/cmdhandler.py` |
| 权限 | Lock DSL + Permissions | **高** | `locks/` |
| 持久化 | Django ORM；SQLite 默认 | **高**（平台完整；tick 路径代价见 §6） | `Choosing-a-Database.md` |
| 定时 | Scripts / TickerHandler / delay | **高** | `scripts/` |
| 频道 | Channel Typeclass + channel 命令 | **高** | `comms/`；`Channels.md` |
| 私信/邮件持久化 | Msg | **中高**（默认可用于 page） | `Msg.md` |
| Prototype/Spawn | dict + OLC | **高**（builder 向） | `prototypes/` |
| Web/REST | 内置；REST 可选 | **中高** | `web/`；`Web-API.md` |
| 帮助 | DB + 命令 docstring | **高** | `help/` |
| 批量建造 | Batch command/code processor | **中** | `Batch-*.md` |
| 战斗 | **核心无**；contrib/教程有 | **核心：无；生态：中** | Introduction L54–58；`contrib/.../turnbattle` |
| 技能/Effect | 核心无；rpg contrib 有 traits/buffs 等 | **核心：无** | `contrib/rpg/` |
| 声明式内容包 | 非一等公民；偏 Python + prototype 模块 | **弱（相对本项目 UGC 目标）** | 创作路径见 Introduction / Prototypes |
| 热重载 | Server reload 成熟 | **高**（有边界） | `Running-Evennia.md` |
| 测试 | Django/`evennia test`；AGENTS 提倡 no-DB 优先 | **中高** | `AGENTS.md`；`.agents/docs/testing.md` |
| 国际化 | locale | **中** | `locale/`；`Internationalization.md` |

---

## 5. 优点与可借鉴实践

每条格式：**为什么好 → 证据 → 可迁移到 mud_engine 的形态**。

### 5.1 游戏代码与引擎分离（mygame vs evennia）

- **为什么好**：库升级与游戏定制解耦；`--init` 降低冷启动成本。  
- **证据**：`game_template/`；`Create-Game-Dir.md`；`BASE_*_TYPECLASS` 指向游戏目录。  
- **迁移形态**：继续强化「引擎包只暴露加载契约；官方武侠与 UGC 都是 pack 目录」。已有 `pack.load_pack` / `creator-contract-v0.md`；可再明确「官方包也不许 import 引擎私有模块」。

### 5.2 Typeclass / 钩子扩展点

- **为什么好**：升级时少改内核；行为落在 `at_*` 钩子（`core-beliefs.md`「hooks not patches」）。  
- **证据**：`DefaultObject` 钩子体系；`Typeclasses.md`。  
- **迁移形态**：**思想**对齐已有 `SkillBehavior` / `RoomHook` / `world.events`；保持「YAML 引用 id，实现为可信 Python」（ADR-0012），**不要**引入 Typeclass+DB。

### 5.3 CommandSet 动态挂载

- **为什么好**：状态组合（战斗×黑暗×醉酒）免巨型 if。  
- **证据**：`Evennia-In-Pictures.md` L105–113；`cmdset.py` / `cmdsethandler.py`。  
- **迁移形态**：中期可设计「命令层叠」：如 `Unconscious` / `Riding` / `Engaged` 各贡献 allow/deny/replace 表，由调度器合并；先做调研票，勿照搬 Evennia 的对象扫描合并成本。

### 5.4 Lock 字符串 DSL

- **为什么好**：fail-closed；builder/题材包可声明；与命令 access 检查统一。  
- **证据**：`Locks.md`；`lockfuncs.py`。  
- **迁移形态**：评估「声明式谓词表达式」统一 `entry_guard`、门、频道 ACL、命令权限；求值器纯函数、无 DB。注意与现有条件系统（`conditions.py`）合并而非并联第二套。

### 5.5 Prototype 数据驱动生成

- **为什么好**：避免为皮肤/数值差异爆炸出子类；支持继承与标签。  
- **证据**：`Prototypes.md` L11–17、L48–73。  
- **迁移形态**：扩展 YAML 模板继承（`prototype_parent` 类比）与模板标签检索；spawn 逻辑保持在 `scene_loader` / `ai` spawner，**不**做游戏内 OLC。

### 5.6 Session 与 Account/Character 分离

- **为什么好**：多端、多角色、OOC/IC 边界清晰。  
- **证据**：`Evennia-In-Pictures.md` L71–79；`Accounts.md` / `Sessions.md`。  
- **迁移形态**：M4/联网时采用「连接会话 ≠ 账号 ≠ 世界内实体」；当前 `PlayerSession` 组件已是实体侧 seam（`components.py` / `messaging` mailboxes）。

### 5.7 通讯/频道抽象

- **为什么好**：Channel 与房间 say 分叉；订阅/静音/权限可组合。  
- **证据**：`Channels.md`；Msg 与 Channel 职责分离（Msg 文档）。  
- **迁移形态**：已有薄 Channel；多人阶段扩展订阅持久化与 ACL 时，保持「频道表在题材包/注册表，不 fallthrough 占命令空间」（与 LPC/`CONTEXT.md` 一致）。

### 5.8 文档与贡献者体验

- **为什么好**：Introduction / In-Pictures / Beginner Tutorial / API 文档降低上手成本；`AGENTS.md` 给 AI agent 明确架构。  
- **证据**：`docs/source/` 体量；仓库根 `AGENTS.md`、`.agents/docs/*`。  
- **迁移形态**：维持 `creator-contract-v0` + `scene-authoring-guide` + GAP 台账；可考虑为 agent 增加短「架构一页纸」（不必抄 Evennia 文档规模）。

### 5.9 测试与开发循环

- **为什么好**：提倡 no-DB 测试优先；reload 缩短改代码反馈。  
- **证据**：`AGENTS.md` L23；`.agents/docs/testing.md`；`Running-Evennia.md` reload。  
- **迁移形态**：本仓库已偏纯内存单测（861 绿，PROGRESS）；**保留**「逻辑可在无网络/无 DB 下测」。不必引入 Django test runner。热重载对 CLI 单测价值有限。

### 5.10 其他有价值实践

| 实践 | 为什么好 | 证据 | 迁移形态 |
|---|---|---|---|
| Contents / CmdSet 合并缓存 | 热路径防抖 | `ContentsHandler`；`_CMDSET_MERGE_CACHE` | 房间实体枚举、命令表合并若变重，加指纹缓存 |
| idmapper 内存上限可配置 | 防 OOM | `IDMAPPER_CACHE_MAXSIZE` 表 | 未来实体量大时考虑房间级加载/卸载（非照搬） |
| Contrib「可选安装」边界 | 核心不膨胀 | `Contribs-Overview.md` | 非 MVP 玩法进 optional 包/插件，不进内核默认路径 |
| Flat API（`evennia.create_object`） | 降低 import 迷宫 | `architecture.md` Flat API | 谨慎：本项目更宜显式模块边界，避免巨型 `__init__` |

---

## 6. 重要缺陷与技术债（诚实）

### 6.1 Django ORM + 同步 DB 在 tick/命令路径上的代价

- Twisted 单线程：同步慢调用阻塞全服（`Async-Process.md` L28–29）。  
- Typeclass/Attribute 的透明持久化使「一次普通属性赋值」可能隐含 DB I/O——性能与心智模型双重税。  
- SQLite 官方文档承认：高并发写 / 多线程多进程访问不可靠；重网站或长事务应换 PostgreSQL（`Choosing-a-Database.md` L18–21）。  
- **与本项目**：不变量明确「内存 + 本地 JSON 定时存档、不上 PG/Redis」——Evennia 默认路径与此相反。

### 6.2 Typeclass 与 DB 强耦合复杂度

- 全局类名唯一、`__init__` 受限、fallback typeclass、aggressive cache 多进程陷阱（`Typeclasses.md`；`TYPECLASS_AGGRESSIVE_CACHE` 注释）。  
- 调试需同时理解 Django 模型、idmapper 缓存、钩子时序。  
- 学习曲线：官方承认新手需爬坡（`Evennia-Introduction.md` L60–68）；概念叠床架屋（Session/Account/Object/Script/Channel/Attribute/Tag/Nick/Lock/CmdSet…）。

### 6.3 性能与规模边界（仅引用第一手声明）

| 声明 | 出处 | 备注 |
|---|---|---|
| idmapper：约 50MB≈1000 缓存对象，400MB 默认 cap | `settings_default.py` L252–267 | **缓存对象数经验式，不是「同时在线玩家」SLA** |
| `MAX_CONNECTION_RATE=2`、`MAX_COMMAND_RATE=80` | 同文件 L268–278 | DoS 向限流，非容量承诺 |
| SQLite「对多数安装足够」；高并发/多进程需「proper database」 | `Choosing-a-Database.md` L16–21 | 无具体 CCU 数字 |
| 未在源码/文档中确认「支持 N 千人同时在线」的硬 SLA | — | **未确认**；勿对外编造 |

本项目目标「单机 1000 在线 + 100 并发」来自自身 mvp-scope，**不是** Evennia 文档数字。

### 6.4 热重载限制与坑

- 仅 Server 热更；Portal/部分 settings/协议相关需冷启。  
- 未 import 的新模块对 typeclass 列表不可见。  
- persistent vs 非 persistent ticker/delay 语义需小心（`TickerHandler.md` L29–31 pickle 限制）。  
- reload 期间全员「短暂暂停」（`Running-Evennia.md` L40）。

### 6.5 战斗/技能等游戏逻辑薄

- 官方明确：无战斗则游戏「very basic」（Introduction L54–58）。  
- 战斗在教程/contrib，版本与核心演进不同步风险由游戏作者承担。  
- **对本项目**：我们已把战斗七步管线与 PowerModel 接缝放进引擎（ADR-0004，`combat.py`）——这是刻意不学 Evennia「核心极薄」之处。

### 6.6 对声明式 UGC 内容包支持薄弱

- 主创作路径：Python Typeclass + 游戏内建造命令 + Prototype/OLC。  
- Batch processor 偏 builder 脚本，不是「包外 manifest + 只读 YAML 契约 + `--validate`」。  
- REST/Admin 可外挂编辑器，但默认仍围绕 DB 实体，不是 UGC 安全沙箱。  
- Contrib `ingame_python` 等存在，与本项目「UGC 禁止可执行 hooks」（ADR-0012）方向相反。

### 6.7 部署复杂度 vs 内存+JSON

Evennia 最小路径已是：双进程 + migrate + SQLite 文件 + Web 端口。生产常加 PostgreSQL、反向代理、证书（`Setup/Online-Setup.md`、`Config-Nginx.md` 等）。  
`mud_engine`：`python -m mud_engine` / `--pack`，存档为 `snapshots/` + `current` symlink（`save.py` docstring）——符合单机阶段不变量。

### 6.8 其他架构债（源码可见）

| 债 | 说明 | 证据 |
|---|---|---|
| `settings_default.py` 巨型 | ~1300+ 行配置面，认知负担 | 文件本身 |
| `DefaultObject` 极大 | ~3778 行，钩子与默认行为集中 | `objects/objects.py` |
| Cmdhandler 热路径复杂 | 合并 + 缓存 + Twisted 回调 | `cmdhandler.py` ~811 行 |
| 核心无组件模型 | ECS 在 contrib，与 Typeclass 双轨 | `Contrib-Components.md` Cons：额外复杂度、需 host typeclass |
| 依赖沉重 | Django+Twisted+DRF+Autobahn… | `pyproject.toml` dependencies |

---

## 7. 与 mud_engine 全方位对比

> mud_engine 侧均已对照源码；进度语境：M1–M3 完成，Pre-M4 三批关闭，861 测试绿（`PROGRESS.md` 2026-07-22）。

| 维度 | Evennia | mud_engine | 评价 / 启示 |
|---|---|---|---|
| 1. 目标定位 | 通用 MU\* **平台**；游戏逻辑自建 | 题材无关**可玩内核** + UGC 包 + 官方武侠包 | 不要换引擎；可借平台层思想（会话/频道） |
| 2. 进程/世界 | Portal+Server；DB 内多对象＝一世界 | 单进程单 `World`（ADR-0009）；CLI | 符合不变量；联网时慎引入双进程复杂度 |
| 3. 对象模型 | Typeclass + ObjectDB + Attributes | ECS-ish：`EntityId` + 组件 dataclass（`world.py` / `components.py`） | 本侧更贴合声明式数据与可测性；Evennia contrib Components 反证「社区也感到继承不够」 |
| 4. 持久化 | 实时 ORM；SQLite/PG/MySQL | 内存权威；周期 JSON 快照（`save.py` / `TickLoop`） | **刻意分叉**；勿学每命令写库 |
| 5. 命令管道 | CmdSet 合并 → Command 类 | Parser 链 → `Intent` → 动词注册表（`parsing.py` / `commands.py`） | 本侧解析/执行分离清晰；可借鉴叠层状态 |
| 6. 消息/会话/多人 | Session/Account/Channel/Msg 完整 | `PlayerSession` + mailbox + 薄 Channel；无真实登录网 | Pre-M4 已留 seam；M4 再对齐会话模型 |
| 7. 时间与 tick | 可选 Ticker/Script；无强制全局 tick | 强制 `TickLoop` + `on_tick` 事件总线 | 本侧更「仿真心跳」；Evennia 更「按需定时」——可并存：重系统用订阅 tick，稀疏事件用 delay 思想 |
| 8. 战斗与技能 | 核心无；contrib 自建 | `combat.resolve_attack` + `PowerModel` + `SkillBehavior` + `CombatSystem` | 坚持 ADR-0004；可扫 `evadventure`/`turnbattle` 作**对照灵感**，非规格 |
| 9. 房间/出口/钩子 | `at_pre_move` 等对象钩子；Exit 实体 | `Exits`/`Doors`/`HiddenExits` + `RoomHook` 窄 ctx（ADR-0012） | 本侧对 UGC/官方轨分界更清晰 |
| 10. 内容创作面 | Python + 游戏内建造 + Prototype/OLC | `manifest.yaml` + `scene.yaml` + creator-contract；`--validate` | **战略分叉**；Evennia OLC 与 ADR-0006 冲突 |
| 11. 扩展机制 | 继承 Typeclass、挂 Script、装 contrib、改 settings | 注册表（技能/钩子/命令）、YAML 透传 `extension_data`、pack | 保持「注册表 + 声明式引用」；慎引入 settings 巨石 |
| 12. 权限/锁 | 统一 Lock DSL | 分散：guard/旗标/门/钩子条件 | 中期可统一求值器（思想来自 Lock） |
| 13. 测试可测性 | 需 DB fixture 的路径重；提倡 no-DB | 纯内存 World 单测友好；`tests/` 大量用例 | **本侧优势**；保持 |
| 14. 运维部署 | 双进程、migrate、Web 端口、可选 PG | 单模块入口、目录存档 | 符合单机阶段；观测后置（不变量） |
| 15. 与 ADR 契合度 | 与 0005/0006/0009/内存存档 **低契合**；与「题材无关框架」**部分契合** | 直接服务当前不变量 | Evennia 作**参考实现**，不作运行时依赖 |

### 7.1 关键路径对照（示意）

**Evennia（玩家输入）**

```
Portal 收包 → AMP → ServerSession
  → cmdhandler.get_and_merge_cmdsets
  → COMMAND_PARSER 匹配
  → Command.parse / func
  → object.msg / channel / DB Attribute.save…
```

**mud_engine（玩家输入）**

```
cli.run_repl 读行
  → parsing.execute_line
  → DeterministicParser → Intent
  → commands.execute（事件钩子 / 领域事件）
  → world 组件变更 + push_message
  → TickLoop.advance → on_tick → 周期 save_world
```

### 7.2 claim → 证据（mud_engine 抽检）

| Claim | 证据 |
|---|---|
| World 为实体-组件容器 | `world.py` L34–38、L41–48 |
| 运行时子系统统一 `wire_runtime` | `runtime.py` L22–38 |
| 内容包 manifest + scene | `pack.py` L63–74；`creator-contract-v0.md` |
| JSON 存档原子发布 | `save.py` L7–17 |
| 战斗七步 / PowerModel | `combat.py` L1–7、L72–74；ADR-0004 |
| 房间钩子官方轨 / UGC 禁 hooks | `room_hooks.py` L1–6；ADR-0012 |
| CLI 无网络协议栈 | `cli.py`；`__main__.py` |
| 薄 Channel 两条 | `messaging.py` L40–44 |
| 单进程单 World | ADR-0009；`CONTEXT.md`「单进程单 World」 |

---

## 8. 可行动建议（三档）

### 8.1 值得近期借鉴（思想级，可进 ADR / 下一 effort）

1. **固化「引擎包 vs 内容包」目录契约**（§5.1）  
   - 动作：官方武侠数据与 `example-pack` 一律只经 `load_pack` / `load_scene`；文档声明禁止题材包依赖 `mud_engine` 私有符号。  
   - 追溯：Evennia `game_template` + 本仓库 ADR-0005。

2. **命令状态叠层设计调研**（§5.3）  
   - 动作：开短 research/ADR 草案，对比「CmdSet 合并」vs 现有昏迷黑名单 / 骑乘分支；目标是减少 `commands.py` 内散落特殊情况。  
   - 追溯：Evennia CmdSet；`commands.py` 已有 before/after 事件点可挂接。

3. **声明式权限/谓词 DSL 草案**（§5.4）  
   - 动作：把 `entry_guard`、旗标、未来频道 ACL 收敛到同一表达式语言（纯函数、可单测）；**不做**游戏内 `lock` 命令。  
   - 追溯：Evennia Lockstring；本仓库 `conditions.py` / `entity_gate`。

4. **模板继承与标签**（§5.5）  
   - 动作：评估 YAML 级 `extends:` / tags，降低 NPC/物品复制粘贴；spawn 仍数据驱动。  
   - 追溯：Evennia Prototype `prototype_parent` / tags。

5. **多人阶段会话模型预留**（§5.6）  
   - 动作：M4 评估时显式画 Session–Account–Entity 图；避免把 `PlayerSession` 组件直接当成「账号」。  
   - 追溯：Evennia 三层；ADR-0008 边界。

### 8.2 明确不要学 / 与不变量冲突

| 不要学 | 冲突点 | 证据 |
|---|---|---|
| 以 Evennia 替换或嵌入为运行时 | 绿场引擎、单进程、内存 JSON、UGC 契约 | ADR-0002；CLAUDE 不变量 1/3/5 |
| Django ORM 实时写库 | 不上 PG/Redis；内存权威 | CLAUDE §1；`save.py` |
| 游戏内 OLC / 编辑器进引擎 | ADR-0006 | ADR-0006；Evennia `olc`/`spawn` |
| UGC 可执行 Python（ingame_python 类） | ADR-0005/0012 | 钩子仅官方轨 |
| 核心「无战斗，全部推题材包」 | ADR-0004 | Introduction vs ADR-0004 |
| 为热重载引入 Portal/Server 双进程 | 单机阶段过重 | Portal-And-Server；ADR-0009 |
| 巨型 settings 上帝对象 | 可维护性 | `settings_default.py` 体量 |

### 8.3 中长期观察项（M4 / post-MVP）

1. **协议适配层**（Telnet/WebSocket）与「游戏内核」进程边界——可参考 Portal「协议不知游戏」思想，但可用更轻的单进程 asyncio/twisted **仅作 I/O 壳**，内核仍内存 World。  
2. **Evennia REST/创作者外挂编辑器模式** vs 本项目独立 Web 创作者平台（post-mvp-backlog）——只借「内容与运行时分离」，不借 Django Admin。  
3. **Ticker 订阅模型**——若 `on_tick` 订阅者爆炸，借鉴 TickerHandler「按间隔聚合」降低每实体计时器。  
4. **扫 contrib `turnbattle` / `evadventure` / `traits` / `buffs`**：仅作风味与 API 形状对照；任何数值/流程不进入规格。  
5. **规模**：若接近「多进程读同一存档/网站」类需求，重读 Evennia 对 SQLite 与 `TYPECLASS_AGGRESSIVE_CACHE` 的警告——对本项目对应「勿让 Web 平台直写游戏内存态」。

---

## 9. 附录：关键源码/文档索引

### 9.1 Evennia

| 主题 | 路径 |
|---|---|
| 版本 | `evennia/VERSION.txt`（6.1.0） |
| 依赖 | `pyproject.toml` |
| Agent 架构摘要 | `.agents/docs/architecture.md`、`core-beliefs.md` |
| 总览文档 | `docs/source/Evennia-Introduction.md`、`Evennia-In-Pictures.md` |
| Portal/Server | `docs/source/Components/Portal-And-Server.md`；`evennia/server/` |
| Typeclass | `docs/source/Components/Typeclasses.md`；`evennia/typeclasses/`；`evennia/objects/models.py` |
| 命令 | `evennia/commands/cmdhandler.py`；`docs/source/Components/Commands.md`、`Command-Sets.md` |
| Lock | `docs/source/Components/Locks.md`；`evennia/locks/` |
| Scripts/Ticker | `docs/source/Components/Scripts.md`、`TickerHandler.md`；`evennia/scripts/` |
| Channels/Msg | `docs/source/Components/Channels.md`、`Msg.md`；`evennia/comms/` |
| Prototypes | `docs/source/Components/Prototypes.md`；`evennia/prototypes/` |
| Web API | `docs/source/Components/Web-API.md` |
| 数据库选择 | `docs/source/Setup/Choosing-a-Database.md` |
| 生命周期/Reload | `docs/source/Concepts/Server-Lifecycle.md`；`Setup/Running-Evennia.md` |
| 异步陷阱 | `docs/source/Concepts/Async-Process.md` |
| Contrib | `docs/source/Contribs/Contribs-Overview.md`；`Contrib-Components.md` |
| 设置 | `evennia/settings_default.py` |
| 游戏模板 | `evennia/game_template/` |

### 9.2 本仓库

| 主题 | 路径 |
|---|---|
| 不变量 | `CLAUDE.md`、`PROGRESS.md`、`CONTEXT.md` |
| ADR | `docs/adr/0001`–`0012`（尤其 0004/0005/0006/0008/0009/0012） |
| 创作者契约 | `docs/creator-contract-v0.md`、`docs/gap-ledger.md` |
| 引擎包 | `engine/src/mud_engine/`（`world`/`runtime`/`components`/`commands`/`parsing`/`messaging`/`combat*`/`room_hooks`/`pack`/`scene_loader`/`save`/`tick`/`cli`/`__main__`） |
| 测试/数据 | `engine/tests/`、`engine/data/` |
| 架构评审语境 | `.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md`（非 Evennia 源） |

### 9.3 自检

- [x] 文件路径：`.scratch/research/02-evennia/vs-mud-engine-2026-07-23.md`  
- [x] 含「给架构师的摘要」  
- [x] 含功能矩阵、对比表、建议三档  
- [x] 重要 claim 带路径/符号；未确认项已标明  

---

*调研日期：2026-07-23。Evennia 以本地 clone 6.1.0 为准；若上游主线变更，以 `VERSION.txt` / 文档对应页复核。*
