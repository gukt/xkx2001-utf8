# ADR-0057：per-object save DaemonStore + death 不引入同步 persist

- 状态：已采纳
- 日期：2026-07-16
- 阶段：AI 分批迁移 第二批 子任务 A（per-object save）
- 关联：[ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) §2 原子写 + §3 offload + §4 dirty-flag 适用边界 / [ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 决策 4 第一批 + 附录第二批调研（per-object save 卡 id=2/9）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1 承重论断 2/3（存档崩溃安全）/ [04](../xkx-arch/04-迁移路径与避坑清单.md) §四 kill criteria 8（迁 PG）

## 背景

[ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) 建立的存档模型是 **ECS 实体级**：`StorageSystem` 每 `persist_interval` tick（默认 30s）周期快照，per-entity dirty-flag 分摊只存脏实体。它解决的是"玩家/NPC/房间等 ECS 实体的崩溃恢复"，存档路径 `<root>/entity/<eid>.json` 按 eid 寻址。

但 LPC 还有一类**单例数据对象**走 F_SAVE 主动 save/restore，存档路径按对象自定义（非 eid）。这些对象不是 ECS 实体（无组件），而是全局单例数据载体：

- **bboard**（`inherit/misc/bboard.c`）：`query_save_file()` 用 `board_id` 作路径，`do_post`/`do_discard` 后调 `save()`（L117/L250），`setup()` 调 `restore()`（L21）。dbase 承载 `board_id`/`notes`/`wizard_only`/`poster_family`。
- **job_data**（`/clone/obj/job/job_data`）：门派任务/贡献度统计，`restore()` 从二进制 .sav 恢复。
- **job_server / mapdb** 等：同类 F_SAVE 单例。

[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 附录第二批调研指出：`StorageSystem` 无"单例数据对象按自定义路径主动 save/restore"语义，卡 id=2（job_data）与 id=9（bboard）样本。每样本各自 monkeypatch 绕过会重复且不一致，需在 `src/xkx` 落地基础实现"修路"。

同时第一批把 `runtime.death._save` 从断裂的 `persist_now(eid)`（真实签名 `persist_now(world)` 且 async）改为 `mark_dirty(eid)`（走 ADR-0022 §1 内存权威 + 周期 persist）。这引出一个待裁决问题：**death 是否需要 per-eid 同步 persist**（LPC `damage.c` `die` 中调 `save()` 是主动同步存档，防死亡状态回档）？

## 决策

### 1. DaemonStore：单例数据对象 per-object save（独立于 StorageSystem）

新增 `runtime/daemon_store.py` 的 `DaemonStore`，承接 LPC F_SAVE 单例语义：

- **独立于 `StorageSystem`**：daemon 不是 ECS 实体，不进 `StorageSystem` 的 dirty-flag / 周期 persist 调度。`DaemonStore` 与 `StorageSystem` 只共用 `write_json_atomic` 原子写 helper（决策 2），不共用 dirty-flag/周期机制。
- **API**：`register(name, daemon)` / `get(name)` / `save(name)`（sync 阻塞）/ `save_async(name)`（事件循环内 await offload）/ `restore_all()`。存档路径 `<root>/daemon/<name>.json`。
- **`DaemonSerializable` Protocol**：`to_dict() -> dict` + `from_dict(cls, d)`。daemon 数据直接 `json.dump` dict，**不套 `serialize_entity`**（非 ECS 组件）。
- **save 语义**：业务变更点主动 save。提供两版：`save(name)` sync 阻塞（非事件循环上下文直接写，daemon save 频率低、单次 fsync ms 级可接受）+ `save_async(name)` 供事件循环内调用方 `await` + `asyncio.to_thread` offload（ADR-0022 §3，不阻塞 tick<100ms 预算）。**约定**：事件循环内必须用 `save_async`，`save` 不在事件循环线程直接做文件 IO（sync 方法无法在已运行 loop 内 `await to_thread`，故分两版由调用方选择，而非 save 内部自动判断）。

覆盖 job_data / bboard / job_server / mapdb 全部 F_SAVE 单例（ADR-0056 附录推荐方案 B）。

### 2. 提取 `write_json_atomic` helper（复用 ADR-0022 §2 三步）

把 `storage.py` `JsonFileBackend._write_entity_atomic` 提为模块级函数 `write_json_atomic(path, obj)`：write-temp（同目录 tmp）+ fsync + os.replace + `os.makedirs(exist_ok)`。原 `_write_entity_atomic` 改调 `write_json_atomic(self._entity_path(eid), state)`。`DaemonStore` 复用同一 helper。

**不变量**：原子写三步不可缺；tmp 与 target 必须同目录同 filesystem（保证 `os.replace` 是原子 rename 非跨设备拷贝）。daemon 路径必须在同一 `<root>/daemon/` 下。

### 3. daemon save **不走** dirty-flag（ADR-0057 核心偏离）

ADR-0022 §4 dirty-flag 是**周期 persist 的优化**：只在周期 persist 时收集 dirty 实体写盘，分摊全量 checkpoint 开销。dirty-flag 的前提是"周期 persist 驱动"。

daemon 不参与周期 persist（它是单例，不是 tick 驱动的 ECS 实体集合），其 save 是**业务变更点主动触发**（bboard 发帖、job_data 统计更新）。主动 save 本就是"现在就写"，没有"延迟到周期"的语义，套 dirty-flag 是无意义层。因此 daemon save 复用 ADR-0022 §2 原子写 + §3 offload，**不走 §4 dirty-flag**。

这不违反 ADR-0022 不变量：ADR-0022 §4 dirty-flag 适用边界是"周期 persist 的分摊优化"，本决策明确 daemon 不在该边界内。daemon 的崩溃安全由原子写三步保证（写 tmp 中途崩溃只损坏 tmp，target 仍是上一次完整存档），与 entity persist 同等。

### 4. daemon vs entity persist 边界

| 维度 | DaemonStore（daemon） | StorageSystem（entity） |
|---|---|---|
| 数据对象 | 单例数据对象（bboard/job_data/job_server/mapdb） | ECS 实体（玩家/NPC/房间，按 eid） |
| save 触发 | 业务变更点主动同步 save | tick 周期 persist（默认 30s） |
| 寻址 | 自定义 name（`<root>/daemon/<name>.json`） | eid（`<root>/entity/<eid>.json`） |
| dirty-flag | 不走（主动 save 无延迟语义） | 走（ADR-0022 §4 周期 persist 分摊） |
| 序列化 | `to_dict`/`from_dict` 直接 JSON | `serialize_entity`/`deserialize_entity`（组件集合） |
| offload | 事件循环内 `to_thread`，否则阻塞 | `_async_persist` + `to_thread` |

**death 属 entity 非 daemon**：death 存的是玩家 ECS 组件（Vitals/Marks/Progression 等），不是单例数据对象。death 的存档走 `StorageSystem.mark_dirty(eid)` + 周期 persist，不进 `DaemonStore`。

### 5. death 存档定位：走 mark_dirty，**不引入 per-eid 同步 persist**（方案 A）

`runtime.death._save` 走 `storage.mark_dirty(eid)`（第一批已修复断裂，确认正确，不改动逻辑）。death **不引入** per-eid 同步 persist（即不为 death 开"立即同步写该 eid 存档"特例）。

**滑坡论证**：LPC 中关键事件主动 `save()` 不止 death--`quit`（退出存档）、交易（给/取物品后存档）、bboard（发帖后存档）、job_server（任务更新后存档）等都有主动 save。若为 death 开"立即同步 persist"特例，这些点同样有资格要求立即存档（死亡回档不可接受 vs 交易回档不可接受 vs 退出回档不可接受，无原则区分）。开了特例就回到 LPC"到处主动 save"模型，ADR-0022 §1 "内存权威 + 周期 persist + dirty-flag"模型被侵蚀：每条 mutation 路径都要求同步 persist，dirty-flag 失去意义，存档退化为 LPC `save_object` 全量覆盖高频写。

**death 回档风险**：death 后到下一次周期 persist（最多 `persist_interval`，默认 30s）内崩溃，可能丢死亡状态（恢复到死亡前）。此风险记为 **ADR-0022 §1 接受权衡**：ADR-0022 §1 明确"persist 只是周期性快照，崩溃后恢复到最近 checkpoint，丢失 checkpoint 后到崩溃间的变更（最多一个存档周期）"。death 在此权衡内。外部玩家测试前迁 PG 补齐更频繁 checkpoint + WAL（kill criteria 8）。

## 关联 dissent

- **[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1 承重论断 2**（持久化边界抽象，非 save=权威写）：DaemonStore 复用同一"持久化边界"抽象（save=崩溃恢复级耐久，非权威写），daemon 主动 save 是把内存态快照到耐久介质，与 entity persist 同语义。
- **[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1 承重论断 3**（write-temp+os.replace 原子写 + offload + dirty-flag）：DaemonStore 复用原子写三步 + offload（§2/§3），明确不走 dirty-flag（§4 适用边界，决策 3）。
- **[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 附录第二批调研**（per-object save 推荐 DaemonStore 方案 B）：本 ADR 落地该推荐。

## 与 [04](../xkx-arch/04-迁移路径与避坑清单.md) 验收关系

- **§三 阶段 1 M1-5**（内存权威 + JSON 存档，原子写 + offload + dirty-flag）：DaemonStore 复用同一原子写 + offload，补齐 daemon 类单例对象的 per-object save（ADR-0022 未覆盖的 LPC F_SAVE 单例语义）。
- **§四 kill criteria 8**（JSON 存储外部测试前必须迁 PG）：daemon 存档同 entity 存档，迁 PG 时 `DaemonStore` 换 `PostgresDaemonBackend`（策略切换，同 `StorageBackend` 路径）。death 回档风险在此 kill criteria 补齐。

## 不做（范围边界）

- **不做 death per-eid 同步 persist**（方案 B，滑坡，决策 5）。
- **不做 job_data 完整数据建模**：job_data 二进制 .sav 无法从 LPC 源提取。保留 pilot id=2 的 `JobDataLike` Protocol 契约（`restore`/`query_family_jobdata`/`choose_of_player`）。`DaemonStore` 只保证 job_data 这类对象可 register/save（空壳或 Protocol 占位），完整数据建模留后续子系统批。不试图反推二进制 .sav 结构。
- **不做 per-object 存档迁 PG**（kill criteria 8 后置）。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- `engine/src/xkx/runtime/storage.py`：提取 `write_json_atomic(path, obj)` 模块级函数，`_write_entity_atomic` 改调它。
- `engine/src/xkx/runtime/daemon_store.py`：`DaemonStore` + `DaemonSerializable` Protocol。
- `engine/src/xkx/runtime/daemons/bboard.py`：`BboardData` + `Note`（首批 daemon，覆盖 id=9 主路径 save/restore）。
- `engine/src/xkx/runtime/world.py`：`build_world` 增 `daemon_store` 参数注入（类比 `storage_backend`）。
- `engine/src/xkx/cli.py`：`load_game` 构造 `DaemonStore`（与 `JsonFileBackend` 同 root；demo 当前不接 storage_backend，daemon_store 同步不接，保持 demo 行为不破坏）。
- `engine/tests/test_daemon_store.py`：原子写 + register/get/save/restore_all + to_dict/from_dict 往返 + 事件循环内/外 save 不阻塞崩。
- `engine/tests/test_death_save.py`：die/death_penalty 后 `mark_dirty(eid)` 被调（真单测，覆盖第一批修复）。
- `engine/tests/test_damage_c_die.py`：修假绿（`_save` 对齐 `mark_dirty`，`FakeStorage` 改 `mark_dirty`）。

## 后续

- bboard 子系统完整迁移（do_post/do_discard/do_list 等）在后续批，本批只落 `BboardData` 数据建模 + DaemonStore 机制。
- job_data 完整数据建模随门派任务子系统批。
- 迁 PG 时 `DaemonStore` 与 `StorageSystem` 同步策略切换（kill criteria 8）。
