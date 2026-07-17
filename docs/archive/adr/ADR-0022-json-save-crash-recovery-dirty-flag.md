# ADR-0022：JSON 存档格式 + 崩溃恢复协议 + dirty-flag 策略 + Effect 序列化

- 状态：草案（Wave 2 T5 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 2 T5
- 关联：[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1（内存权威 + JSON 存档）/ [04 §四](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 8（JSON 存储外部测试前必须迁 PG）/ [04 §七](../xkx-arch/04-迁移路径与避坑清单.md) 第 9 条（JSON 存档崩溃安全）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 8（存储收缩丢失语义）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1 承重论断 2/3 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 6 承重论断 1 / [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp / [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) ConditionTickResult / [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T5

## 背景

[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 里程碑 M1-5："内存权威 + JSON 存档 | 原子写 + offload + dirty-flag；崩溃冷重启从 checkpoint 恢复"。[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T5 任务卡：内存权威 + 本地 JSON 定时存档，原子写 + offload + dirty-flag 分摊 + 崩溃冷重启从 checkpoint 恢复 + Effect 可崩溃恢复。验收：原子写通过崩溃测试；存档不阻塞事件循环；冷重启恢复玩家状态。

**LPC save_object 的前车之鉴**（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_user_save` invariant / [spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_save_spec`）：

- LPC `save_object` 是 FluffOS efun，全量覆盖写 dbase 中所有非 static 变量，**无原子写**（非 write-temp+rename）。写入中途崩溃即文件损坏，下次 `restore_object` 读到半截 JSON 或截断文件。
- `user.c save()` 三步交织：`save_autoload()` -> `::save()`（F_SAVE 委托 `save_object`）-> `clean_up_autoload()`。存档路径 `DATA_DIR/user/<首字母>/<id>`（如 `/data/user/a/alice`）。
- `NATURE_D->event_sunrise`（[spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py)）是全局自动保存触发点：每日日出遍历 `users()`，对每个有 `link_ob` 的玩家 `link_ob->save(); body->save()`（link_ob + body 双重保存）。
- greenfield 不得重蹈此覆辙（CLAUDE.md 架构不变量 + [04 §七](../xkx-arch/04-迁移路径与避坑清单.md) 第 9 条）。

**存储收缩是隐性重新设计**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 8 + 专家 6 承重论断 1）：内存+JSON 不是"换存储"而是对 v2 子系统6（PG+Redis 贯穿 EventStore/SnapshotStore/CommandBus 乐观并发/CAS 等）的重新设计。策略模式存储接口若以"save=权威写"抽象，迁 PG 时是架构变更非策略切换；必须以"持久化边界"（persist=崩溃恢复级耐久）为抽象（专家 1 承重论断 2）。

**JSON 存档崩溃安全三要素**（专家 1 承重论断 3，CLAUDE.md 不变量）：

1. write-temp + os.replace 原子写
2. 事件循环外 offload（`run_in_executor`，存档不阻塞 tick）
3. dirty-flag 分摊（只存脏实体，非全量）

**Effect 可崩溃恢复**（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) §2 + 04 §三硬约束）：EffectComp 必须可序列化/可中断/可崩溃恢复；存档需含未完成 Effect 状态（剩余 `duration`/`next_tick`），冷重启后从 checkpoint 恢复。

**现状**：

- 阶段 1 无任何存储代码（T5 产出 StorageBackend）。[runtime/world.py](../../engine/src/xkx/runtime/world.py) `to_snapshot` 是 combat 边界快照（非存档快照），`apply_effects` 是即时 Effect apply 路径。
- [runtime/components.py](../../engine/src/xkx/runtime/components.py) 14 个 dataclass 组件（含 EffectComp），字段全基本类型 + set/dict 容器，无闭包/函数引用，dataclasses 序列化友好。
- [runtime/conditions.py](../../engine/src/xkx/runtime/conditions.py) ConditionSystem 持有 `ConditionHandler`，`on_tick` 是纯函数返回 `ConditionTickResult`，apply 后 mutate EffectComp（`duration`/`next_tick`）。这些 mutation 即 dirty 来源。
- [combat/result.py](../../engine/src/xkx/combat/result.py) 即时 Effect（`CombatRoundResult.effects`）apply 后不持久化（账本已记录），不在本 ADR 序列化范围。

## 决策

### 1. 持久化边界抽象（persist=崩溃恢复级耐久，非 save=权威写）

StorageBackend 策略接口以"持久化边界"为抽象，核心语义是**崩溃恢复级耐久**（crash-recovery durability）：

- **persist(entity_states)**：将内存权威态落盘到崩溃恢复级耐久介质。语义保证：调用返回成功后，进程崩溃不丢失本次落盘数据；调用返回前崩溃，不保证已落盘（下次从上一个 checkpoint 恢复）。
- **restore() -> entity_states**：从耐久介质读回最近一次成功 persist 的状态，重建内存权威态。
- **不承诺**：事务原子性（多实体跨文件无 ACID 事务）/ 并发写 CAS（单进程无并发写）/ 关系完整性（无外键约束）/ append-only 防篡改（JSON 文件可被直接编辑）。这些是 PG 才有的语义，本 ADR §5 逐一标注丢失 + 止损线。

**"非 save=权威写"的关键**：内存是权威态，persist 只是周期性把权威态快照到耐久介质。崩溃后 restore 恢复到最近 checkpoint（丢失 checkpoint 之后到崩溃间的变更，最多一个存档周期，默认 30s）。这与 PG 权威+Redis 缓存模型（PG 是权威，Redis 是读穿透缓存）是两种不同一致性模型。

**策略切换路径**（为迁 PG 留路径，kill criteria 8）：

- StorageBackend 是抽象基类，`JsonFileBackend`（T5）与未来 `PostgresBackend`（kill criteria 8 触发后）是两个实现。
- 接口只暴露 persist/restore，不暴露 JSON 文件路径/save_object 等实现细节。迁 PG 时实现层换 `JsonFileBackend` -> `PostgresBackend`，调用方（StorageSystem）无感。
- `PostgresBackend` 补齐丢失语义（事务原子性 via 事务/CAS via 乐观锁/关系完整性 via 外键），是语义增强非接口变更。本 ADR §5 台账即迁 PG 时的补齐清单。

### 2. 原子写协议（write-temp + os.replace）

`JsonFileBackend.persist` 的原子写三步：

1. **序列化**：在事件循环外（`run_in_executor`，见 §3）把 entity_states 序列化为 JSON 字符串。
2. **write-temp**：写到临时文件 `<target>.tmp.<pid>`（同目录，同 filesystem，保证 `os.replace` 是原子 rename 而非跨设备拷贝）。
3. **fsync + os.replace**：`os.fsync(tmp_fd)` 刷盘后 `os.replace(tmp_path, target_path)` 原子替换。`os.replace` 在 POSIX 下是原子操作（rename(2)），替换瞬间旧文件要么完整存在、要么被新文件完整替换，不存在半截状态。

**崩溃安全性证明**：

- 写 `<target>.tmp` 中途崩溃：tmp 文件损坏，target 文件仍是上一次成功的完整存档。下次 restore 读 target（上一个 checkpoint），不受 tmp 损坏影响。
- `os.replace` 执行瞬间崩溃：POSIX 保证 rename 原子，要么 target 已是新的、要么仍是旧的，不存在中间态。
- `os.replace` 后崩溃：target 已是新存档，下次 restore 读新存档。

**不重蹈 LPC save_object 覆辙**：LPC `save_object` 直接全量覆盖 target 文件（无 tmp + rename），写入中途崩溃即 target 损坏。本协议的 tmp + replace 隔离了"写"与"替换"两个阶段，写阶段崩溃不影响 target。

**目录存在性**：对齐 LPC `assure_file`（[spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_save_spec` side_effect order=1），persist 前 `os.makedirs(dir, exist_ok=True)` 确保目录存在。

### 3. 事件循环外 offload（存档不阻塞 tick）

persist 在 `asyncio.to_thread`（或 `loop.run_in_executor`）中执行，不阻塞事件循环：

- StorageSystem 每存档周期（默认 30s，对齐 LPC NATURE_D event_sunrise 每日自动保存的周期语义但缩短到适合测试的间隔）触发一次 persist。
- persist 是 async 方法，内部 `await asyncio.to_thread(self._backend.persist_blocking, states)`，`persist_blocking` 是同步阻塞的序列化+文件 IO。
- tick 驱动的 System（CombatSystem/ConditionSystem/HealSystem）在事件循环中只做内存 mutation，不碰文件 IO；StorageSystem 的 persist 在独立线程，与 tick 并行。
- **不阻塞验证**：tick profiler（[ADR-0013](ADR-0013-engine-toolchain-prd.md) tick-profiler）测量 tick compute<100ms 时，persist 期间 tick 延迟不超阈值。T10 验收"存档不阻塞事件循环"即此验证。

**并发安全**：persist 在独立线程读内存态，tick 在事件循环写内存态。`run_in_executor` 传入的 states 是 persist 触发瞬间的深拷贝快照（在事件循环中同步拷贝，避免线程读到半 mutation 状态），persist 线程只读快照不碰现场。深拷贝在事件循环中执行，但 1000 实体的组件快照拷贝在 μs-ms 级，不破 tick 预算（T10 实测验证）。

### 4. dirty-flag 分摊（只存脏实体，非全量）

StorageSystem 维护 per-entity dirty-flag：

- **标记 dirty**：组件 mutation 路径（`world.get` 返回的可变组件被 System 修改）后标记 entity dirty。具体实现：System.update 末尾调 `storage.mark_dirty(eid)`（显式标记，不依赖 setattr 拦截以避免热路径开销）。EffectComp 的 `duration`/`next_tick` mutation（ConditionSystem apply）同样标记。
- **persist 时只存脏实体**：persist 收集所有 dirty entity 的组件快照，序列化写盘。非 dirty entity 跳过。
- **全量 checkpoint 周期**：每隔 N 次增量 persist 做一次全量 persist（写完整存档，重置所有 dirty-flag），避免增量存档文件无限增长。N 默认 10（即每 10 个存档周期，约 5 分钟，做一次全量）。

**存档文件格式**（收敛，不穷尽字段）：

- 每个实体一个 JSON 文件（路径 `save/<entity_type>/<id>.json`），对齐 LPC `DATA_DIR/user/<首字母>/<id>` 的 per-entity 文件模型。entity_type 区分 player/npc/room 等。
- 文件内容：`{"version": 1, "entity_id": int, "components": {<comp_type_name>: {<field>: <value>}}, "effects": [...]}`。`components` 是该实体所有组件的序列化（EffectComp 独立到 `effects` 数组，见 §6）。
- 全量 checkpoint 直接覆写该文件（原子写）；增量 persist 覆写该实体文件（per-entity 文件模型下增量=只写 dirty entity 文件，非 dirty entity 文件不动）。

**LPC 全量覆盖对比**：LPC `save_object` 每次全量写整个对象的 dbase（所有非 static 变量）。本方案的 dirty-flag 分摊在 per-entity 文件粒度生效（只重写 dirty entity 的文件），非 dirty entity 文件不碰。文件内仍是该实体的全量组件（不做字段级增量，字段级增量复杂度过高，违反收敛优先）。

### 5. 丢失语义台账（dissent 8 逐一标注 + 止损线）

JSON 存储相对 PG 丢失的语义，逐一标注 + 止损线（外部玩家测试前迁 PG，kill criteria 8）：

| # | 丢失语义 | JSON 现状 | 止损线 | 迁 PG 补齐方式 |
|---|---|---|---|---|
| 1 | **事务原子性** | 多实体跨文件 persist 无 ACID 事务，崩溃可能部分实体已写部分未写 | 阶段 1 无外部玩家，崩溃丢失最多一个存档周期（30s）可接受 | `PostgresBackend` 用单事务包裹多实体 persist |
| 2 | **崩溃恢复** | 只能恢复到最近 checkpoint，checkpoint 后到崩溃间的变更丢失 | 同上，30s 丢失对外部玩家不可接受（kill criteria 8 触发） | PG WAL + 更频繁 checkpoint |
| 3 | **并发写 CAS** | 单进程无并发写，无需 CAS | 单进程阶段 1 不触发 | 多进程/分布式阶段 PG 乐观锁 |
| 4 | **关系完整性** | 无外键约束，entity 引用（如 EffectComp.target_id）可能指向不存在实体 | restore 时校验引用，悬空引用记 warning 并跳过 | PG 外键约束 |
| 5 | **append-only 防篡改** | JSON 文件可被直接编辑，无 tamper-evidence | 阶段 1 单机开发期信任本地文件系统 | PG 权限 + audit log；或文件签名（后置） |

**止损线**：kill criteria 8（[04 §四](../xkx-arch/04-迁移路径与避坑清单.md) 第 8 条）--任何外部玩家测试开始前必须迁 PG。崩溃丢 30s 对外部玩家不可接受。阶段 1 无外部玩家测试，不触发；迁 PG 时本台账即补齐清单，StorageBackend 策略切换（见 §1）。

**dissent 8 落实**：本台账即 dissent 8 要求的"逐一标注丢失语义 + 止损线"。专家 6 承重论断 1 指出存储收缩是隐性重新设计，本台账显式记录设计取舍。

### 6. Effect 序列化与崩溃恢复

EffectComp（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) §2 + [runtime/components.py](../../engine/src/xkx/runtime/components.py)）作为 ECS 组件随实体序列化，存档含未完成 Effect 状态：

**序列化**：

- EffectComp 字段全基本类型（`effect_id: str`/`kind: str`/`target_id: int`/`source_id: int`/`amount: int`/`detail: str`/`duration: int`/`tick_interval: int`/`next_tick: int`/`flags: int`），dataclasses 直接序列化为 JSON object。
- 持续 Effect 作为独立 effect 实体（`EffectComp` attach 到 effect 实体，`target_id` 指向被作用实体，见 [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) §2 + [conditions.py](../../engine/src/xkx/runtime/conditions.py) 模块 docstring）。序列化时按 effect 实体存档（含 EffectComp + 其他组件），`target_id`/`source_id` 是 entity_id 引用。
- 存档文件 `effects` 数组存该实体承载的所有持续 Effect（若 EffectComp attach 到玩家实体本身则进 `components.EffectComp`；若作为独立 effect 实体则进独立文件。T5 实现时按 ADR-0017 的"独立 effect 实体"模型定）。

**崩溃恢复**：

- restore 读回 EffectComp 后，`duration`/`next_tick`/`tick_interval` 完整恢复，ConditionSystem 下一 tick 按 `next_tick <= current_tick` 判断是否触发（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) §3 非均匀 tick）。
- **next_tick 对齐**：冷重启后 `next_tick` 是存档时的绝对 tick 编号。重启时 current_tick 从 checkpoint 的 tick 编号继续递增（存档含 `last_tick` 字段）。若 `next_tick < current_tick`（崩溃期间该 Effect 本应触发但未触发），**不补执行**--补执行会破坏非均匀 tick 语义且可能瞬间触发大量 DoT。改为将 `next_tick` 对齐到 `current_tick + tick_interval`（顺延一个周期），等价于"崩溃期间该 Effect 暂停"。这与 [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) §2 "可崩溃恢复"的"跳过崩溃期间未执行的 tick，非补执行"一致。
- **duration 不衰减**：崩溃期间 duration 不衰减（因 Effect 未触发），restore 后 duration 保持存档时值。等价于"崩溃期间 Effect 时间冻结"。

**与 ConditionTickResult 的边界**：

- `ConditionTickResult`（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) §2）是 `on_tick` 的纯函数返回值（即时副作用 + 衰减 delta），apply 后即丢弃，**不持久化**。持久化的是 apply 后的 EffectComp 状态（`duration`/`next_tick` 已更新）。
- 即时 Effect（combat `CombatRoundResult.effects`，[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) §3）apply 后不持久化（账本已记录），不在本 ADR 序列化范围。

### 7. 冷重启恢复协议

崩溃冷重启的恢复流程：

1. **扫描存档目录**：读 `save/<entity_type>/` 下所有 JSON 文件，按 `entity_id` 去重（全量 checkpoint 文件优先于增量）。
2. **反序列化**：每个文件 `json.load` -> 组件 dataclass 重建 -> `world.add(eid, comp)`。EffectComp 同理重建为持续 Effect 实体。
3. **引用校验**：检查 EffectComp.target_id/source_id 指向的实体是否存在（台账 #4）。悬空引用记 warning 并跳过该 Effect（不 crash，对齐 LPC restore_object 容忍半损坏文件的鲁棒性）。
4. **tick 对齐**：读存档 `last_tick` 字段，current_tick 从 `last_tick + 1` 继续递增。EffectComp 的 `next_tick` 按 §6 对齐。
5. **恢复完成**：内存权威态重建，事件循环启动，System 开始 tick。

**LPC restore_object 对比**：LPC `restore_object`（[spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_restore_spec`）恢复 dbase 非 static 变量，是 per-object 的同步恢复。本协议是冷启动时全量扫描恢复所有实体，对齐 LPC `LOGIN_D` 登录时 `restore` 玩家 + 全局世界启动时恢复所有 NPC/房间的语义。

## 不做（范围边界）

- **不做字段级增量存档**：dirty-flag 粒度到 entity（per-entity 文件），文件内仍是该实体全量组件。字段级增量复杂度过高，违反收敛优先（[04 §一](../xkx-arch/04-迁移路径与避坑清单.md) 第 7 条）。
- **不做 append-only 事件溯源**：内存权威 + JSON 存档是 snapshot 模型非 event-sourcing（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) "全量事件溯源(CQRS+ES)作为默认持久化"已砍）。高价值事件走 audit_event（独立于存档）。
- **不做并发写 CAS**：单进程无并发写（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 砍分布式）。多进程阶段由 PG 补齐（kill criteria 8 后）。
- **不做存档加密/签名**：阶段 1 单机开发期信任本地文件系统（台账 #5）。文件签名后置。
- **不做运行时热存档迁移**：存档 schema 版本号（`version: 1`）预留，但 schema migration 后置（阶段 1 无历史存档需迁移）。restore 时 version 不匹配则 warning 并尝试兼容读，不 crash。
- **不做 PG 实现**：T5 只实现 `JsonFileBackend`。`PostgresBackend` 是 kill criteria 8 触发后的后置任务，本 ADR 只定义接口为策略切换留路径。
- **不做 per-component 文件**：per-entity 文件粒度（一个实体一个 JSON 文件），不拆到 per-component。对齐 LPC per-object save_object 文件模型。
- **不修改 LPC 源**（只读规格）。
- **不持久化即时 Effect**：combat `CombatRoundResult.effects` apply 后丢弃（账本已记录），只有持续 EffectComp 持久化（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) §3 边界）。
- **不持久化 ConditionTickResult**：on_tick 返回值是即时副作用账本，apply 后丢弃，不持久化（§6 边界）。

## 产出位置

- `engine/src/xkx/runtime/storage.py`：`StorageBackend` 抽象基类（persist/restore 接口）+ `JsonFileBackend`（原子写 + offload + dirty-flag）+ `StorageSystem`（tick 驱动周期 persist + mark_dirty）+ 存档 schema dataclass。
- `engine/src/xkx/runtime/world.py`：`build_world` 接入 `StorageSystem`（作为第 N 个 System，与 CombatSystem/ConditionSystem 并列）。
- `engine/src/xkx/runtime/serialization.py`：组件 dataclass <-> JSON 序列化/反序列化（dataclasses.fields 提取，衔接 [ADR-0019](ADR-0019-schema-registry-and-dsl-validator-boundary.md) SchemaRegistry 的字段名集）。
- `engine/tests/test_storage.py`：原子写崩溃测试（模拟写入中断，验证 target 不损坏）+ offload 不阻塞事件循环测试 + dirty-flag 只存脏实体测试 + 冷重启恢复测试 + Effect 崩溃恢复测试（duration/next_tick 恢复 + 悬空引用跳过）+ hypothesis 属性测试（序列化往返一致性）。

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 8（存储收缩丢失语义）：§5 丢失语义台账逐一标注 + 止损线
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1 承重论断 2（持久化边界抽象，非 save=权威写）：§1 StorageBackend 以 persist=崩溃恢复级耐久为抽象
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1 承重论断 3（write-temp+os.rename 原子写 + offload + dirty-flag）：§2/§3/§4 三要素
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 6 承重论断 1（存储收缩是隐性重新设计）：§5 台账显式记录设计取舍
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1 M1-5（内存权威 + JSON 存档）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §四 kill criteria 8（JSON 存储外部测试前必须迁 PG，硬止损线）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §七第 9 条（JSON 存档崩溃安全：write-temp+os.replace + offload + dirty-flag）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §六（内存数据+本地 JSON 定时存档，策略模式，外部玩家测试前必须迁 PG）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp（持续 Effect 组件，§6 序列化 + 崩溃恢复衔接）
- [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) ConditionTickResult（on_tick 返回值，apply 后不持久化，§6 边界）
- [ADR-0019](ADR-0019-schema-registry-and-dsl-validator-boundary.md) SchemaRegistry（组件字段名集，序列化衔接）
- [ADR-0013](ADR-0013-engine-toolchain-prd.md) tick profiler（§3 存档不阻塞事件循环验证工具）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T5（本任务）/ T10（1000+100 集成测试，存档不阻塞验证）
- LPC 源：`feature/save.c`（F_SAVE save/restore 框架）/ `clone/user/user.c` save()（三步交织）/ `adm/daemons/natured.c` event_sunrise（全局自动保存触发点）
- 规格源：[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_user_save`（JSON 存档崩溃安全 invariant）/ [spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_save_spec`/`_restore_spec`（F_SAVE 委托 save_object/restore_object）/ [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) event_sunrise（全局自动保存）
