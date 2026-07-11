# ADR-0024：WS 协议 + 重连策略（ring vs snapshot）+ AccountService

- 状态：草案（Wave 3 T7 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 3 T7
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1（M1-4 WS 服务器）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 8（存储收缩丢失语义）+ 专家 2 承重论断 4（Command 仅覆盖外部意图）/ [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T7 / [ADR-0014](ADR-0014-daemon-responsibility-redesign.md)（logind -> ConnectionSystem + AccountService 决策 7）/ [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md)（8 段命令管线，WS 收命令 -> 管线）/ [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（StorageSystem，玩家状态存档）/ [02](../xkx-arch/02-三个开放架构问题裁决.md)（HS256/内存吊销集合裁决）/ [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py)（LOGIN_D 13 阶段 + LoginState 枚举）/ [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py)（visible 三级 + save 三步 + net_dead/reconnect）

## 背景

[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T7 任务卡（第 212-225 行）：asyncio WS 服务器承载会话 + argon2 密码 + HS256 session token + 断线重连（ring 重放 / snapshot 降级）。验收三件：单进程承载会话 + 断线重连 ring/snapshot 切换正确 + argon2 密码验证通过。

**现有资产（Wave 1/2 已产出，T7 在此基础上接入）**：

- [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 8 段命令管线 + ActionContext + CapabilityToken（WS 收 command 帧 -> run_pipeline 执行）。
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) StorageSystem + JsonFileBackend（玩家权威态存档，原子写 + offload + dirty-flag）。
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py) COMMAND_REGISTRY + run_pipeline + dispatch（T4 产出，WS 入口直接调）。
- [runtime/capability.py](../../engine/src/xkx/runtime/capability.py) PermissionService（T4 产出，WS 服务器注入 dispatch 段 2 权限校验）。
- [cli.py](../../engine/src/xkx/cli.py) CLI REPL 命令解析（参考其命令分发，迁到 WS 入口）。
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) LOGIN_D 13 阶段状态机 + LoginState 枚举 + SECURITY_D valid_cmd（fail-closed）+ NATURE_D 时间系统。
- [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) visible 三级判定（巫师等级 > invisibility > 鬼魂）+ user.c save 三步（save_autoload -> ::save -> clean_up_autoload）+ net_dead/reconnect/user_dump。

**dissent 8 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 8 条）：

> 存储收缩丢失语义：JSON 丢失事务原子性/崩溃恢复/CAS。会话状态（session token 吊销/重连 ring）若持久化会撞此张力。

本 ADR 落地裁决：**会话态进程内内存**（ring buffer + 吊销集合），不持久化（崩溃丢失可接受，玩家重新登录即可）；**玩家权威态走 T5 StorageSystem 存档**（已原子写）。这是"会话态非权威态"的显式取舍。

**02 裁决**（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3）：

> 不引入 JWT RS256 + Redis 黑名单；单进程无跨进程鉴权，HS256/内存 session token + 内存吊销集合。

**CLAUDE.md 不变量**：

- tick=1s + compute<100ms + 非均匀 tick（ConnectionSystem tick 驱动会话超时）。
- PronounContext 必须携带 viewer（WS 事件推送 visible 过滤）。
- JSON 存档崩溃安全（玩家态走 T5，会话态不持久化）。
- Command 仅覆盖外部意图（WS command 帧 -> 管线；System tick 不经 Command）。

## 决策

### 1. WS 协议（JSON 帧格式，三类主帧 + 登录子协议）

帧类型（JSON 文本帧，UTF-8）：

| 帧类型 | 方向 | 字段 | 用途 |
|---|---|---|---|
| `command` | C->S | `type, verb, args, seq` | 玩家命令（go/kill/ask 等，进 8 段管线） |
| `result` | S->C | `type, seq, messages, effects` | 命令结果（管线 dispatch 产出） |
| `event` | S->C | `type, event_type, data, seq` | 异步事件（房间消息/战斗消息/频道，server 推） |
| `login` | C->S | `type, state, input` | 登录交互（驱动 LOGIN_D 状态机） |
| `login_state` | S->C | `type, state, prompt` | 登录提示（当前状态 + 期望输入） |
| `resume` | C->S | `type, token, last_seq` | 断线重连（携带 session token + 最后收到 seq） |
| `resumed` | S->C | `type, mode, events` | 重连结果（mode=ring\|snapshot，events=补发事件） |

**登录子协议**：WS 连接建立后先走 `login` 帧（logon -> get_id -> get_passwd -> enter_world），enter_world 成功后签发 session token，后续帧走 `command`/`result`/`event`。重连用 `resume` 帧。

> 帧格式最小化，不引入 protobuf/MsgPack（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六收敛，JSON 足够，阶段 1 1000+100 不涉及带宽瓶颈）。seq 单调递增（每会话独立），用于 ring 重放对齐。

### 2. 重连策略（ring 重放 + snapshot 降级，切换条件）

每会话维护 **ring buffer**（进程内 `collections.deque`，存储近期 `event` 帧，默认 100 条或 30 秒，T10 实测后调）。

重连判定（`resume` 帧 `{token, last_seq}`）：

1. 验签 token + 查会话表（token 吊销/会话不存在 -> 拒绝重连，走完整 `login`）。
2. `last_seq >= ring_head`（ring 最早 seq）：**ring 重放**，发 ring 中 `last_seq` 之后的 event。
3. `last_seq < ring_head`（断线太久，ring 已覆盖）：**snapshot 降级**，发全量快照（玩家位置/状态/房间可见实体），后续转正常推送。
4. `last_seq` 缺失（首次重连或客户端无记录）：snapshot 降级。

切换条件 = ring 容量 vs 断线时长。阶段 1 默认 ring=100 条/30 秒，T8 tick profiler + T10 集成测试提供数据后调。

> ring buffer 进程内内存，不持久化（崩溃丢失可接受，玩家重新登录）。snapshot 由 T5 存档恢复玩家权威态 + 运行时 ECS 现场构建房间可见实体（非独立快照存储）。

### 3. AccountService（argon2 + 账号管理，ADR-0014 决策 7）

[ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 7：regid -> AccountService，argon2 替换 LPC `crypt()`。

- **argon2id 密码哈希**（替换 LPC `crypt()`，抗 GPU/ASIC 暴力破解）。
- **账号注册**：`check_legal_id`（3-8 小写字母，[spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) `_check_legal_id`）+ `check_legal_name`（1-4 中文，`_check_legal_name`）+ `random_gift`（天赋生成，str+int+con+dex+end=100，kar+pat+per=60，`_random_gift`）。
- **账号存储**：JSON 文件（衔接 T5 StorageSystem，每账号一文件 `DATA_DIR/account/<id>.json`，含 password_hash + 天赋 + 基础属性）。
- **密码验证**：`argon2.verify(input, stored_hash)`。
- **自杀列表**（SUICIDE_LIST）：阶段 1 简化为内存集合（测试期无自杀账号），完整文件扫描后置。

> AccountService 是**无状态服务**（非 System），密码哈希 + 账号查询纯函数式。账号权威态走 T5 存档。依赖 `argon2-cffi`（pyproject.toml 加）。

### 4. HS256 session token（签发/验签/吊销，02 裁决）

[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 裁决：HS256/内存 session token + 内存吊销集合。

- **签发**：`enter_world` 成功后签发 `{account_id, exp, nonce}` HS256 签名（密钥进程内，启动期生成或配置读取）。
- **验签**：`resume` 帧验签 + 查内存吊销集合（命中即拒绝）。
- **吊销**：断线超时（NET_DEAD_TIMEOUT 后 user_dump）/ 主动登出 / 管理员踢人 时吊销（加入内存吊销集合）。
- **内存吊销集合**：进程内 `set`，崩溃清空（玩家重新登录即可，02 裁决不引入 Redis 黑名单）。

> session token 不持久化（进程内内存），崩溃后所有会话失效，玩家重新登录。这是 dissent 8 存储收缩的取舍：**会话态非权威态，丢失可接受**；玩家权威态（角色属性/位置/物品）走 T5 存档，崩溃冷重启可恢复。

### 5. LOGIN_D 13 阶段状态机映射（WS 登录子协议）

`LoginState` 枚举（[spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) 已定义 14 状态）映射 WS 登录子协议。LPC `input_to(state, ob)` 语义 -> WS `login_state` 帧（prompt + 期望输入），玩家 `login` 帧驱动状态转换。

**阶段 1 完整实现**（M1-4 验收要求 + 1000+100 测试需批量建号）：

- 老玩家登录：`logon` -> `get_id` -> `get_passwd` -> `enter_world`。
- netdead 重连：`get_passwd` -> `find_body` -> `reconnect`。
- 新人物创建：`get_id`（存档不存在）-> `confirm_id` -> `get_name` -> `new_password` -> `confirm_password` -> `get_gift` -> `get_email` -> `get_gender` -> `make_body` -> `init_new_player` -> `enter_world`。

**阶段 1 简化项**（后置，不阻塞 M1-4）：

- BIG5/GB 编码选择（`confirm_big5`）：`languaged` 砍掉，UTF-8 统一，跳过该状态。
- `wiz_lock` / `REGBAN_D` / `valid_wiz_login`（巫师登录 IP 白名单）：阶段 1 无巫师账号或预置，跳过。
- `MARRY_D->validate_marriage` / `UPDATE_D->login_check` / 豹胎易筋丸检查：后置。
- `random_gift` 50 次 `random(5)`：阶段 1 保留完整逻辑（纯计算，非 combat 范围，不需要确定性 RNG），但天赋 reroll（`get_gift` 的 y/Y 分支）可简化为单次确认。

### 6. ConnectionSystem（ADR-0014 第 6 个 System，tick 驱动会话管理）

[ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 盘点的第 6 个 ECS System，与 logind 合并实现（logind 登录流程 + ConnectionSystem 会话管理，同一 System 两职责）。

- **tick 驱动**（tick=1s 非均匀，CLAUDE.md 不变量）：扫描会话表，检测超时。
- **会话表**：`session_id -> ConnectionSession`（account_id, ws, ring, last_seq, state, last_active, body_eid）。
- **LOGIN_TIMEOUT**：登录状态机超时（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `login.c time_out`），超时关闭 WS。
- **NET_DEAD_TIMEOUT**：断线后保留 body 的超时（`user.c user_dump` DUMP_NET_DEAD），超时强制 quit。
- **IDLE_TIMEOUT**：发呆超时（`user_dump` DUMP_IDLE），巫师豁免（阶段 1 无巫师，全部踢）。
- **net_dead 检测**：WS 关闭/心跳超时 -> `set_temp('netdead', 1)` + 安排 user_dump 定时器 + 通知房间。
- **reconnect 恢复**：`set_heart_beat(1)` + 清除 netdead + 取消 user_dump（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_user_reconnect`）。

> ConnectionSystem 继承 T1 System 基类（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)），`update(world, dt, ctx)` 扫描超时。会话表进程内内存（非 ECS 组件，因会话非实体态）。

### 7. visible 三级判定 + PronounContext viewer（WS 事件推送过滤）

WS `event` 帧推送时用 `visible` 过滤（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_visible`）：

- **viewer** = 玩家（会话对应的 body）。
- **target** = 房间内实体（NPC/物品/其他玩家）。
- **三级判定**：巫师等级 > invisibility > 鬼魂（优先级递减）。

`PronounContext` 三元组（speaker/viewer/target，CLAUDE.md 不变量）在 WS 事件中：

- **speaker** = 事件发起者（NPC/系统/其他玩家）。
- **viewer** = 当前会话玩家（决定 visible + 代词渲染）。
- **target** = 事件涉及对象。

> visible 过滤确保玩家只收到可见实体的事件（隐身/鬼魂不可见）。PronounContext viewer 是 CLAUDE.md 不变量（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) ActionContext 已携带 viewer，WS 推送复用）。

## 不做（范围边界）

- **不做 JWT RS256 + Redis 黑名单**（[02](../xkx-arch/02-三个开放架构问题裁决.md) 裁决，HS256/内存吊销集合）。
- **不做 uvloop**（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六，stdlib asyncio 优先，基准显示 I/O 瓶颈时启用）。
- **不做分布式网关**（单进程 WS 足够，[04](../xkx-arch/04-迁移路径与避坑清单.md) §六）。
- **不做 intermud 跨服**（dns_master/ftpd/socket 砍掉，[ADR-0014](ADR-0014-daemon-responsibility-redesign.md)）。
- **不做 BIG5/GB 编码选择**（UTF-8 统一，`languaged` 砍掉，[ADR-0014](ADR-0014-daemon-responsibility-redesign.md)）。
- **不做会话态持久化**（进程内内存，崩溃丢失可接受，dissent 8 取舍；玩家权威态走 T5 存档）。
- **不做完整 LOGIN_D 13 阶段的每个细节**（简化项见决策 5，后置不阻塞 M1-4）。
- **不做 MARRY_D/UPDATE_D login_check / 豹胎易筋丸 / 巫师 IP 白名单**（后置）。
- **不做 ring buffer 持久化**（进程内，崩溃清空，玩家重新登录走 snapshot 降级）。
- **不做 WS 子协议的版本协商**（单版本，阶段 1 无多客户端兼容需求）。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/ws_server.py](../../engine/src/xkx/runtime/ws_server.py)（新）：asyncio WS 服务器 + 帧编解码 + 会话生命周期 + 连接接受/关闭。
- [runtime/connection.py](../../engine/src/xkx/runtime/connection.py)（新）：ConnectionSystem（tick 驱动会话超时）+ ConnectionSession + ring buffer。
- [runtime/account.py](../../engine/src/xkx/runtime/account.py)（新）：AccountService（argon2 + 账号注册/验证 + check_legal_id/name + random_gift）。
- [runtime/session.py](../../engine/src/xkx/runtime/session.py)（新）：HS256 session token 签发/验签/吊销（内存吊销集合）。
- [runtime/login.py](../../engine/src/xkx/runtime/login.py)（新）：LOGIN_D 13 阶段状态机（WS 登录子协议驱动，LoginState 映射）。
- [tests/test_ws_server.py](../../engine/tests/test_ws_server.py)（新）：WS 协议帧 + 登录 + 命令分发测试。
- [tests/test_connection_system.py](../../engine/tests/test_connection_system.py)（新）：会话超时 + net_dead + reconnect + ring/snapshot 切换测试。
- [tests/test_account_service.py](../../engine/tests/test_account_service.py)（新）：argon2 + 账号注册/验证 + check_legal_id/name + random_gift 不变量测试。
- [tests/test_session_token.py](../../engine/tests/test_session_token.py)（新）：HS256 签发/验签/吊销/过期测试。
- [tests/test_login_state_machine.py](../../engine/tests/test_login_state_machine.py)（新）：LOGIN_D 13 阶段状态机转换 + 新人物创建 + 重连路径测试。
- [pyproject.toml](../../engine/pyproject.toml)：加 `argon2-cffi` 依赖。

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 8（存储收缩丢失语义）：会话态进程内内存不持久化，玩家权威态走 T5 存档。
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 2 承重论断 4（Command 仅覆盖外部意图）：WS 收 command 帧 -> T4 管线，System tick 不经 Command。
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1（M1-4 WS 服务器）/ §六不做（uvloop/分布式网关/intermud/BIG5）。
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T7（本任务）/ T10（1000+100 集成测试，WS 服务器性能验证）。
- [ADR-0014](ADR-0014-daemon-responsibility-redesign.md)（logind -> ConnectionSystem + AccountService 决策 7，第 6 个 System）。
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（T1 System 基类，ConnectionSystem 继承）。
- [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md)（8 段命令管线 + ActionContext viewer，WS 收命令 -> 管线）。
- [ADR-0021](ADR-0021-previous-object-explicit-mapping.md)（previous_object 显式化，LOGIN_D 的 this_player/previous_object 映射）。
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（StorageSystem，玩家权威态存档 + 崩溃冷重启）。
- [02](../xkx-arch/02-三个开放架构问题裁决.md) Q3（HS256/内存吊销集合裁决，force_me=PrivilegedAction 保真让步）。
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py)（LOGIN_D 13 阶段 + LoginState + SECURITY_D valid_cmd + NATURE_D 时间）。
- [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py)（visible 三级 + save 三步 + net_dead/reconnect/user_dump）。
