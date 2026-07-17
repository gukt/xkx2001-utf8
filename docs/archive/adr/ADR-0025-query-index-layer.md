# ADR-0025：Query/索引层设计（query() 语义 + 索引 + 后置 key 激活）

- 状态：草案（阶段 2 Wave 1 前置）
- 日期：2026-07-12
- 阶段：阶段 2 Wave 1（2.1 Query/索引层）
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2（M2-1）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 2（ECS 取代 daemon，query 语义偏离 LPC F_DBASE）+ dissent 8（存储语义，新组件可序列化）/ [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.1 / [ADR-0019](ADR-0019-schema-registry-and-dsl-validator-boundary.md)（SchemaRegistry 拼写检查护栏）/ [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（SparseSet + 13 组件）/ [spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py)（F_DBASE 8 函数 + F_NAME/F_MOVE 规格）/ [13-dbase-key-map.md](../xkx-arch/13-dbase-key-map.md)（37 已映射 + 2 路径 + 55 后置）

## 背景

[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.1 任务卡：实现 LPC `query()`/`query_temp()`/`set()`/`set_temp()` 运行时语义，对照 [13-dbase-key-map.md](../xkx-arch/13-dbase-key-map.md) 映射表。完善 Identity/Position/Inventory 组件规格等价。验收：LPC `query("skill/axe")` -> `Skills.levels["axe"]` 语义等价；hypothesis 属性测试（路径前缀解析 + 未映射 key 处理）。

**现有资产（阶段 1 已产出，2.1 在此基础上补运行时语义）**：

- [dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) DBASE_KEY_MAP（37 简单 key -> 13 组件字段）+ PATH_PREFIX_MAP（`skill/` -> Skills.levels，`marks/` -> Marks.flags）+ POSTPONED_KEYS（55 后置 key）+ `resolve_dbase_key(key) -> (comp_type, field) | None`。**只定映射，无运行时读写接口**（[13](../xkx-arch/13-dbase-key-map.md) §六"不实现运行时 query 接口"）。
- [ecs.py](../../engine/src/xkx/runtime/ecs.py) World（SparseSet + `entities_in_room` 已有 + `entities_with` 交集查询）。**无 family/prototype/alias 索引**。
- [schema.py](../../engine/src/xkx/runtime/schema.py) SchemaRegistry（`has_field` + `resolve` + `resolve_name`，拼写检查护栏 ADR-0019）。
- [inspector.py](../../engine/src/xkx/runtime/inspector.py) EntityInspector（只读快照 + LPC_KEY_MAP 映射表 + `lpc_key_mapping(key)` 查询映射条目）。**只读检视工具，非运行时接口**；其 `LPC_KEY_MAP` 与 `dbase_map.DBASE_KEY_MAP` 部分重复（两套映射表，需收敛）。
- [components.py](../../engine/src/xkx/runtime/components.py) 13 组件（Identity/Position/Inventory 等已定义，但**缺运行时方法**：无 `short()`/`present()`/`move()` 语义函数，这些逻辑散落在 commands.py 的 go/get/give 命令里）。
- [spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) 24 函数规格：F_DBASE 8 函数（set/query/delete/add + temp 变体 + set_default_object）+ F_NAME 5 函数（set_name/id/name/short/long）+ F_MOVE 5 函数（move/weight/set_weight/add_encumbrance/remove）+ F_MESSAGE/F_SAVE/F_CLEAN_UP。

**dissent 2 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 2 条）：

> ECS 取代 daemon：query 语义偏离 LPC F_DBASE。LPC dbase 是字符串 key 的 mapping，全仓 68771 调用点；ECS 用结构化组件替代，但 query("cobmat_exp") 拼写错误静默返回 0 的 bug 难发现。

本 ADR 落地裁决：**运行时 query/set 接口对齐 LPC F_DBASE 语义**（简单 key + 路径前缀），映射到 ECS 组件字段（复用 DBASE_KEY_MAP）；**拼写错误不静默**（区分"后置 key"与"未知 key"，后置返回 None，未知 raise）；**索引层为查询便利**（family/prototype/alias 线性扫描，预建索引后置性能优化）。

**dissent 8 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 8 条）：

> 存储收缩丢失语义：新组件必须可序列化 + EffectComp 崩溃恢复。

本 ADR 不新增组件（复用阶段 1 的 13 组件），只加运行时接口；序列化已在 [serialization.py](../../engine/src/xkx/runtime/serialization.py) 覆盖 13 组件，无新增序列化需求。

**CLAUDE.md 不变量**：

- tick=1s + compute<100ms（query 线性扫描 O(n)，1000 实体规模足够；预建索引后置性能优化备选 2，[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七）。
- Command 仅覆盖外部意图（query/set 是 System/Command 共用的运行时工具函数，非 Command）。
- CombatKernel 从武侠提取、用非武侠验证（query 层不含武侠语义，纯 F_DBASE 通用语义）。

## 决策

### 1. query/set 运行时接口（对照 LPC F_DBASE 8 函数）

新建 [runtime/query.py](../../engine/src/xkx/runtime/query.py)，实现 LPC F_DBASE 的 8 个核心函数（[spec/layer_b](_set_spec)/[_query_spec](_query_spec)/[_delete_spec](_delete_spec)/[_add_spec](_add_spec) + temp 变体）：

| LPC 函数 | greenfield 接口 | 语义（对照层 B 规格） |
|---|---|---|
| `set(prop, data)` | `set(world, eid, key, val) -> Any` | 写组件字段，返回 val（LPC 返回 data） |
| `query(prop, raw)` | `query(world, eid, key) -> Any` | 读组件字段，不存在返回 None（LPC 返回 0） |
| `delete(prop)` | `delete(world, eid, key) -> int` | 删组件字段（set 默认值），返回 1/0 |
| `add(prop, data)` | `add(world, eid, key, val) -> Any` | query 旧值 + set 新值（增量） |
| `set_temp(prop, data)` | `set_temp(world, eid, key, val) -> Any` | 写 temp 变体（marks/ 等） |
| `query_temp(prop, raw)` | `query_temp(world, eid, key) -> Any` | 读 temp 变体 |
| `delete_temp(prop)` | `delete_temp(world, eid, key) -> int` | 删 temp 变体 |
| `add_temp(prop, data)` | `add_temp(world, eid, key, val) -> Any` | temp 增量 |

**路径前缀解析**（对齐 LPC `_set`/`_query` 路径访问，[spec/layer_b](_set_spec notes)）：

- `query(world, eid, "skill/axe")` -> `Skills.levels["axe"]`（PATH_PREFIX_MAP["skill"]）
- `query_temp(world, eid, "marks/酥")` -> `"酥" in Marks.flags`（PATH_PREFIX_MAP["marks"]）
- 简单 key：`query(world, eid, "qi")` -> `Vitals.qi`（DBASE_KEY_MAP["qi"]）

**未映射 key 的三类处理**（核心决策，区分 dissent 2 的"拼写错误静默"问题）：

1. **已映射 key**（DBASE_KEY_MAP / PATH_PREFIX_MAP）：正常读写组件字段。
2. **后置 key**（POSTPONED_KEYS）：`query` 返回 None + 可选 warning（`warnings.warn`，对应子系统未实现，不是 bug）；`set` raise `DbaseKeyError`（后置 key 无组件承接，写无意义）。
3. **未知 key**（拼写错误，如 `"cobmat_exp"`）：`query`/`set` raise `DbaseKeyError`（非静默，对齐 ADR-0019 拼写检查精神）。

> 区分"后置"与"未知"是本层核心价值：LPC `query("cobmat_exp")` 静默返回 0，bug 难发现（dissent 2）；greenfield 让拼写错误显式失败，后置 key 显式标注未实现。`DbaseKeyError` 是 `SchemaError` 子类（复用 ADR-0019 错误体系）。

**set/delete 的组件字段写语义**：

- 简单 key（标量字段，如 `Vitals.qi`）：`setattr(comp, field, val)`。
- 路径前缀（dict/set 字段）：`set("skill/axe", 30)` -> `Skills.levels["axe"] = 30`；`set_temp("marks/酥", 1)` -> `Marks.flags.add("酥")`；`delete_temp("marks/酥")` -> `Marks.flags.discard("酥")`。
- `add` 语义：`set(key, query(key) + val)`（对齐 LPC `add` = query 旧值 + set 新值，[spec/layer_b](_add_spec)）。int + int / string + string / dict 更新；类型不兼容 raise `TypeError`。

### 2. 简化范围（不做什么，对齐 04 §六收敛）

对照 LPC F_DBASE 完整语义，本层简化以下项（后置或砍掉）：

| LPC 语义 | 简化决策 | 理由 / 后置时机 |
|---|---|---|
| `query(prop, raw=1)` raw 参数 | 不实现 | greenfield 无 function 类型值（LPC `evaluate()` 特有），raw 恒等价于 raw=1 |
| `default_ob` 回退（master copy 默认值） | 不实现 | greenfield 无 clone/master copy 机制（LPC 对象模型特有），每个实体独立 |
| `set_default_object(ob)` | 不实现 | 同上，无 default_ob 概念 |
| 完整 treemap（`"a/b/c/d"` 任意深度路径） | 不实现 | 只支持 `skill/<id>` / `marks/<flag>` 两类已知前缀（PATH_PREFIX_MAP）；LPC F_TREEMAP 是实现细节，[spec/layer_b](../../engine/src/xkx/spec/layer_b_object_base.py) notes 明确不提取 |
| `evaluate()` 对 function 类型求值 | 不实现 | greenfield 无 LPC function 类型；需动态求值时用 Python callable 在组件中直接处理 |
| `short()` 状态修饰（打坐/鬼气/断线/昏迷） | 后置 2.5 | TitleSystem + condition 状态修饰，2.5 称谓系统时补 |
| `move()` 负重级联（weight/encumbrance） | 后置 2.3 | F_MOVE 装备系统，2.3 Attribute/Skill/Equipment 时补 |
| `receive_message` subclass 路由 | 后置 2.x | F_MESSAGE 频道/户外/天气子类，消息系统时补 |
| `clean_up` 对象回收 | 后置 M3 | greenfield 实体生命周期由 ECS 管理，无 LPC clean_up 心跳回收 |
| `save`/`restore`（F_SAVE 框架） | 已由 T5 覆盖 | [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) StorageSystem 已实现存档，F_SAVE 框架不单独提取 |

> 简化台账与 [ADR-0002](ADR-0002-resolve-attack-extraction.md) / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 模式一致：明确列出"不做什么"及其后置时机，避免实施时模糊。

### 3. 索引层（World 扩展，线性扫描）

对照 [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.1 产出"索引层：`entities_in_room` 已有，扩展 `entities_with_family` / `entities_by_prototype` 等"：

| 查询接口 | 语义 | LPC 对照 |
|---|---|---|
| `entities_in_room(world, room_id)` | 按房间查实体（已有，[ecs.py](../../engine/src/xkx/runtime/ecs.py)） | `all_inventory(room_ob)` |
| `entities_with_family(world, family)` | 按门派查实体（Attributes.family） | shanmen.c 守卫判断 |
| `entities_by_prototype(world, prototype_id)` | 按 NPC def id 查（Identity.prototype_id） | LPC `find_object` + clone 追踪 |
| `find_in_room(world, room_id, keyword)` | 房间内按 name/alias/id 查实体 | `present(str, room_ob)` 语义 |
| `find_item(world, eid, keyword)` | 玩家物品栏按 id/alias 查 | `present(str, me)` 语义 |

**索引策略**（性能决策）：

- **阶段 2.1 线性扫描**（O(n)，1000 实体规模足够）：复用 `entities_with` 交集查询 + Python 过滤。
- **预建索引后置**（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七性能优化备选 2）：启动期建立 `family -> set[eid]` / `prototype -> set[eid]` 反向索引，仅在 tick profiler 实测瓶颈后引入。
- **不预建索引的理由**：T10 压测 tick p99 12.6ms，查询非瓶颈（CombatSystem 占 92%）；预建索引增加 mutation 维护成本（family 变更需同步索引），过早优化违反收敛原则。

### 4. Identity/Position/Inventory 组件规格等价

对照 [spec/layer_b](../../engine/src/xkx/spec/layer_b_object_base.py) F_NAME/F_MOVE 规格，在 query.py 实现运行时语义函数（**不加组件字段，不加方法到 dataclass**，保持组件纯数据）：

**Identity（F_NAME）**：

- `id_match(identity, keyword) -> bool`：keyword 匹配 `Identity.aliases`（含主 id aliases[0]）或 `Identity.name`。对照 LPC `id(str)` 规格（[spec/layer_b](_id_spec)）：apply/id 掩码后置（无 apply 机制），可见性检查后置（2.5 visible 三级）。
- `short(identity) -> str`：返回 `name(id)` 格式（如 `"葛伦布(ge lunbu)"`），对照 LPC `short(raw=1)` 基础格式（[spec/layer_b](_short_spec)）。状态修饰后置 2.5。

**Position（F_MOVE）**：

- `move_to(world, eid, room_id) -> None`：切换 `Position.room_id`。对照 LPC `move(dest)` 的核心效果（[spec/layer_b](_move_spec) postcondition 6 `move_object`）。负重级联 + 自动 look 后置 2.3。
- `environment(world, eid) -> str | None`：返回 `Position.room_id`（LPC `environment()`）。无 Position 组件返回 None。

**Inventory（present 语义）**：

- `present_item(world, eid, keyword) -> str | None`：keyword 匹配 `Inventory.items` 中的物品 id。对照 LPC `present(str, me)`（[spec/layer_b](_move_spec) 跨层引用 `all_inventory`）。物品 alias 匹配后置（物品系统，当前 Inventory.items 是 id 集合，无 ItemDef alias）。
- `all_inventory(world, eid) -> set[str]`：返回 `Inventory.items` 副本（LPC `all_inventory()`）。

> 组件保持纯数据（dataclass 无方法），语义函数放 query.py。这符合 ECS 模式（组件 = 数据，系统/工具 = 行为），也避免 dataclass 方法污染序列化（[serialization.py](../../engine/src/xkx/runtime/serialization.py) 按 `dataclasses.fields` 提取）。

### 5. 后置 key 激活策略（按"实现到时才补"原则）

对照 [13-dbase-key-map.md](../xkx-arch/13-dbase-key-map.md) §五的 55 后置 key，按子系统激活：

| 子系统 | 激活的 key | 激活时机 |
|---|---|---|
| 2.1 Query | 无新增（Identity/Position/Inventory 已映射） | 本任务 |
| 2.2 Vitals/Heal | `eff_jing` / `eff_jingli`（Vitals 扩展字段）+ 死亡轮回 key（`death_count`/`death_times`/`my_killer`） | 2.2 实现 |
| 2.3 Attribute/Skill/Equipment | `equipped` / `weight` / `encumbrance`（F_MOVE 装备） | 2.3 实现 |
| 2.5 TitleSystem | `title` / `nickname` / `shen`（道德值） | 2.5 实现 |
| 2.6 WorldGovernance | `vendetta` / `vendetta_mark` / `pking` / `pktime`（法院系统） | 2.6 实现 |
| 2.7 门派切割 | `race`（human.c race 层） | 2.7 实现 |
| 后置 M3 | `channels` / `chblk_on` / `block_msg` / `language`（频道/消息）+ `link_ob`/`body_ob`（已 T7 部分覆盖） | M3 消息系统 |

**激活协议**：子系统实现时，在 DBASE_KEY_MAP 加条目（从 POSTPONED_KEYS 移除），`validate_dbase_map` 启动期校验映射目标字段存在。本 ADR 不预激活任何后置 key（2.1 范围控制）。

### 6. 映射表收敛（inspector.LPC_KEY_MAP 与 dbase_map.DBASE_KEY_MAP 去重）

**现状问题**：[inspector.py](../../engine/src/xkx/runtime/inspector.py) `LPC_KEY_MAP` 与 [dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) `DBASE_KEY_MAP` 部分重复（两套映射表，维护成本高，易漂移）。

**收敛决策**：

- `DBASE_KEY_MAP` / `PATH_PREFIX_MAP` / `POSTPONED_KEYS` 是**权威映射表**（启动期校验 + 运行时 query/set 依赖）。
- `inspector.LPC_KEY_MAP` 改为**从 DBASE_KEY_MAP 派生**（运行时构建，不重复定义），保留 inspector 特有的 `lpc_scope` / `field_path` / `note` 展示信息（从 DBASE_KEY_MAP + POSTPONED_KEYS 派生）。
- inspector 的 `lpc_key_mapping(key)` 复用 `dbase_map.resolve_dbase_key` + `is_postponed` 判断。

> 收敛后单一信源（DBASE_KEY_MAP），映射变更只改一处。inspector 保留展示层（note/scope），不存重复映射数据。

## 代码结构

### 新建 `engine/src/xkx/runtime/query.py`

```python
# 核心接口（8 个 LPC F_DBASE 函数）
def query(world, eid, key) -> Any: ...
def query_temp(world, eid, key) -> Any: ...
def set(world, eid, key, val) -> Any: ...
def set_temp(world, eid, key, val) -> Any: ...
def add(world, eid, key, val) -> Any: ...
def add_temp(world, eid, key, val) -> Any: ...
def delete(world, eid, key) -> int: ...
def delete_temp(world, eid, key) -> int: ...

# 索引层
def entities_with_family(world, family) -> Iterator[int]: ...
def entities_by_prototype(world, prototype_id) -> Iterator[int]: ...
def find_in_room(world, room_id, keyword) -> int | None: ...
def find_item(world, eid, keyword) -> str | None: ...

# Identity/Position/Inventory 语义函数
def id_match(identity, keyword) -> bool: ...
def short(identity) -> str: ...
def move_to(world, eid, room_id) -> None: ...
def environment(world, eid) -> str | None: ...
def present_item(world, eid, keyword) -> str | None: ...
def all_inventory(world, eid) -> set[str]: ...
```

### 扩展 `engine/src/xkx/runtime/dbase_map.py`

- 新增 `DbaseKeyError(SchemaError)`：未映射/后置 key 写入异常。
- 新增 `is_postponed(key) -> bool`：判断 key 是否在 POSTPONED_KEYS。
- 新增 `classify_key(key) -> KeyClass`：返回 `MAPPED` / `POSTPONED` / `UNKNOWN`（三类区分）。
- `resolve_dbase_key` 保留（向后兼容 inspector 现有调用）。

### 重构 `engine/src/xkx/runtime/inspector.py`

- `LPC_KEY_MAP` 改为从 DBASE_KEY_MAP + POSTPONED_KEYS 派生（运行时构建，删除 `_LPC_ENTRIES` 硬编码列表）。
- `lpc_key_mapping(key)` 复用 `dbase_map.classify_key` + `resolve_dbase_key`。

### 测试 `engine/tests/test_query.py`

- 8 函数行为等价（query/set/add/delete + temp 变体）：简单 key + 路径前缀 + 未映射三类。
- 索引层：entities_with_family / entities_by_prototype / find_in_room / find_item。
- Identity/Position/Inventory 语义：id_match / short / move_to / environment / present_item / all_inventory。
- hypothesis 属性测试：路径前缀解析（`skill/<random_id>` 往返一致）+ 未映射 key 分类（MAPPED/POSTPONED/UNKNOWN 三类覆盖）+ add 增量语义（int/string/dict 类型）。
- 映射表收敛回归：inspector LPC_KEY_MAP 与 DBASE_KEY_MAP 一致性。

## 简化台账（与 LPC F_DBASE 的差异）

| # | LPC 语义 | greenfield 实现 | 后置时机 | 关联 |
|---|---|---|---|---|
| 1 | `raw` 参数（function 求值） | 不实现（无 function 类型） | 砍掉 | [spec/layer_b](_query_spec) |
| 2 | `default_ob` 回退 | 不实现（无 clone/master copy） | 砍掉 | [spec/layer_b](_query_spec) notes |
| 3 | `set_default_object` | 不实现 | 砍掉 | [spec/layer_b](_set_default_object_spec) |
| 4 | 完整 treemap（任意深度路径） | 只 skill//marks/ 两前缀 | 砍掉 | [spec/layer_b](_set_spec) notes |
| 5 | `evaluate()` function 求值 | 不实现 | 砍掉 | [spec/layer_b](_query_spec) |
| 6 | `short()` 状态修饰 | 基础格式 only | 2.5 TitleSystem | [spec/layer_b](_short_spec) |
| 7 | `move()` 负重级联 | room 切换 only | 2.3 Equipment | [spec/layer_b](_move_spec) |
| 8 | `move()` 自动 look | 后置 | 2.3 / 命令层 | [spec/layer_b](_move_spec) side_effect 7 |
| 9 | `receive_message` subclass 路由 | 不实现 | M3 消息系统 | [spec/layer_b](_receive_message_spec) |
| 10 | `clean_up` 对象回收 | 不实现 | M3（ECS 管理生命周期） | [spec/layer_b](_clean_up_spec) |
| 11 | `id()` apply/id 掩码 | 不实现 | 砍掉（无 apply 机制） | [spec/layer_b](_id_spec) notes |
| 12 | `id()` 可见性检查 | 不实现 | 2.5 visible 三级 | [spec/layer_b](_id_spec) invariant |

> 简化台账与 [ADR-0002](ADR-0002-resolve-attack-extraction.md) §简化台账 / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §简化台账模式一致。砍掉项 = greenfield 不实现（LPC 特有机制）；后置项 = 对应子系统实现时补。

## 验收标准（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.1）

- [ ] LPC `query("skill/axe")` -> `Skills.levels["axe"]` 语义等价（路径前缀解析）
- [ ] LPC `query("qi")` -> `Vitals.qi` 语义等价（简单 key）
- [ ] LPC `query_temp("marks/酥")` -> `Marks.flags` 语义等价（temp 变体）
- [ ] 未映射 key 三类处理：已映射正常 / 后置返回 None + warning / 未知 raise DbaseKeyError
- [ ] `set`/`add`/`delete` + temp 变体行为等价（对照层 B 规格 postcondition）
- [ ] 索引层：entities_with_family / entities_by_prototype / find_in_room / find_item
- [ ] Identity/Position/Inventory 语义函数：id_match / short / move_to / environment / present_item / all_inventory
- [ ] 映射表收敛：inspector LPC_KEY_MAP 从 DBASE_KEY_MAP 派生（单一信源）
- [ ] hypothesis 属性测试：路径前缀往返 + 未映射 key 三类分类 + add 增量类型
- [ ] 现有 1035 tests 不回归（commands.py go/get/give 内联逻辑可逐步迁到 query.py，但本任务不强制全迁）
- [ ] ruff 全过（行长 100，中文按字符数计）
- [ ] test_theme_neutrality 硬门禁持续通过（query 层纯 F_DBASE 通用语义，无武侠烙印）

## 关联 dissent

| dissent | 本 ADR 应对 |
|---|---|
| **2（ECS 取代 daemon，query 语义偏离）** | query/set 接口对齐 LPC F_DBASE 8 函数语义；DBASE_KEY_MAP 映射 + 拼写错误不静默（三类区分） |
| **8（存储语义，新组件可序列化）** | 不新增组件（复用 13 组件），无新增序列化需求；后置 key 激活时新组件字段须可序列化 |

## 不做（范围边界）

- **不预建索引**：线性扫描 O(n)，1000 实体规模足够；预建索引后置性能优化备选 2（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七）。
- **不实现 LPC function 类型求值**：`raw` 参数 / `evaluate()` / `default_ob` 全砍（LPC 特有，greenfield 无对应概念）。
- **不实现完整 treemap**：只 `skill/<id>` / `marks/<flag>` 两类已知前缀。
- **不实现 `short()` 状态修饰**：后置 2.5 TitleSystem（打坐/鬼气/断线/昏迷修饰）。
- **不实现 `move()` 负重级联**：后置 2.3 Attribute/Skill/Equipment（F_MOVE weight/encumbrance）。
- **不激活后置 key**：按子系统实现时补，2.1 只覆盖已映射的 Identity/Position/Inventory 语义。
- **不强制迁移 commands.py 内联逻辑**：go/get/give 命令中的 dbase 读写可逐步迁到 query.py，但本任务不强求全迁（避免大范围重构引入回归风险）；新增代码用 query.py 接口。
- **不扫全量 68771 调用点**：聚焦核心键集 + 9 层规格涉及键（[13](../xkx-arch/13-dbase-key-map.md) §不做）。

*最后更新：2026-07-12*
