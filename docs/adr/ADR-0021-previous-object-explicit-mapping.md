# ADR-0021：previous_object 显式化策略（155 处映射）

- 状态：草案（Wave 2 T4 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 2 T4
- 关联：[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 M1-7（previous_object 显式化 155 处）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（force_me 边界侵蚀，靠审计/限制调用点）/ [02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 决策 2（ActionContext + CapabilityToken 替换 previous_object/geteuid 信任链，155 处实证）/ [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T4 / [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 段 6 previous_object 注入 + ActionContext.source 字段

## 背景

[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 决策 2："ActionContext + CapabilityToken 替换 `previous_object`/`geteuid` 信任链（155 处实证），仅作用于 Command 路径。"[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T4 任务卡产出项："previous_object 显式化（LPC `this_player()` / `previous_object()` 155 处映射）"。

**LPC previous_object() 语义**（只读规格源）：

- `previous_object()` 返回**最近一次 `call_other` 的调用者对象**（LPC driver 维护的隐式调用栈顶）。它是 LPC 信任链的核心：被调函数通过 `previous_object()` 反查"谁在调我"，再用 `geteuid(previous_object())` 判定调用者权限。
- `this_player()` 返回**当前命令的发起者**（driver 级线程局部变量，由 `command_hook` 设置）。它在 `command_hook` 执行期间对所有被调函数可见，是 LPC 命令路径的"当前玩家"。
- `this_object()` 返回**当前函数所属对象**（静态，编译期确定）。

**155 处实证**（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3）：LPC 侠客行代码库中 `previous_object()` / `this_player()` 相关权限检查约 155 处，典型分布：

- `geteuid(previous_object()) == ROOT_UID` 门控（`force_me` / `disable_player` / `set_status` / `set` nomask 等，[spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) `_func_force_me` precondition + [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) `_set_status` precondition）
- `previous_object() == this_object()` 自调用检查（`disable_player`，[spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) `_func_disable_player` precondition）
- `previous_object() == find_object("/cmds/adm/promote")` 特定调用者检查（`set_status`，[spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) `_set_status` precondition）
- `visible(me, ob)` 中 `me=this_object()=this_player()=viewer`（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_visible`）
- `rankd.c` `query_close`/`query_self_close` 依赖 `this_player()->query("age")`（[ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 3 实证）

**greenfield 问题**：单进程 asyncio 无 driver 级线程局部变量，无隐式调用栈顶。若保留"全局 this_player()"会引入全局可变状态（违反 ECS 纯函数原则 + 1000 并发下竞态）。必须将 `previous_object()` / `this_player()` 的隐式信任链显式化为 ActionContext 字段。

**dissent 6 关联**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6）：force_me 边界侵蚀的缓解措施是"靠审计/限制调用点"。previous_object 显式化是审计前提--只有调用源（source）成为 ActionContext 的显式字段，才能审计"谁在调 PrivilegedAction.force"，否则调用点隐藏在 LPC 隐式调用栈中无法审计。

## 决策

### 1. 映射表：LPC 隐式信任链 -> ActionContext 显式字段

| LPC 隐式原语 | greenfield 显式字段 | 语义 |
|---|---|---|
| `this_player()` | `ActionContext.actor` | 命令发起者（command_hook 设置的"当前玩家"） |
| `previous_object()` | `ActionContext.source` | 调用源（最近一次 call_other 的调用者，greenfield 为显式传参） |
| `this_object()` | 函数所属实体（Python 方法绑定的 entity_id） | 当前函数所属对象（静态，无需字段） |
| `geteuid(previous_object())` | `ActionContext.source.capability_token` | 调用源的能力令牌（不可伪造，替代 euid 字符串） |
| `geteuid(previous_object()) == ROOT_UID` | `source.capability_token` 含 `root` capability | ROOT 门控（PrivilegedAction 用） |
| `previous_object() == this_object()` | `source == actor` | 自调用检查 |
| `previous_object() == find_object(X)` | `source == X` 的实体 | 特定调用者检查（promote 命令等） |
| `this_player()` 在 `rankd`/`visible` 中 | `ActionContext.viewer` | 代词求值 / 可见性判定的观察者 |

**关键区分**（LPC `this_player()` vs `previous_object()` 的 greenfield 映射）：

- LPC `this_player()` 在命令路径下是 `command_hook` 设置的"当前玩家"，映射为 `ActionContext.actor`。
- LPC `previous_object()` 是"谁在调我"，映射为 `ActionContext.source`。
- 玩家命令路径下 `this_player() == previous_object() == this_object()`（玩家对象调自己的命令），greenfield 下 `actor == source`。
- force_me / PrivilegedAction 路径下 `this_player()` = 被代执行的玩家，`previous_object()` = 系统调用者，greenfield 下 `actor` = 被代执行的玩家，`source` = 系统调用者，`actor != source`。

### 2. 映射策略：155 处分三类处置

**A 类：Command 路径权限检查（约 60 处）-> ActionContext.source + capability_token**

典型：`force_me` / `disable_player` / `set` nomask / `set_status` 的 `geteuid(previous_object()) == ROOT_UID` 门控。

- greenfield 处置：这些检查在 8 段管线的段 2（权限校验）+ 段 6（previous_object 注入）完成。段 2 校验 `ActionContext.capability_token` 是否含所需 capability（如 `root` / `cmd.adm`），段 6 注入 `source` 字段。
- 被调函数（如 `PrivilegedAction.force`）从 ActionContext 取 `source.capability_token` 判定 ROOT 门控，不再依赖隐式 `previous_object()`。
- CapabilityToken 不可伪造（HS256 签名，[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 决策 3），替代 LPC euid 字符串的"可伪造但 driver 保护"模型。

**B 类：PronounContext / 可见性求值（约 40 处）-> ActionContext.viewer**

典型：`rankd.c` `query_close`/`query_self_close` 的 `this_player()->query("age")`、`visible(me, ob)` 的 `me=this_object()=viewer`。

- greenfield 处置：代词求值函数（PronounService）和可见性判定函数（`visible` 等价）签名改为 `(viewer: int, target: int, world: World) -> ...`，viewer 从 ActionContext 取。
- 不变量（[CLAUDE.md](../../CLAUDE.md) 关键不变量 + [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 3）：PronounContext 必须携带 viewer，三元组 speaker/viewer/target。greenfield 无全局 this_player()，viewer 必须显式传参。
- 玩家命令路径下 viewer == actor；PrivilegedAction 路径下 viewer == actor（被代执行的玩家是观察者），source == 系统调用者。

**C 类：System.update 路径（约 55 处）-> SystemContext（非 ActionContext）**

典型：heart_beat / do_attack / heal / condition 过期中的 `this_player()` / `previous_object()` 检查。

- greenfield 处置：System.update 路径不经 Command 管线（Q3 裁决"System tick 派生变更不经 Command"），无 ActionContext。这些路径的 `previous_object()` 检查在 LPC 中多是防御性代码（防止 System 函数被外部误调），greenfield 下 System.update 由引擎调度器（TickRunner）调用，不存在"外部误调"场景，**这些检查直接删除**。
- 若 System 路径确需审计 / 能力钩子（如 combat do_attack 需记录"谁打的谁"），携带轻量 `SystemContext`（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 未消除风险"System 路径 ActionContext 分歧"裁决："System 路径携带轻量 SystemContext 供能力/审计钩子但派生变更不进 input log"）。SystemContext 只含 actor/target（无 source/capability_token，因 System 无"调用源"概念）。

**映射表产出**：构建 `PREVIOUS_OBJECT_MAP`（LPC `previous_object()`/`this_player()` 调用点 -> A/B/C 类 + greenfield 字段），类比 T3 的 `DBASE_KEY_MAP`（LPC dbase key -> 组件字段）。映射表是文档 + 代码常量，启动期校验（衔接 [ADR-0019](ADR-0019-schema-registry-and-dsl-validator-boundary.md) SchemaRegistry 的"启动期失败"思路：映射目标字段不存在则启动期失败）。

### 3. 调用点审计策略（dissent 6 "靠审计/限制调用点"）

dissent 6 缓解措施"靠审计/限制调用点"在 greenfield 下的落地：

**a. source 字段强制显式传参**：

- greenfield 无隐式 `previous_object()`，所有需要"调用源"语义的函数必须显式接收 `source: int` 参数。Python 无 LPC driver 的隐式调用栈，显式传参是唯一选项。
- 这使所有"谁在调我"的调用点在代码中**可见**（LPC 中 `previous_object()` 隐藏调用关系，greenfield 显式化为参数流）。

**b. PrivilegedAction 调用点白名单**（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 决策 4）：

- `PrivilegedAction.force` 的调用点必须在代码 review 时登记白名单（初始 4 处对应 LPC 4 调用点：updated / cost / to 语音重定向 + disable_player 等价）。
- 阶段 1 验收时 grep 代码库 `PrivilegedAction.force` 调用点数量，与白名单比对，超出即 dissent 6 告警。
- 新增调用点需 ADR 记录理由（为何不能用 System.update 替代）。

**c. ROOT capability 签发审计**：

- `root` capability 仅由 PermissionService 在引擎启动时签发给系统实体（daemon 等价实体），运行期不签发。`PermissionService.issue_root_token(entity_id)` 每次调用写一条 `ROOT_ISSUE` 审计日志。
- 这使"谁有 ROOT 权限"在代码中可见（启动期固定签发），运行期无法新增 ROOT 实体。

**d. 段 7 审计日志 + PrivilegedAction 审计日志分离**（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 决策 4 + 5）：

- 段 7 普通命令审计（`COMMAND_AUDIT`）记录玩家意图命令。
- `PRIVILEGED_ACTION` 审计记录系统代执行命令。
- 两类日志分离便于区分"玩家意图"与"系统代执行"，dissent 6 监控"force_me 调用点增长侵蚀边界"时直接查 `PRIVILEGED_ACTION` 日志。

### 4. 映射表启动期校验（衔接 ADR-0019）

`PREVIOUS_OBJECT_MAP` 构建时校验映射目标字段合法（类比 [ADR-0019](ADR-0019-schema-registry-and-dsl-validator-boundary.md) 决策 4 `DBASE_KEY_MAP` 的 `has_field` 校验）：

- A 类映射目标：`ActionContext.source` / `ActionContext.capability_token` 字段存在（frozen dataclass 字段集校验）。
- B 类映射目标：PronounService / visible 等价函数签名含 `viewer` 参数（函数签名检查）。
- C 类映射目标：System.update 签名含 `SystemContext`（或确认该调用点检查已删除）。

若映射目标不存在（如某 LPC 调用点映射到的 greenfield 函数不存在），启动期 `MappingError`（非运行时静默）。

## 不做（范围边界）

- **不保留全局 this_player()**（greenfield 无 driver 线程局部变量）：`this_player()` 语义全部映射为 ActionContext.actor / viewer 显式字段。1000 并发下全局可变状态是竞态源。
- **不把 System.update 包成 Command 以保留 previous_object 语义**（Q3 裁决）：C 类调用点的 `previous_object()` 检查直接删除（System 无外部误调场景），不为此把 System 包成 Command。
- **不做 previous_object 调用栈还原**（LPC `previous_object(-1)` / `call_stack()` 历史调用者）：greenfield 不保留完整调用栈，仅 `source`（最近一次调用者）一字段。LPC `previous_object(-1)` 等历史栈查询无 greenfield 等价物，后置（若有真实需求再评估）。
- **不做 155 处逐一映射的完整枚举**（收敛优先于完备）：映射表覆盖 9 层规格涉及的 `previous_object()` / `this_player()` 调用点（A/B/C 三类典型），阶段 1 验收时抽样校准（类比 [ADR-0015](ADR-0015-layer-calibration-methodology.md) 校准方法论），不提前穷尽 155 处。
- **不做运行期 previous_object 动态查询**：`source` 是 ActionContext 构造时确定的 frozen 字段，运行期不可变。LPC `previous_object()` 的"动态查询当前调用者"语义无 greenfield 等价物（显式传参是静态的）。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/action_context.py](../../engine/src/xkx/runtime/action_context.py)：`ActionContext.source` 字段（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 共用）
- [runtime/previous_object_map.py](../../engine/src/xkx/runtime/previous_object_map.py)：`PREVIOUS_OBJECT_MAP`（LPC 调用点 -> A/B/C 类 + greenfield 字段）+ 启动期 `MappingError` 校验
- [runtime/pronoun.py](../../engine/src/xkx/runtime/pronoun.py)：`PronounService`（viewer/target 显式传参，替代 `this_player()` 隐式依赖）
- [runtime/system_context.py](../../engine/src/xkx/runtime/system_context.py)：`SystemContext`（轻量，System.update 路径用，含 actor/target 无 source/capability_token）
- [tests/test_previous_object_map.py](../../engine/tests/test_previous_object_map.py)：A/B/C 三类映射 / 启动期校验 / source 显式传参 / viewer 不变量
- [tests/test_privileged_action.py](../../engine/tests/test_privileged_action.py)：调用点白名单 / ROOT 门控 / 审计日志（与 [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 共用）

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（force_me 边界侵蚀）：source 显式化是"靠审计/限制调用点"的前提--调用源成为 ActionContext 显式字段才能审计，调用点白名单 + ROOT 签发审计 + 段 7/PrivilegedAction 审计分离共同落地 dissent 6 缓解
- [02](../xkx-arch/02-三个开放架构问题裁决.md) Q3 决策 2（ActionContext + CapabilityToken 替换 previous_object/geteuid 信任链，155 处实证）+ Q3 未消除风险"System 路径 ActionContext 分歧"（SystemContext 轻量裁决）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1 M1-7（previous_object 显式化 155 处）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T4（本任务）
- [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 段 6 previous_object 注入 + ActionContext.source/viewer 字段 + 决策 4 PrivilegedAction 调用点白名单
- [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 1（securityd -> PermissionService + CapabilityToken）+ 决策 3（rankd -> PronounContext 三元组，viewer 不变量实证）
- [ADR-0019](ADR-0019-schema-registry-and-dsl-validator-boundary.md) 决策 4（DBASE_KEY_MAP 启动期校验思路，本 ADR PREVIOUS_OBJECT_MAP 类比）
- [spec/layer_c_command.py](../../engine/src/xkx/spec/layer_c_command.py) `_func_force_me` / `_func_disable_player`（previous_object() 门控规格源）
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) `_set_status`（previous_object() == promote 检查规格源）
- [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_visible`（this_player() = viewer 规格源）
