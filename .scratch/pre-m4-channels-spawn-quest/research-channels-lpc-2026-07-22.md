# 调研：侠客行 LPC「频道」与多人世界消息（2026-07-22）

> **范围**：仓库内 LPC 只读第一手源；服务 Pre-M4 架构设计，**不是**行为等价规格（[ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）。  
> **目标问题**：题材无关的 MUD 核心引擎里，如何既保持通用 messaging / session 能力，又留下干净可扩展的 Channel 面（Pre-M4 可薄切片，不绑死武侠频道表）？  
> **关联**：主 grill 卡点「问题 2」——频道 ID / 命令面 / 默认订阅（见 [grill-paused-2026-07-22.md](grill-paused-2026-07-22.md)、[session-notes-2026-07-22.md](session-notes-2026-07-22.md)）。  
> **引擎现状对照**：当前 Python 引擎仅有同房间 `room_say`（`engine/src/openmud/messaging.py`）；频道 / 登录按 [ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md) 不在 M3 停机门闩内。

---

## 1. 摘要（给架构师）

LPC 的「频道」本质是：**全局（或权限过滤后的）命名广播管道**，与房间 `say` / 定向 `tell` / 全员 `shout` 并列，而不是房间消息的超集。核心枢纽是 `CHANNEL_D`（`/adm/daemons/channeld.c`）里硬编码的 `channels` mapping；玩家侧用 dbase 字段 `channels`（string 数组）做订阅；命令面靠 `feature/command.c` 的 fallthrough——**任意未知 verb 若命中频道 ID 就 `do_channel`**，因此频道名即命令名。投递两段式：daemon 先 `filter_array(users(), …)` 筛资格听众，再 `message("channel:"+id, …)`；真正「是否听见」由 `feature/message.c` 的 `receive_message` 对照订阅表决定。武侠特有层（`menpai` 同门过滤、`rumor` 匿名 + 精力消耗、巫师 `sys`/`wiz`、Intermud `gchat`/`gwiz`、运营禁言 `chblk_*`、心跳刷屏封禁）全部揉进同一 daemon / 同一命令命名空间。对通用引擎的启示是：**保留「会话投递 + 消息类路由 + 订阅集合」三件套；把「频道表 / ACL / 显示名 / 是否匿名 / 消耗」切到题材包或可注册扩展；命令映射不要默认「verb = channel id」绑定死全局命令空间。** Pre-M4 薄切片只需 1～2 条跨 session 广播 + 默认订阅即可验证假多人 seam；门派频道、谣言匿名、禁言投票、Intermud 一律 OOS。

---

## 2. LPC 频道体系鸟瞰

### 2.1 频道表（谁拥有配置）

| 频道 ID | 显示前缀（speak） | 关键标志 | 说明 |
|---|---|---|---|
| `sys` | 【系统】 | `wiz_only` | 运维 / 登录进出；玩家不可听写（听写靠 wizard） |
| `wiz` | 【巫师】 | `wiz_only` + emote | 巫师内部 |
| `chat` | 【闲聊】 | 全员；`omit_address`；`filter`（Intermud 侧） | 主社交频道 |
| `rumor` | 【谣言】 | `anonymous: "某人"` | 匿名；玩家发言耗 `jingli`；系统死亡/宝物也常走此道 |
| `menpai` | 【门派】→ 运行时改成【门派名】 | `menpai_only` | 同 `family/family_name`；巫师旁听 |
| `gwiz` | 【网际巫师】 | `wiz_only` + `intermud: GWIZ` | 跨站巫师 |
| `gchat` | 【泥潭闲聊】 | `intermud: GCHANNEL` | 跨站闲聊 |

**配置所有权**：硬编码在 `adm/daemons/channeld.c` 文件顶部 `mapping channels = ([ ... ])`（约 L18–52）。**未找到**独立 `/adm/daemons/channels` 实现（`include/daemons.h` 中 `CHANNELS_D` 已注释）。**未找到** `cmds/channels/` 目录（`include/config.tmi.h` 的 `CHAN_CMDS` 指向空路径）。

### 2.2 文档与代码漂移（反例信号）

玩家帮助 `doc/help/channels` 还列出 **侠客行频道 `xkx`**（镜像站联播），并提到 `chat*` 式频道 emote。但当前 `channeld.c` 的 `channels` mapping **没有 `xkx`**：`do_channel(..., "xkx", ...)` 会因 `undefinedp(channels[verb])` 直接 `return 0`。内容侧仍有调用（如 `d/bwdh/square.c` 武林大会广播）。巫师指令 `cmds/wiz/chblk.c` / `unchblk.c` 仍调用 `CHANNEL_D->set_block(...)` 并处理 `chblk_xkx`，但 **`channeld.c` 内未定义 `set_block`**——全仓库仅这两处调用，属死接口 / 历史残留。

### 2.3 投递模型（一句话）

```
玩家输入 verb arg
  → command_hook：cmd → 房间 emote → CHANNEL_D->do_channel(me, verb, arg)
       → 权限 / 禁言 / 防刷检查
       → 自动把 verb 加入 me->channels（发言即订阅）
       → 可选频道 emote（verb 以 * 结尾）
       → filter_listener 筛 users()
       → message("channel:"+verb, formatted, listeners)
            → 各对象 receive_message：再查订阅
       → 可选 Intermud / extra_listener 继电器
```

与房间 `say` 完全分叉：`say` 走 `message("sound", …, environment(me), …)`，从不进 `CHANNEL_D`。

---

## 3. 关键路径拆解（claim → 路径 + 符号）

### 3.1 Daemon：`CHANNEL_D`

| Claim | 证据 |
|---|---|
| 宏指向 `channeld` | `include/globals.h`：`#define CHANNEL_D "/adm/daemons/channeld"`（亦见 `inherit/misc/globals.h`） |
| 唯一频道注册表 | `adm/daemons/channeld.c`：`mapping channels = ([ ... ])` |
| 发送入口 | `do_channel(object me, string verb, string arg, int emote)`（同文件 L60） |
| 听众过滤 | `filter_listener(object ppl, mapping ch)`（L227）：无 `environment` → 丢弃；`wiz_only` → `wizardp`；`menpai_only` → 同门或巫师 |
| 继电器扩展点 | `register_relay_channel(string channel)`（L239）；投递时调 `extra_listener->relay_channel`（L209–212）。**仓库内无其它文件调用 `register_relay_channel`**（扩展点存在但未用） |
| Intermud 出口 | `channels[verb]["intermud"]->send_msg(...)`（L215–219）；实现见 `adm/daemons/network/services/gchannel.c` 的 `send_msg` / `incoming_request` |
| 网际巫师 | `adm/daemons/network/services/gwizmsg.c` 收到后 `do_channel(..., "gwiz", ...)` |

**`menpai` 过滤实现瑕疵（反例）**：`filter_listener` L234 使用 `this_player()->query("family/family_name")` 与听众比较，而不是发送者 `me`。若发送上下文 `this_player()` 非发言者（系统 / 强制），同门过滤会错。这是「把发送者上下文藏在全局 this_player」的典型泥潭债。

### 3.2 登录默认订阅

| Claim | 证据 |
|---|---|
| 新角色默认订阅 | `adm/daemons/logind.c` → `init_new_player` L518：`user->set("channels", ({ "chat", "rumor", "gchat" }))` |
| 不含 `menpai` / `sys` / `wiz` | 同上；`menpai` 需发言自动打开或日后存档里已有 |
| 老角色靠存档 | `logind` **仅**在 `init_new_player` 设默认；重登不强制覆盖 → 订阅持久化在玩家 dbase |
| 登录本身发 sys | `enter_world` / `reconnect`（L674、L689）对 `CHANNEL_D->do_channel(this_object(), "sys", ...)` 报连线；daemon 自身 `set("channel_id", "连线精灵")`（logind L72） |

### 3.3 命令面（chat / rumor / tell / shout / say）

| 能力 | 是否频道 | 路径 / 机制 |
|---|---|---|
| `chat` / `rumor` / `menpai` / `gchat` / `wiz`… | **是** | **无**独立 `cmds/**/chat.c`；靠 `feature/command.c` `command_hook` L63：`CHANNEL_D->do_channel(this_object(), verb, arg)`——**频道 ID = 命令 verb** |
| 频道 emote | **是** | 输入 `chat* hi`：`do_channel` L66–68 见 verb 末尾 `*` 则 `emote=1`，再调 `EMOTE_D->do_emote`（`adm/daemons/emoted.c` L79+；channel_emote 1/2/3 区分 chat/rumor/intermud） |
| `say` | **否**（房间） | `cmds/std/say.c`：`message("sound", …, environment(me), me)` + `relay_say` |
| `tell` | **否**（点对点） | `cmds/std/tell.c`：`tell_object` / 跨站 `GTELL`；与订阅无关 |
| `shout` | **否**（强制全员） | `cmds/std/shout.c` → simul_efun `shout` → `message("shout", str, users(), …)`（`adm/simul_efun/message.c` L46–49）；玩家默认关闭（`SHOUT_LIST` 空） |
| 房间自由 emote | **否** | `cmds/std/emote.c`：同房间 `tell_room`；与频道 `*` emote 不同路径 |
| 预设动作 emote | 房间优先 | `command_hook` 先 `EMOTE_D->do_emote`（无 channel 标志），失败才 `do_channel`——因此 **同名时房间 emote 优先于频道** |

帮助文：`doc/help/channels`；开关说明嵌在 `cmds/std/tune.c` 的 help。

### 3.4 表情与频道钩子

| Claim | 证据 |
|---|---|
| 频道 emote 复用 EMOTE_D | `channeld.c` L140–180；`emoted.c` 注释 L77–78：`channel_emote==1` chat，`==2` rumor（匿名「某人」），`==3` intermud |
| 频道 emote 可跨房找目标 | `emoted.c` L99–103：非频道 emote 只 `present` 同房；频道 emote 可 `find_player` |
| 返回格式化串供频道包装 | `emoted.c` L167–168：`channel_emote` 时 `return normal_color(str)` 而非本地 `message("emote",…)` |
| 自由 `emote` 命令不进频道 | `cmds/std/emote.c` 仅同房间 |

### 3.5 房间 say vs 跨房间频道边界

| 维度 | 房间 `say` | 频道 |
|---|---|---|
| 范围 | `environment(me)` | `users()` 再过滤 |
| 消息类 | `"sound"` / simul_efun `"say"` | `"channel:<id>"` |
| 订阅 | 无（同房即听，除非 `block_msg`） | 必须在 `query("channels")` |
| 命令解析 | 正式 cmd 文件 | fallthrough 命中 mapping |
| NPC 钩子 | `relay_say` | 无对等；系统用假 speaker + `do_channel` |

引擎对照：`openmud.messaging.room_say` ≈ LPC `say` 侧；**尚无** `channel:*` 对等物。

### 3.6 门派 / 帮派 / 巫师特殊频道

| 类型 | 结论 |
|---|---|
| 门派 | `menpai` 频道；准入 `family/family_name`；显示名运行时改写 shared mapping（`channeld.c` L95–98）——**全局可变模板，并发发言会互相覆盖显示名**（设计债） |
| 巫师 | `sys` / `wiz` / `gwiz`；`wiz_only`；非巫师 `do_channel` 对 wiz 频道 `return 0`（静默失败，L119–120） |
| 帮派 | **未找到**独立帮派频道。`include/daemons.h` 有 `#define PARTY_D "/adm/daemons/party_d"`，但 **`party_d` 文件未找到**；频道表无 party/bang |
| 广告伪频道 | `adm/daemons/adsd.c` 直接 `message("channel:ads", …, users())`；**未**注册进 `channels` mapping → 不能 `ads 你好` 发言，只能系统推；收听仍靠订阅名 `"ads"` |

### 3.7 订阅开关与禁言

| 机制 | 作用 | 路径 |
|---|---|---|
| `tune <id>` | **只关不开**；列表查询 | `cmds/std/tune.c`：从 `channels` 数组减去；打开靠「对该频道说话」 |
| 发言即订阅 | 自动 `channels += ({ verb })` | `channeld.c` L131–136 |
| 玩家禁言标志 | `chblk_on` / `chblk_rumor` / `chblk_chat` / `chblk_gchat` / `chblk_menpai` / `chblk_xkx` | 写侧：`cmds/wiz/chblk.c`、`cmds/std/vote/chblk.c`；读侧：`channeld.c` L79–116 |
| 全关级联 | `chblk_on` 时强制打开各分项 chblk | `channeld.c` L79–85 |
| 刷屏自动封 | 每 heartbeat：`channel_msg_cnt > 10` → 谣传 + `chblk_on` | `inherit/char/char.c` `heart_beat` L70–80；计数在 `do_channel` L128 `add_temp` |
| 重复句拦截 | 与 `last_channel_msg` 相同则拒绝 | `channeld.c` L122–123 |
| 留言板暂关频道 | 读写板时 `channels` 置 0，结束恢复 | `inherit/misc/bboard.c` `tune_channels` / `open_channels`（L255–277） |
| 编译期总开关 | `BLOCK_CHAT` / `BLOCK_RUMOR` 恒为 0 | `channeld.c` L13–14；`set_block` **未实现** |

### 3.8 「多人世界」相关广播 daemon / 旁路

| 组件 | 角色 |
|---|---|
| `CHANNEL_D` | 主跨房间社交 / 系统广播 |
| `gchannel.c` / `gwizmsg.c` / `gemote.c` / `remote_q.c` | Intermud 进出，最终仍入 `do_channel` |
| `adsd.c` | 定时广告，走 `channel:ads` 消息类 |
| `combatd.c` / `feature/damage.c` 等 | 死亡等事件 `do_channel(..., "rumor", …)`（世界叙事广播） |
| `logind.c` | 进出世界 `sys` |
| 直接 `message("channel:chat", …, users())` | 绕过 `do_channel`（如 `cmds/usr/suicide.c`、部分城市通告）——**不走禁言 / 防刷 / 发言即订阅** |
| `shout` | 另一条全员管道，不经频道订阅 |
| `INTER_CHAN_D` | `include/net/daemons.h` 指向 `/adm/daemons/network/inter_chan`——**文件未找到** |

---

## 4. 数据结构与 API 面

### 4.1 频道注册条目（每频道 mapping 字段）

来自 `channeld.c` 实际使用的键：

| 键 | 含义 |
|---|---|
| `msg_speak` | `sprintf` 模板：`who, arg` |
| `msg_emote` | emote 模板 |
| `wiz_only` | 仅巫师听 / 写 |
| `menpai_only` | 同门听；无门派不能写 |
| `anonymous` | 发言者显示名替换；并向 `sys` 泄露真名 |
| `omit_address` | emote 本地剥离 `@mud` 地址 |
| `intermud` | 跨站发送对象 |
| `channel` | 跨站协议上的频道名 |
| `intermud_emote` | 跨站 emote 模式 |
| `filter` | 传给 Intermud `send_msg` 的 mud 过滤（chat/gchat 为常量 `1`） |
| `extra_listener` | 运行时继电器对象数组（`register_relay_channel` 填充） |

### 4.2 玩家侧状态

| 字段 | 存哪 | 含义 |
|---|---|---|
| `channels` | 玩家 dbase（可存档） | 订阅的频道 ID 列表 |
| `chblk_*` / `chblk_on` | 玩家 dbase | 运营 / 投票禁言（写禁，不是退订） |
| `channel_msg_cnt` / `last_channel_msg` | temp | 防刷 |
| `channel_id` | 对象 dbase（daemon/NPC） | 非玩家发言时的显示身份（如「频道精灵」「连线精灵」） |
| `env/block` 等 | tell 专用 | 与频道订阅无关 |

### 4.3 投递 API 分层

1. **业务 API**：`CHANNEL_D->do_channel(me, verb, arg [, emote])`  
2. **传输 API**：efun/mudlib `message(msgclass, msg, targets [, exclude])`  
3. **会话接收**：`feature/message.c` → `receive_message`；subclass `channel` 时查订阅；支持输入中缓冲（`msg_buffer`）  
4. **旁路**：直接 `message("channel:…")` 或 `shout` / `tell_object`

对引擎设计最有用的分层是 **2+3**（通用投递与会话过滤），而不是照搬 **1** 的巨型 `do_channel`。

---

## 5. 与「多人世界」的耦合点

| 耦合 | LPC 做法 | 对通用引擎的风险 |
|---|---|---|
| 在线集合 | `users()` 即广播域 | 引擎需显式 `World` 内 session 枚举（已有单进程单 World，[ADR-0009](../../docs/adr/0009-single-process-single-world.md)） |
| 登录生命周期 | 进出刷 `sys`；新号写默认订阅 | 频道不要绑死完整登录账号系统（ADR-0008）；假多人可用「创建 PlayerSession 时写默认订阅」 |
| 权限 | `wizardp` / 门派 family | ACL 应是可插拔谓词，不宜写死武侠门派字段 |
| 题材经济 | rumor 扣 `jingli` | 消耗策略属题材包，不应进 core |
| 防刷 | heartbeat 计数 + 永久 `chblk_on` + 投票 | Pre-M4 可留钩子；完整运营策略 OOS（session-notes §3） |
| 世界叙事 | 死亡 / 宝物 / 任务大量 `rumor` | 「系统公告频道」与「玩家闲聊频道」在 LPC 常混用——引擎宜分开语义 |
| Intermud | 频道条目内嵌跨站 | 明确 OOS；扩展面不要为跨服预留半吊子字段污染核心 |
| 命令空间 | 频道 ID 占用全局 verb | 与引擎命令表冲突风险高（见 §6） |

---

## 6. 对通用引擎的启示

### 6.1 灵感（值得保留的形状）

1. **消息类路由**：`channel:<id>` / 房间 / tell / shout 分轨；接收端统一进 session（LPC：`receive_message`；引擎：`PlayerSession` + `pending_messages`）。  
2. **订阅集合在 session / 玩家组件上**：听不听是接收策略，不是发送方枚举房间。  
3. **发送方资格过滤 ≠ 接收方订阅**：LPC 两段式清晰——core 可做成 `ACL predicate → fan-out → per-session subscribe gate`。  
4. **发言即订阅**（可选 UX）：降低「开了才能说」的摩擦；与 `tune` 只关不开放对。  
5. **系统可用具名 speaker 发频道**（`channel_id`）：测试 / NPC / 世界事件不必伪装玩家。  
6. **扩展继电器**（`register_relay_channel`）：日志、审计、未来创作者钩子的干净挂点——比把逻辑写进 `do_channel` 中段更好。

### 6.2 反例（明确不要照搬）

1. **频道表硬编码进 core daemon**，武侠名（闲聊 / 谣言 / 门派）与 Intermud 字段同表。  
2. **命令 fallthrough：任意 verb = 频道 ID**——污染全局命令空间，和技能 / 别名 / 出口缩写抢解析顺序。  
3. **`menpai` 运行时改写全局模板** + **`this_player()` 过滤**——共享可变状态与隐式上下文。  
4. **禁言标志矩阵**（`chblk_on` 与分项纠缠）与 **文档/代码漂移**（`xkx`、`set_block`）。  
5. **旁路 `message("channel:…")` 绕过策略**——禁言 / 防刷形同虚设。  
6. **把世界公告、死亡谣传、玩家闲聊塞同一 `rumor` 语义**——题材包叙事可以，core 契约应区分 `system` vs `player` 管道（或同一管道不同 `source_kind`）。  
7. **刷屏直接永久封频道**绑在 `heart_beat`——运维策略不应成为引擎心跳义务。  
8. **广告伪频道未注册却占用 `channel:` 命名空间**——注册表应是单一真相源。

### 6.3 通用 messaging / session 应保留什么

建议落在 core（与现有 `messaging.py` / `PlayerSession` 对齐）：

| 能力 | 说明 |
|---|---|
| Session 收件箱 | 已有 `pending_messages`；频道与房间共用投递终点 |
| 房间广播 | 已有 `room_say` + `on_hear_say`；边界保持「同 Position.room」 |
| 跨 session 广播原语 | 新增如 `broadcast(msg_class, payload, sessions|predicate)`，**不**内置武侠频道名 |
| 每 session 订阅集 | 如 `PlayerSession.subscriptions: set[str]` 或独立组件 |
| 消息类约定 | 至少：`room` / `channel:<id>` / `tell`（后二者可薄）；接收侧按类过滤 |
| 可测试 seam | 同一 `World` 双 `PlayerSession`（session-notes 已选 A） |

### 6.4 Channel 扩展面应切在哪

推荐切开的四层（由内到外）：

```
[Core]
  Session delivery + msg_class routing + subscription set
        ↑ 注册 / 查询
[Channel Registry]  （可先做极薄 in-memory）
  id → {display?, acl?, allow_emote?, flags?}
        ↑ 填充
[Pack / 题材配置]
  声明有哪些频道、默认订阅、显示名、是否匿名、消耗
        ↑ 绑定
[Command map]
  玩家输入 → channel id（显式命令表或 pack 别名，避免全局 fallthrough）
```

**切缝原则**：

- **ID**：不透明字符串；core 不解释 `menpai`/`rumor` 语义。  
- **订阅**：core 只存集合 + tune/subscribe API；默认值可由 pack 或引擎演示配置提供。  
- **命令映射**：pack 或命令模块声明 `chat → channel:chat`；**不要**「未知命令都去问 ChannelRegistry」。  
- **题材规则**：匿名、扣资源、同门 ACL、巫师 ACL → registry 上的可选策略对象 / 钩子，默认 no-op。

### 6.5 Pre-M4 薄切片建议

**本波够用（1～2 频道）**：

- 双 `PlayerSession` 互听同房 `say`（已接近）；再加 **一条**全局 `chat`（或两条：`chat` + 可选 `rumor` 但 **不做匿名/扣精力**）。  
- 默认订阅：创建 session 时写入演示默认（可硬编码在测试 fixture / 官方示例包，不必完整 `tune`）。  
- API：`channel_say(world, speaker, channel_id, text)` → 格式化 → 推给订阅者的 `pending_messages`。  
- 验收：测试断言 B 收到 A 的频道句；退订（若做）后收不到。

**必须留给题材包 / 后续**：

- 门派 / 帮派过滤与动态显示名  
- 谣言匿名与系统谣传叙事  
- 巫师频道、登录公告频道运营策略  
- Intermud / 镜像站  
- 投票禁言、刷屏永久封、广告伪频道  
- `chat*` 全套 emote 目录（房间 emote 可另议）  
- 「发言即订阅 + tune 只关」的完整体验（可后置；本波可默认全开且无开关，与 grill 草案 A 一致）

### 6.6 明确不要从 LPC 照搬的清单（短）

- 武侠频道表进 `openmud` 常量  
- verb fallthrough 抢命令解析  
- `jingli` / `family_name` / `wizardp` 写进 core `do_channel`  
- 未注册频道的旁路 `message("channel:…")` 模式（应强制走 registry）  
- Intermud 字段  
- 行为等价于 `chblk_*` 矩阵与 vote 禁言

---

## 7. 对主 grill「问题 2」的推荐输入

> 问题：频道具体 ID / 命令面 / 默认订阅？  
> 约束：题材无关 core + Pre-M4 薄切片；LPC 仅灵感 / 反例。  
> **以下给出选项与取舍，不替架构师拍板。**

### 选项矩阵

| 选项 | 频道 ID | 命令面 | 默认订阅 | 本波 tune | 优点 | 代价 / 风险 |
|---|---|---|---|---|---|---|
| **A**（grill 曾荐） | `chat` + `rumor` | 命令同名（`chat`/`rumor`） | 全开 | 不做 | 与 LPC / 玩家心智接近；双 session 可测「闲聊 vs 谣传」叙事位 | ID 略武侠；易诱后续把匿名/扣血搬进 core；两频道可能超薄切片所需 |
| **B** | 中性 ID：如 `ooc` + `gossip`（或仅语义名 `global` / `story`） | pack 或命令表映射中文/别名；core 只认中性 ID | 全开 | 不做 | **最贴「题材无关」**；显示名可交给官方轻量武侠包写成「闲聊/谣言」 | 与 LPC 文档对照成本；命名需多一轮 bikeshed |
| **C** | 仅 `chat`（一条） | 显式命令 `chat`（或 `channel chat …`） | 开 | 不做 | 最小验收；强制把「第二频道语义」留给题材包 | 无法在本波验证「多频道订阅隔离」 |
| **D** | `chat` + `rumor` | **统一** `channel <id> <text>` 或 `c <id> …`；同名快捷作 pack 糖 | `chat` 默认开；`rumor` 默认开或关可选 | 可选最小 `tune` | 命令空间干净（吸取 LPC fallthrough 反例）；扩展第三频道零冲突 | 玩家多打一层字；与「假多人 CLI 不改 REPL 体验」要协调（测试 seam 为主则可接受） |

### 取舍维度（供拍板时加权）

1. **扩展面优先 vs 熟词优先**  
   - 怕武侠词渗进 core API → 偏 **B** 或 **D**。  
   - 官方包就是武侠、且本波只想尽快验收 → **A** / **C** 足够。  

2. **要不要在本波验证「订阅隔离」**  
   - 要（A 听得到 chat、关掉后听不到）→ 至少两频道或一频道 + 假退订 API；与「本波不做 tune」冲突时，可用测试直接改 `subscriptions`。  
   - 不要 → **C** 最省。  

3. **命令面污染**  
   - LPC 反例强烈建议：**不要**做「未知 verb 丢给 ChannelRegistry」。  
   - 即便选 A 的同名命令，也应是**显式注册**的两条命令，而非 fallthrough。  

4. **`rumor` 要不要出现在 core 默认**  
   - 若 ID 叫 `rumor` 却无匿名，会误导后续实现者「补齐 LPC 语义」。  
   - 若需要第二管道做「系统叙事 vs 玩家闲聊」，更干净的是 `chat` + `system`（或 `story`），而不是半吊子 `rumor`。  

5. **与 ADR-0008**  
   - 任一选项都不应暗示「完整登录 / 运营禁言已进停机范围」；本波是 Pre-M4 假多人 seam，修订 ADR 形态仍是主 grill 未决项。  

### 调研者倾向性提示（非拍板）

若目标函数是「**通用扩展面清晰 + Pre-M4 可测**」，综合 LPC 反例后，**B 或 D 优于裸 A**：中性 ID（或统一 `channel` 命令）把武侠显示名留给官方包；A 仅在「刻意复用熟词、并写明 core 不实现谣言语义」时可作为务实捷径。**C** 适合觉得双频道仍胖、只想先打通 fan-out 的情况。  

无论选哪条，建议在 grill 决议里写死三句：

1. Core 只保证：registry（可极薄）+ subscribe + broadcast to sessions。  
2. 命令映射显式注册，禁止 LPC 式 fallthrough。  
3. 匿名 / 门派 ACL / 禁言 / Intermud = 题材包或 post-Pre-M4。

---

## 8. 源码索引（便于复查）

| 主题 | 路径 |
|---|---|
| 频道 daemon | `/home/gukt/github/xkx2001-utf8/adm/daemons/channeld.c` |
| 宏 | `include/globals.h`（`CHANNEL_D`） |
| 命令 fallthrough | `feature/command.c`（`command_hook`） |
| 接收 / 订阅门闩 | `feature/message.c`（`receive_message`） |
| 默认订阅 | `adm/daemons/logind.c`（`init_new_player`） |
| tune | `cmds/std/tune.c` |
| say / tell / shout / emote | `cmds/std/{say,tell,shout,emote}.c` |
| 频道 emote | `adm/daemons/emoted.c`（`do_emote`） |
| 刷屏封禁 | `inherit/char/char.c`（`heart_beat`） |
| 巫师 / 投票禁言 | `cmds/wiz/chblk.c`, `cmds/wiz/unchblk.c`, `cmds/std/vote/chblk.c`, `cmds/std/vote/unchblk.c` |
| Intermud | `adm/daemons/network/services/gchannel.c`, `gwizmsg.c`, `gemote.c` |
| 广告伪频道 | `adm/daemons/adsd.c` |
| 玩家帮助 | `doc/help/channels` |
| shout 原语 | `adm/simul_efun/message.c`（`shout`） |
| 引擎房间消息 | `engine/src/openmud/messaging.py` |

### 未找到（显式）

| 符号 / 路径 | 状态 |
|---|---|
| `/adm/daemons/channels`（`CHANNELS_D`） | 未找到（宏已注释） |
| `cmds/channels/`（`CHAN_CMDS`） | 未找到 |
| `CHANNEL_D->set_block` 实现 | 未找到（仅被 wiz 指令调用） |
| `xkx` 频道注册 | 未找到于 `channeld.c` mapping（帮助与内容仍引用） |
| `/adm/daemons/party_d` | 未找到 |
| `/adm/daemons/network/inter_chan` | 未找到 |
| 独立帮派频道 | 未找到 |
| `std/` 目录下 channel 定义 | 路径不存在；相关在 `feature/` + `inherit/` |

---

## 9. 是否足以支撑窄域 grill

**是。** 本调研已厘清：

- LPC 频道 = 命名全局广播 + 订阅 +（可选）ACL，与 `say`/`tell`/`shout` 分轨；  
- 配置硬编码、命令 fallthrough、武侠 ACL / 匿名 / Intermud 为主要反例；  
- Core 应保留的通用面与应外置的题材面边界清楚；  
- 对问题 2 给出 A/B/C/D 选项及取舍维度，可直接喂回主 `/grill-with-docs` 从卡点续问。  

**不需要**再为「LPC 有没有频道」做第二轮宽搜；若窄域 grill 中选了含 `rumor` 的方案，只需追加一句产品语义（是否匿名）——那是设计选择，不是 LPC 事实缺口。
