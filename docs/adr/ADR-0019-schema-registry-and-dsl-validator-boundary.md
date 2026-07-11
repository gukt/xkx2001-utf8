# ADR-0019：SchemaRegistry 设计（与 DSL SchemaValidator 边界）

- 状态：草案（Wave 1 T2 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 1 T2
- 关联：[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1（SchemaRegistry 类型化组件）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变）/ [ADR-0008](ADR-0008-schema-validator-four-checks.md) DSL SchemaValidator / [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) 组件 / [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T2 / T3

## 背景

[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 里程碑 M1-2："SchemaRegistry 类型化组件 | query 拼写错误启动期失败"。[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T2 任务卡：组件类型注册 + 字段 schema + 拼写检查 + 启动期校验；验收 "`world.get(eid, Identity)` 拼写 `Identidy` 启动期失败；未知字段警告（衔接 [ADR-0008](ADR-0008-schema-validator-four-checks.md) SchemaValidator）"。

**LPC dbase 的静默失败问题**（[spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_query_spec` postcondition）：

- LPC `query(prop)` 不存在时返回 0（undefined），**不报错**。`query("cobmat_exp")`（拼写错误）静默返回 0，bug 难发现。
- greenfield 用结构化组件（`Progression.combat_exp`）避免了属性拼写（Python `AttributeError`），但 `world.get(eid, comp_type)` 传入未注册/拼错的类型时返回 `None`（运行时静默，与 LPC 静默返回 0 同病）。
- T3 将引入 `DBASE_KEY_MAP`（LPC dbase key -> 组件字段，[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T3），字符串 key 映射到组件字段时，目标字段拼写错误需 schema 校验。

**现状**：

- [runtime/ecs.py](../../engine/src/xkx/runtime/ecs.py) `World.get`/`add`/`has`/`remove` 不校验 `comp_type` 是否合法，任意 type 对象均可传入，未注册类型静默返回 `None`。
- [dsl/validator.py](../../engine/src/xkx/dsl/validator.py) `SceneValidator`（[ADR-0008](ADR-0008-schema-validator-four-checks.md)）是 DSL IR 层四道校验（SchemaValidator/CapabilityAuditor/ResourceBudgetChecker/DependencyResolver），面向 Agent 产出 + UGC，校验 RoomDef/NpcDef/QuestDef/EventRule 的 pydantic 结构。
- [runtime/components.py](../../engine/src/xkx/runtime/components.py) 13 个 dataclass 组件，字段集由 `dataclasses.fields` 可提取。

## 决策

### 1. SchemaRegistry 职责：类型注册 + 字段名存在性校验（拼写检查）

`SchemaRegistry`（[runtime/schema.py](../../engine/src/xkx/runtime/schema.py)）是 runtime 组件层的类型注册表：

- **组件类型注册**：所有组件类型（Identity/Position/Attributes/Vitals/Progression/Skills/CombatState/NpcBehavior/Inventory/Marks/QuestLog/EffectComp/RoomComp）启动时注册到 SchemaRegistry。
- **字段 schema 自动提取**：从 dataclass 的 `dataclasses.fields` 提取合法字段名集，无需手写 schema。
- **拼写检查**：
  - `resolve(comp_type)`：校验 comp_type 已注册，未注册 raise `SchemaError`（非静默 None）。
  - `has_field(comp_type, field_name)` / `field_names(comp_type)`：字段名存在性查询，供 T3 `DBASE_KEY_MAP` 校验映射目标字段合法。

### 2. World 可选注入 SchemaRegistry（向后兼容 + 生产路径强制）

- `World.__init__(schema: SchemaRegistry | None = None)`：可选注入。`schema=None` 时不校验（向后兼容 [test_ecs.py](../../engine/tests/test_ecs.py) 的 `World()` + 临时 `_A`/`_B`/`_C` 组件）。
- `World.get`/`add`/`has`/`remove`/`entities_with`：有 schema 时调 `resolve(comp_type)` 校验，未注册类型 raise `SchemaError`。
- `build_world`（[runtime/world.py](../../engine/src/xkx/runtime/world.py)）用 `World(SchemaRegistry.with_builtins())` 创建带校验的生产 World。
- `SchemaRegistry.with_builtins()` 类方法：注册全部 13 个内置组件。

**"启动期失败"语义**：引擎启动时（`build_world` 首次调用）`SchemaRegistry.with_builtins()` 注册全部内置组件；此后生产路径任何 `world.get(eid, comp_type)` 传入未注册类型（拼写错误或误用），在**首次访问即 raise SchemaError**，而非静默 None 传播 bug。与 LPC `query("cobmat_exp")` 静默返回 0 对立。

> 阶段 1 过渡安排：`World()` 无 schema 不校验，兼容现有测试与开发期临时组件。T4 命令管线落地后评估是否将 `with_builtins` 设为默认（届时测试侧用显式注册的临时组件或 `World(schema=None)` 开关）。

### 3. 与 DSL SchemaValidator 的边界（dissent 3 护栏）

| 维度 | DSL SchemaValidator（[ADR-0008](ADR-0008-schema-validator-four-checks.md)） | SchemaRegistry（本 ADR） |
|---|---|---|
| 层次 | DSL IR 层（YAML -> JSON IR） | runtime 组件层（ECS） |
| 时机 | 创作期 / 场景加载期 | 启动期 / 运行期 |
| 面向 | Agent 产出 + UGC 场景文件 | 引擎代码（System / Command / world） |
| 校验对象 | RoomDef/NpcDef/QuestDef/EventRule pydantic 结构 | 组件类型注册 + 字段名存在性 |
| 校验内容 | 结构 + 未知字段 + 能力声明 + 资源非负 + 引用完整性 | 类型注册 + 字段名拼写 |
| 失败行为 | warning / 测试门禁（阶段 -1 不阻塞编译） | `SchemaError`（启动期/调用期硬失败） |

**边界红线**（dissent 3 护栏）：

- SchemaRegistry **只做类型注册 + 字段名存在性**（拼写检查），**不做语义校验**（非负 / 范围 / 引用完整性 / 字段值枚举）。
- 语义校验留给：DSL SchemaValidator（创作期，[ADR-0008](ADR-0008-schema-validator-four-checks.md)）+ 各 System 运行期不变量（如 [spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) 三层资源不变量 `0<=qi<=eff_qi<=max_qi`）。
- 若 SchemaRegistry 开始校验"combat_exp 非负""kind 必须是 6 种之一"等语义规则，即蠕变成事实上的规则引擎（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3）。判定标准：SchemaRegistry 的校验是"名字存在性"（声明式、无业务逻辑），不是"值合法性"（语义、跨字段关系）。

### 4. T3 衔接：DBASE_KEY_MAP 字段校验

T3（[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T3）产出 `DBASE_KEY_MAP`（LPC dbase key -> 组件字段）。构建时调 `SchemaRegistry.has_field(comp_type, field_name)` 校验映射目标字段存在：

- `DBASE_KEY_MAP["combat_exp"] = (Progression, "combat_exp")` -> `has_field(Progression, "combat_exp")` 必须为 True。
- 若映射目标字段不存在（如 `(Progression, "cobmat_exp")`），启动期 `SchemaError`，而非运行时 `AttributeError`。

这是 T2 与 T3 的衔接点：SchemaRegistry 提供 `has_field` / `field_names` API，T3 的映射表构建时校验。衔接 [ADR-0008](ADR-0008-schema-validator-four-checks.md) 的"未知字段警告"：DSL IR 侧未知字段由 SchemaValidator 捕获，runtime 侧字段映射由 SchemaRegistry 校验，两端共同防止拼写错误静默传播。

## 不做（范围边界）

- **不做语义校验**：非负 / 范围 / 引用完整性 / 字段值枚举（留给 DSL SchemaValidator + System 不变量，dissent 3 护栏）。
- **不做字段值枚举校验**：`EffectComp.kind` 是自由字符串（damage/wound/exp/potential/jingli/skill_improve + condition 扩展），不强制枚举。
- **不做运行时强制所有 World 校验**：`World(schema=None)` 合法存在（兼容测试），生产路径 `build_world` 强制。
- **不做 schema 热重载**：启动时静态注册，运行期不变。
- **不做跨组件关系校验**：外键式（如 EffectComp.target_id 指向某实体）不校验，留给 System 运行期检查。
- **不做 pydantic 组件迁移**：现有 12 组件保持 dataclass（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) 已定 dataclass 风格），schema 从 `dataclasses.fields` 提取，不引入 pydantic 运行时开销。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/schema.py](../../engine/src/xkx/runtime/schema.py)：`SchemaRegistry` + `SchemaError` + `with_builtins()` + `BUILTIN_COMPONENTS`
- [runtime/ecs.py](../../engine/src/xkx/runtime/ecs.py)：`World.__init__` 加 `schema` 参数 + `get`/`add`/`has`/`remove`/`entities_with` 校验
- [runtime/world.py](../../engine/src/xkx/runtime/world.py)：`build_world` 用 `World(SchemaRegistry.with_builtins())`
- [tests/test_schema.py](../../engine/tests/test_schema.py)：注册 / 解析 / 字段查询 / 未注册类型失败 / 内置组件全覆盖 / hypothesis 字段集一致性

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变）：SchemaRegistry 只做拼写检查，不扩展为规则引擎
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1（SchemaRegistry 类型化组件，query 拼写错误启动期失败）
- [ADR-0008](ADR-0008-schema-validator-four-checks.md) DSL SchemaValidator（DSL IR 层，边界对侧）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) 组件 dataclass 风格（schema 从 dataclasses.fields 提取）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T2（本任务）/ T3（DBASE_KEY_MAP 衔接 has_field）
- [spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) `_query_spec`（LPC query 静默返回 0 的规格源）
