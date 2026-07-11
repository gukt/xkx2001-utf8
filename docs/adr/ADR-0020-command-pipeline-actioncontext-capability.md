# ADR-0020：命令 8 段中间件管线分段 + ActionContext + CapabilityToken

- 状态：草案（Wave 2 T4 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 2 T4
- 关联：[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 M1-7（命令管线 + ActionContext + CapabilityToken）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（force_me 边界侵蚀）/ [02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 Command 模式裁决 / [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T4 / [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) securityd -> PermissionService + CapabilityToken / [ADR-0021](ADR-0021-previous-object-explicit-mapping.md) previous_object 显式化

## 背景

[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 里程碑 M1-7："命令管线 + ActionContext + CapabilityToken | go/kill 单段 -> 8 段中间件 + previous_object 显式化（155 处）"。[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T4 任务卡：单段命令执行升级为 8 段中间件管线；ActionContext（actor/viewer/target 三元组）；CapabilityToken（不可伪造，02 裁决 HS256 + 内存吊销）；force_me=PrivilegedAction（ROOT 门控 + 强制审计）。

**LPC 规格源**（只读参考）：

- [spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) `command_hook` 四分支（方向快捷 -> find_command -> emote -> channel，短路求值，`feature/command.c:32-76`）+ `process_input` 预处理（刷屏检测 -> 历史替换 -> 自定义别名 -> 全局方向别名，`feature/alias.c:21-110`）+ `find_command` 逆序搜索（`commandd.c:28-48`）+ 18 方向别名（`DIRECTION_ALIASES`）+ `force_me`（`feature/command.c:89-95`，`geteuid(previous_object())==ROOT_UID` 门控）
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) `SECURITY_D valid_cmd`（`securityd.c:710-772`，fail-closed：euid 为空返回 0；exclude 优先于 authorized；cmds/std/skill/usr 对所有玩家开放；未通过记 CMD_LOG 返回 0）
- [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `visible(me, ob)`（viewer=this_object()，target=ob；invisibility > wiz_level(viewer) 不可见；鬼魂需 is_ghost() 或 astral_vision；"PronounContext 必须携带 viewer"实证）

**Q3 裁决**（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3）：Command = 8 段管线信封的形式化命名（不新建类层级），仅覆盖外部意图；System.update 覆盖派生变更不经 Command。force_me=PrivilegedAction（Command 变体，ROOT 门控 + 强制审计），显式承认是保真让步--边界在 force_me 处妥协以保 LPC 保真。

**现状**：

- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py) 10 命令（go/kill/ask/give/quest/take/look/inventory/hp）单段执行，无中间件分层、无 ActionContext、无 CapabilityToken、无审计日志。
- 阶段 -1 垂直切片的 `Game` + 纯函数命令仅是"路由 -> 执行"两段，未覆盖别名/权限/方向快捷/previous_object 注入/审计。

## 决策

### 1. 8 段分段（对照 LPC command_hook 四分支 + process_input 预处理）

8 段中间件按 LPC 命令分发管线真实顺序分段，每段是纯函数 `(ActionContext) -> ActionContext | Abort`，短路求值（任一段 Abort 则管线终止，后续段不执行）：

| 段 | 名称 | LPC 对照 | 职责 |
|---|---|---|---|
| 0 | 刷屏检测 | `process_input` cnt 计数 + CMDS_PER_TICK=20 | tick 内命令计数，超阈值扣气/精，3x 触发天雷（50% 昏迷 + 强制 quit） |
| 1 | 别名解析 | `process_input` 历史替换 + 自定义别名 + `ALIAS_D->process_global_alias` | 历史替换（`!`/`!N`）+ 玩家别名展开（`$N`/`$*`）+ 全局方向别名（`DIRECTION_ALIASES` 18 项 + 非方向别名） |
| 2 | 权限校验 | `SECURITY_D->valid_cmd` fail-closed | CapabilityToken 校验 + 命令路径权限（exclude 优先 authorized，cmds/std/skill/usr 开放，cmds/adm 仅 admin） |
| 3 | 命令查找 | `COMMAND_D->find_command` 逆序搜索 | 按身份路径（ADM/ARC/WIZ/APR/IMM/PLR/UNR/NPC_PATH）逆序查找命令，首次访问 rehash 缓存 |
| 4 | 方向快捷 | `command_hook` 分支 A（arg=="" 且房间有 exit -> 隐式 go） | 无参方向名且房间有对应 exit 时，重写为 `go <direction>` |
| 5 | 参数解析 | 命令 main 函数入参 | 引号感知 tokenizer（替代 `split()` 拆空格，12 文档技术债）+ LPC `parse_command` 语义对齐（阶段 1 最小集） |
| 6 | previous_object 注入 | `this_player()` / `previous_object()` 信任链 | ActionContext 显式填充 actor/source/target 三元组（详见 [ADR-0021](ADR-0021-previous-object-explicit-mapping.md)） |
| 7 | 执行 + 审计 | `call_other(file, "main", this_object(), arg)` + CMD_LOG | 同步执行命令 main（保 LPC `call_other` 同步语义，68771 处调用栈）+ 审计日志（命令/actor/result/timestamp） |

**分段理由**（对照 LPC 四分支）：

- LPC `command_hook` 四分支（方向快捷 / find_command / emote / channel）是**路由段**的保真目标，新引擎将其拆为段 3（命令查找）+ 段 4（方向快捷）两段：段 3 逆序查找普通命令，段 4 是段 3 未命中时的方向快捷回退（LPC 顺序是方向快捷优先，但方向快捷本质是"verb 是方向名且无参时重写为 go"的别名变体，与段 1 全局方向别名语义连贯，故放在参数解析前）。
- emote / channel 两分支在阶段 1 不实现（emote/频道后置，[12](../xkx-arch/12-阶段1-核心循环实施计划.md) 不做清单），段 3 命令查找未命中时直接返回 0（对齐 LPC 四分支全未命中返回 0）。
- LPC `process_input` 预处理（刷屏/历史/别名）映射到段 0 + 段 1，是 `command_hook` 之前的阶段（LPC `process_input` 先于 `command_hook` 执行）。
- `SECURITY_D->valid_cmd` 在 LPC 中是 `find_command` 内部调用（找到命令文件后校验），新引擎将其独立为段 2（权限校验先于命令查找），原因是：CapabilityToken 是不可伪造的能力令牌（非 LPC euid 字符串），权限校验独立成段便于 fail-closed 语义清晰化 + 审计点单一。

**段顺序不变量**：段 0 刷屏检测必须最先（防止刷屏命令绕过权限校验）；段 2 权限校验必须在段 3 命令查找前（fail-closed，未授权命令视为不存在，对齐 LPC `valid_cmd` 不通过返回 0）；段 6 previous_object 注入必须在段 7 执行前（执行段依赖 ActionContext.actor/source/target）。

### 2. ActionContext 三元组（PronounContext viewer 不变量）

ActionContext 是 8 段管线的数据信封（非类层级，Q3 裁决"不另起类抽象"），携带：

```python
@dataclass(frozen=True, slots=True)
class ActionContext:
    verb: str                       # 命令动词（LPC query_verb()）
    raw_args: str                   # 原始参数（去动词后）
    parsed_args: list[str]          # 段 5 解析后参数
    actor: int                      # 发起者 entity_id（LPC this_player() / this_object()）
    source: int                     # 调用源 entity_id（LPC previous_object()，详见 ADR-0021）
    viewer: int                     # 观察者 entity_id（PronounContext 不变量）
    target: int | None              # 目标 entity_id（LPC visible(me, ob) 的 ob）
    capability_token: CapabilityToken | None   # 段 2 注入，None=未授权
    seq: int                        # 命令序列号（input log 重放用）
    result: list[str]               # 段 7 执行产出消息
    effects: list[Effect]           # 段 7 执行产出的副作用账本
```

**三元组 actor/viewer/target 语义**（PronounContext 不变量，[CLAUDE.md](../../CLAUDE.md) 关键不变量 + [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `visible` 实证）：

- **actor**（LPC `this_player()` / `this_object()`）：命令发起者，也是 `command_hook` 的 `this_object()`。go 命令的移动者、kill 命令的攻击者、give 命令的给予者。
- **viewer**（LPC `this_player()` 在 `rankd.c` / `visible` 中的观察者角色）：代词求值的观察者。`rankd.c` 的 `query_close`/`query_self_close` 依赖 `this_player()->query("age")` 决定称呼（长辈/平辈/晚辈），`visible(me, ob)` 中 `me=this_object()=viewer` 判定 `ob` 是否可见。**viewer 与 actor 在玩家命令路径下通常相同**（玩家发起命令时，this_player() 既是 actor 也是 viewer），但在 force_me / NPC AI 路径下可能不同（系统代玩家执行命令时，viewer 是被代执行的玩家，actor 是系统 source）。
- **target**（LPC `visible(me, ob)` 的 `ob` / 战斗的 `victim`）：命令的目标对象。kill 的被攻击者、give 的接受者、ask 的对话对象。`None` 表示无目标命令（go/look/quest）。

**不变量**：

- `actor` / `viewer` / `source` 必须在段 6 注入完成，段 7 执行段可依赖三者已就位。
- PronounContext 求值（rankd 代词 / visible 可见性）必须从 ActionContext 取 viewer，不得从全局 `this_player()` 取（greenfield 无全局 this_player()，LPC 的 this_player() 是 driver 级线程局部变量，单进程 asyncio 下无等价物）。
- `capability_token` 在段 2 注入；段 3-7 可读取但不能修改（frozen dataclass）。force_me / PrivilegedAction 路径注入 ROOT 等价 token（详见决策 4）。

### 3. CapabilityToken 实现（HS256 + 内存吊销集合，02 裁决）

[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 + [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 1：LPC euid/uid 字符串模型映射为不可伪造的 CapabilityToken。02 裁决明确"HS256/内存 session token + 内存吊销集合，不引入 JWT RS256 + Redis 黑名单"。

```python
@dataclass(frozen=True, slots=True)
class CapabilityToken:
    subject: int            # entity_id（LPC euid 等价）
    status: WizLevel        # 巫师等级（LPC get_status()，PLAYER/IMMORTAL/.../ADMIN）
    capabilities: frozenset[str]   # 能力集（如 "cmd.adm"、"root"、"valid_write./u/"）
    issued_at: float        # 签发时间
    expires_at: float       # 过期时间（session 时长）
    signature: bytes        # HS256 签名（subject + status + capabilities + issued_at + expires_at）
```

**实现决策**：

- **HS256 对称签名**：引擎启动时生成一次性 secret（`secrets.token_bytes(32)`），进程内持有，不持久化（重启后所有 token 失效，玩家需重新登录）。HS256 而非 RS256：单进程无需非对称密钥分发，02 裁决明确不引入 JWT RS256 + Redis 黑名单。
- **不可伪造**：`CapabilityToken` 是 frozen dataclass，`signature` 由 secret 对 `(subject, status, capabilities, issued_at, expires_at)` 做 HMAC-SHA256 生成。段 2 权限校验先验签（`hmac.compare_digest`），签名不符则 fail-closed 拒绝。
- **内存吊销集合**：`set[bytes]`（token 的 signature 哈希），玩家断线 / quit / 被封禁时加入吊销集合。段 2 校验时检查 signature 是否在吊销集合中，命中则拒绝。内存集合不持久化（重启后吊销集合清空，但所有 token 也失效，等价全量吊销）。
- **能力集映射 LPC 权限模型**：
  - `status=PLAYER` -> capabilities 含 `cmd.std` / `cmd.skill` / `cmd.usr`（对齐 `valid_cmd` cmds/std/skill/usr 开放）
  - `status=ADMIN` -> capabilities 含 `cmd.adm` / `root`（对齐 ROOT_UID 直接返回 1）
  - exclude 优先于 authorized：`exclude_cmds[dir]` 命中则从 capabilities 中移除对应能力，即使 status 匹配 authorized 等级也拒绝（对齐 `valid_cmd` exclude 优先 authorized 不变量）
- **fail-closed**：token 为 None / 签名无效 / 已吊销 / 已过期 / 能力不足时，段 2 返回 Abort，命令视为不存在（对齐 LPC `valid_cmd` 返回 0，不泄露命令存在性）。

**与 [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 的衔接**：ADR-0014 决策 1 定 securityd -> PermissionService + CapabilityToken，本 ADR 定 CapabilityToken 的具体实现（HS256 + 内存吊销）。PermissionService 是签发 + 校验的服务对象（`PermissionService.issue_token(entity_id, status)` / `verify_token(token)` / `revoke(token)`），CapabilityToken 是不可伪造的值对象。CLAUDE.md 要求安全模块类型完整，CapabilityToken + PermissionService 全部类型注解。

### 4. force_me = PrivilegedAction（ROOT 门控 + 强制审计，dissent 6 护栏）

[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 决策 6 + 最强反论回应：force_me 是 PrivilegedAction（Command 变体），显式承认是保真让步。LPC 4 个真实调用点（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 最强反论）：`updated.c:177` 强制传闻广播（系统发起）、`cost.c:18` 巫师工具、`to.c:20-21` 语音重定向。

**PrivilegedAction 设计**：

- **API**：`PrivilegedAction.force(actor: int, cmd: str, source: int) -> list[str]`，source 必须是 ROOT 等价实体（系统 daemon / 可信 System 代码）。
- **ROOT 门控**：`source` 必须持有 `root` capability（对齐 LPC `geteuid(previous_object())==ROOT_UID`），否则 raise `PermissionError`（非静默拒绝，因 PrivilegedAction 是系统级 API，误调是 bug）。
- **强制审计**：每次 PrivilegedAction.force 调用写一条 `PRIVILEGED_ACTION` 审计日志（actor / source / cmd / timestamp / result 摘要），独立于段 7 普通审计日志，便于 dissent 6 "靠审计/限制调用点"的调用点监控。
- **走完整 8 段管线**：PrivilegedAction 不绕过管线，而是构造一个 `capability_token=ROOT_TOKEN` 的 ActionContext 注入段 0，走完整 8 段（保 LPC `force_me` 经 `process_input` + `command_hook` 的语义，[spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) `_func_force_me` side_effects 已验证）。这保证 force_me 的命令也过刷屏检测 / 别名解析 / 权限校验（ROOT_TOKEN 全能力通过）/ 命令查找 / 执行 + 审计。
- **viewer 注入**：PrivilegedAction 路径下 viewer=actor（被代执行的玩家是观察者），source=系统调用者。这与玩家命令路径（actor=viewer=source=玩家）不同，但 PronounContext 求值仍从 ActionContext.viewer 取，不变量不破坏。

**dissent 6 护栏**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6）：

- **调用点白名单**：PrivilegedAction.force 的调用点必须在代码 review 时显式登记（初始 4 处对应 LPC 4 调用点），新增调用点需 ADR 记录理由。阶段 1 验收时扫描代码库 `PrivilegedAction.force` 调用点数量，与登记白名单比对，超出即 dissent 6 触发告警。
- **NPC AI 不得使用**：NPC AI 走 heart_beat / do_attack / System.update 路径（Q3 决策 3），不调 PrivilegedAction.force。若未来 NPC AI 需"代玩家执行命令"语义，优先走 System.update 直接 mutate（保边界纯净），仅在必须复用命令路径时才用 PrivilegedAction（需 ADR）。
- **触发器不得使用**：DSL 层1 触发器（valid_leave / accept_object）的 action 是 Effect 账本附加到父 Command，不另起 PrivilegedAction（Q3 决策 5）。

### 5. 段 7 审计日志（与 PrivilegedAction 审计分离）

段 7 执行后写一条 `COMMAND_AUDIT` 日志（actor / verb / args / target / result 摘要 / timestamp / seq），用于：

- 行为等价验证（combat-sim 重放时对照命令时序）
- dissent 6 调用点监控（普通命令审计 + PrivilegedAction 审计分离，便于区分"玩家意图"与"系统代执行"）
- kill criteria 3 性能分析（tick profiler 统计命令执行耗时）

审计日志是内存 ring buffer（阶段 1 不持久化，外部玩家测试前才需持久化审计轨迹，04 §六后置）。

## 不做（范围边界）

- **不新建 Command 类层级**（Q3 裁决"不另起类抽象"）：ActionContext 是 frozen dataclass 信封，不是抽象基类；各命令是纯函数 `(game, ctx) -> list[str]`，不继承 `Command` 基类。抵抗向 ActionContext 添加方法 / 继承层级的诱惑。
- **不把 System.update 包成 Command**（Q3 裁决"System tick 派生变更不经 Command"）：heal / condition 过期 / combat do_attack / NPC AI 走 System.update 直接 mutate ECS 组件，不经 8 段管线。1s tick 下避免热路径对象 churn（GC 压力）。
- **不实现 emote / channel 分支**（阶段 1 后置，[12](../xkx-arch/12-阶段1-核心循环实施计划.md) 不做清单）：段 3 命令查找未命中时直接返回 0，emote/频道后置阶段 2/ M3。
- **不实现玩家自定义别名**（[spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) 边界"玩家自定义别名后置"）：段 1 仅处理全局方向别名 + 历史替换，玩家 `set_alias` 管理后置。
- **不引入 JWT RS256 + Redis 黑名单**（02 裁决）：HS256 对称签名 + 内存吊销集合，单进程无需分布式 token 基础设施。
- **不持久化 CapabilityToken**：token 是 session 级，重启失效，玩家重新登录。存档（T5）只持久化 entity 状态（status/capabilities 派生自 WizLevel），不持久化 token 本身。
- **不持久化审计日志**（阶段 1 后置）：内存 ring buffer，外部玩家测试前才需持久化审计轨迹。
- **不做异步命令队列**（Q3 裁决"反对默认异步化"）：段 7 执行同步返回结果（保 LPC `call_other` 同步语义，68771 处调用栈），asyncio WS 收命令后同步走 8 段管线（T7 WS 服务器设计）。
- **不做全量 LPC parse_command**：段 5 参数解析阶段 1 最小集（引号感知 tokenizer），LPC `parse_command` 完整语义后置。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：重构为 8 段中间件管线 + ActionContext + 10 命令适配
- [runtime/action_context.py](../../engine/src/xkx/runtime/action_context.py)：`ActionContext` frozen dataclass + `Abort` 信号
- [runtime/capability.py](../../engine/src/xkx/runtime/capability.py)：`CapabilityToken` + `PermissionService`（issue/verify/revoke，HS256 + 内存吊销集合）
- [runtime/privileged.py](../../engine/src/xkx/runtime/privileged.py)：`PrivilegedAction.force`（ROOT 门控 + 强制审计）
- [runtime/middleware/](../../engine/src/xkx/runtime/middleware/)：8 段中间件各一文件（`s0_flood_check.py` ... `s7_execute_audit.py`）
- [tests/test_command_pipeline.py](../../engine/tests/test_command_pipeline.py)：8 段管线行为等价（go/kill/ask/give/quest 等 10 命令）/ 段顺序不变量 / Abort 短路
- [tests/test_capability_token.py](../../engine/tests/test_capability_token.py)：HS256 签发/验签 / 内存吊销 / fail-closed / 能力集映射 LPC 权限模型 / hypothesis 不可伪造性
- [tests/test_privileged_action.py](../../engine/tests/test_privileged_action.py)：ROOT 门控 / 强制审计 / 调用点白名单 / NPC AI 禁用

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（force_me 边界侵蚀）：PrivilegedAction ROOT 门控 + 强制审计 + 调用点白名单 + NPC AI 禁用，回应"靠审计/限制调用点"
- [02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 Command 模式裁决（8 段管线信封 + 仅外部意图 + force_me 保真让步）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1 M1-7（命令管线 + ActionContext + CapabilityToken）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T4（本任务）
- [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 1（securityd -> PermissionService + CapabilityToken，本 ADR 定 CapabilityToken 实现）
- [ADR-0021](ADR-0021-previous-object-explicit-mapping.md) previous_object 155 处显式化（本 ADR 段 6 注入的 source/target 字段来源）
- [spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) `command_hook` 四分支 + `process_input` 预处理 + `find_command` 逆序 + `force_me`（规格源）
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) `SECURITY_D valid_cmd` fail-closed（规格源）
- [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `visible(me, ob)` viewer/target 语义（PronounContext 不变量实证）
