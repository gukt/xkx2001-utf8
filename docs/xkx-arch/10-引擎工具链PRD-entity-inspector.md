# 引擎工具链 PRD：Entity Inspector（实体检视器）

> 创建日期：2026-07-11
> 阶段：0 PRD（阶段 1 同步开发）
> 关联：[04 §三阶段 1](04-迁移路径与避坑清单.md) 工具链同步、[04 §六](04-迁移路径与避坑清单.md) 最小三件、[层 B 对象基础规格](../engine/src/xkx/spec/layer_b_object_base.py) F_DBASE 语义

---

## 一、定位与目标

### 1.1 工具链中的角色

Entity Inspector 是引擎工具链最小三件（Entity Inspector / Tick Profiler / Combat Replay Viewer）之一，定位为**阶段 1 开发期调试工具**，非生产运维工具。其核心职责：

- 在开发期提供实体状态的**只读快照检视**能力，帮助开发者验证 ECS 组件数据的正确性。
- 为 Tick Profiler 和 Combat Replay Viewer 提供**程序化查询接口**（这两个工具需要按 entity_id 或组件类型检索实体状态来关联性能数据/战斗回放帧）。
- 在 LPC 语义与 ECS 组件之间提供**映射对照**，便于开发者将 LPC `query("key")` 的心智模型对应到 ECS 组件字段。

### 1.2 与运行时引擎的关系

- **进程内只读模块**：Entity Inspector 是 `xkx.runtime` 的子模块，直接读取 `World` 实例的组件数据，不引入跨进程通信。
- **只读不写**：阶段 1 严格只读，不修改任何组件状态，不影响 tick 调度，不产生副作用。
- **非热路径**：Inspector 不参与 tick 循环，仅在开发者显式调用或 Tick Profiler / Replay Viewer 请求时执行查询。
- **单进程 asyncio 安全**：查询在事件循环中同步执行（纯内存 dict 读取，微秒级），不引入锁、不跨线程。

### 1.3 非目标

- 不是生产运维面板（无 Web UI、无远程连接、无告警）。
- 不是存档浏览工具（不读取 JSON 存档文件，只检视内存中的运行时状态）。
- 不是修改工具（阶段 1 不支持 `set` / `add` 修改组件字段，后置能力见 §七）。

---

## 二、核心功能

### 2.1 实体查询

支持以下过滤维度检索实体列表：

| 查询方式 | 示例 | 说明 |
|---|---|---|
| 按 entity_id | `inspect 42` | 精确查询单个实体的全部组件 |
| 按组件类型 | `inspect --filter comp=Vitals` | 列出所有拥有 Vitals 组件的实体 |
| 按位置 | `inspect --filter position=room:xkx/chaguan` | 列出指定房间内所有实体 |
| 按组件类型组合 | `inspect --filter comp=Vitals,Position` | 列出同时拥有指定组件的实体 |
| 按名称 | `inspect --filter name=官兵` | 按 Identity.name 模糊匹配 |
| 列出全部 | `inspect --list` | 列出所有实体（entity_id + name + 位置） |

查询返回 entity_id 列表，可进一步检视单个实体的组件详情。

### 2.2 组件状态检视

对单个实体，展示其拥有的全部组件及字段值。支持以下粒度：

| 命令 | 展示范围 |
|---|---|
| `inspect <eid>` | 全部组件概览（组件名 + 关键字段摘要） |
| `inspect <eid> vitals` | Vitals 组件全部字段 |
| `inspect <eid> identity` | Identity 组件全部字段 |
| `inspect <eid> position` | Position 组件全部字段 |
| `inspect <eid> skills` | Skills 组件全部字段 |
| `inspect <eid> combat` | CombatState 组件全部字段 |
| `inspect <eid> marks` | Marks 组件全部字段 |
| `inspect <eid> quest` | QuestLog 组件全部字段 |
| `inspect <eid> inventory` | Inventory 组件全部字段 |
| `inspect <eid> npc` | NpcBehavior 组件全部字段 |

### 2.3 LPC F_DBASE 语义映射

LPC 中所有对象数据通过 `set(prop, data)` / `query(prop)` / `set_temp(prop, data)` / `query_temp(prop)` 访问，prop 可含 `/` 路径分隔符（如 `"skill/axe"`）。Inspector 提供 LPC dbase key -> ECS 组件字段的映射表，使开发者能用 LPC 心智模型定位 ECS 数据。

#### 映射表（阶段 1 核心组件）

| LPC dbase key | dbase/temp | ECS 组件 | 字段 | 说明 |
|---|---|---|---|---|
| `name` | dbase | Identity | `name` | 对象中文名 |
| `id` | dbase | Identity | `aliases[0]` / `prototype_id` | 主 ID |
| `title` | dbase | Identity | （后置） | 称谓，阶段 2 称谓系统 |
| `nickname` | dbase | Identity | （后置） | 绰号 |
| `family` / `family_name` | dbase | Attributes | `family` | 门派（S4 ADR-0005） |
| `str` / `dex` / `int` / `con` | dbase | Attributes | `str_` / `dex_` / `int_` / `con_` | 先天属性 |
| `age` | dbase | Attributes | `age` | 年龄 |
| `gender` | dbase | Attributes | `gender` | 性别 |
| `qi` / `max_qi` / `eff_qi` | dbase | Vitals | `qi` / `max_qi` / `eff_qi` | 气血 |
| `jing` / `max_jing` | dbase | Vitals | `jing` / `max_jing` | 精 |
| `jingli` / `max_jingli` | dbase | Vitals | `jingli` / `max_jingli` | 精力 |
| `neili` / `max_neili` | dbase | Vitals | `neili` / `max_neili` | 内力 |
| `combat_exp` | dbase | Vitals | `combat_exp` | 战斗经验 |
| `potential` | dbase | Vitals | `potential` | 潜能 |
| `skill/<skill_id>` | dbase | Skills | `levels[skill_id]` | 技能等级（路径访问） |
| `apply_attack` / `apply_dodge` / `apply_parry` / `apply_damage` / `apply_armor` | dbase | Skills | `apply_*` | 技能加成 |
| `marks/<flag_name>` | temp | Marks | `flags` (set) | 临时标记（路径访问，S4 ADR-0006） |
| `inquiry` | dbase | NpcBehavior | `inquiry` | NPC 对话主题 |
| `attitude` | dbase | NpcBehavior | `attitude` | NPC 态度 |
| `chat_chance_combat` | dbase | NpcBehavior | `chat_chance_combat` | 战斗喊话概率 |
| `chat_msg_combat` | dbase | NpcBehavior | `chat_msg_combat` | 战斗喊话内容 |
| `short` / `long` | dbase | RoomComp | `short` / `long` | 房间描述（RoomComp 实体） |
| `exits` | dbase | RoomComp | `exits` | 房间出口 |
| `outdoors` | dbase | RoomComp | `outdoors` | 是否户外 |
| `no_fight` | dbase | RoomComp | `no_fight` | 禁止战斗 |
| `equipped` | dbase | （后置） | - | 装备状态，阶段 2 |
| `weight` / `encumbrance` | dbase | （后置） | - | 负重，阶段 2 F_MOVE |
| `channels` | dbase | （后置） | - | 频道，阶段 2 F_MESSAGE |

#### 路径访问语义

LPC `query("skill/axe")` 的路径访问语义在 ECS 中映射为嵌套结构的点访问：

- `skill/axe` -> `Skills.levels["axe"]`
- `marks/酥` -> `Marks.flags.__contains__("酥")`

Inspector 在展示组件详情时，对含路径访问的 key（skill/marks）同时展示原始 LPC 路径形式和 ECS 字段路径，方便开发者对照。

#### default_ob 回退

LPC `query(prop)` 在当前对象 dbase 未找到时委托 `default_ob->query(prop)` 查找默认值。阶段 1 ECS 无 default_ob 概念，Inspector 对映射表中标记为"后置"的 key 显示 `(unmapped)` 而非尝试回退，避免引入不存在的语义。

### 2.4 调试修改能力

| 能力 | 阶段 1 | 后置 |
|---|---|---|
| 只读快照检视 | 支持 | - |
| 修改组件字段 | 不支持 | 后置（见 §七） |
| 设置临时标记 | 不支持 | 后置 |
| 创建/销毁实体 | 不支持 | 后置 |

阶段 1 严格只读。修改能力后置到阶段 2 子系统实现期间，届时按需引入受控修改接口（带审计日志）。

---

## 三、接口设计

### 3.1 CLI 命令格式

Inspector 提供开发期 CLI 命令，在引擎调试 shell 中执行（非玩家命令管线的一部分）：

```
inspect                         # 列出全部实体概览
inspect <eid>                   # 检视实体全部组件
inspect <eid> <comp>            # 检视实体指定组件
inspect --list                  # 列出全部实体（entity_id + name + room_id）
inspect --filter comp=<C1,C2>   # 按组件类型过滤
inspect --filter position=<room_id>  # 按位置过滤
inspect --filter name=<keyword> # 按名称过滤
inspect --map <lpc_key>         # 查询 LPC dbase key 对应的 ECS 组件/字段
inspect --help                  # 帮助
```

**输出格式**（人类可读的文本表格）：

```
> inspect 42
Entity #42  [player]  官兵  room: xkx/chaguan

  Identity:
    name         官兵
    aliases      [bing, guanbing]
    is_player    False
    prototype_id city/npc/bing

  Vitals:
    qi           85/100 (eff: 100)
    jing         100/100
    jingli       80/100
    neili        0/0
    combat_exp   500
    potential    10

  Position:
    room_id      xkx/chaguan

  CombatState:
    enemy_ids    []
    attack_skill unarmed
    weapon_label 拳头

  Marks:
    flags        {}

> inspect --filter position=xkx/chaguan
  #42  官兵      [npc]     xkx/chaguan
  #43  玩家甲    [player]  xkx/chaguan

> inspect --map skill/axe
  LPC key: skill/axe
  ECS path: Skills.levels["axe"]
  Component: Skills
  Field: levels (dict[str, int])
```

### 3.2 程序化 API

供 Tick Profiler / Combat Replay Viewer 调用的 Python API：

```python
from xkx.runtime.inspector import EntityInspector

# 初始化（传入 World 实例引用）
inspector = EntityInspector(world)

# 按 entity_id 查询
snapshot = inspector.snapshot(eid)  # -> EntitySnapshot

# 按组件类型查询
eids = inspector.query_by_component(Vitals, Position)  # -> list[int]

# 按位置查询
eids = inspector.query_by_room("xkx/chaguan")  # -> list[int]

# 按名称查询
eids = inspector.query_by_name("官兵")  # -> list[int]

# 获取单组件快照
vitals = inspector.component_snapshot(eid, Vitals)  # -> dict[str, Any]

# LPC key 映射查询
mapping = inspector.lpc_key_mapping("skill/axe")
# -> LPCKeyMapping(component=Skills, field_path='levels["axe"]', lpc_scope="dbase")
```

**返回类型**：

- `EntitySnapshot`：`{entity_id: int, components: dict[str, dict[str, Any]]}`，组件名为 key，字段值为序列化后的 dict。
- `LPCKeyMapping`：`{lpc_key: str, component: type, field_path: str, lpc_scope: str, mapped: bool}`，映射表中未找到时 `mapped=False`。

**设计约束**：

- API 全部为同步纯内存读取，无 IO，无 async。
- 返回值为不可变快照（`dict` 的浅拷贝），调用方修改不影响运行时状态。
- 组件字段值通过 `dataclasses.asdict()` 序列化为 dict，set 类型转为 sorted list 以保证确定性输出。

---

## 四、数据模型

### 4.1 快照 vs 实时

阶段 1 采用**实时读取**模式：Inspector 每次 `snapshot()` 调用时直接从 `World._entities` 读取当前值。理由：

- 单进程 asyncio 无并发写入风险（查询在事件循环同步执行）。
- 快照拷贝成本极低（单实体组件数 < 10，字段数 < 20，微秒级）。
- 开发期调试场景需要看到"当前"状态，快照反而引入困惑。

后置阶段（§七）可引入快照存档 + 历史回溯，阶段 1 不做。

### 4.2 组件序列化格式

每个组件序列化为扁平 dict：

```python
# Vitals 组件序列化示例
{
    "qi": 85,
    "max_qi": 100,
    "eff_qi": 100,
    "jing": 100,
    "max_jing": 100,
    "jingli": 80,
    "max_jingli": 100,
    "neili": 0,
    "max_neili": 0,
    "combat_exp": 500,
    "potential": 10,
}
```

特殊类型处理：

| Python 类型 | 序列化形式 | 示例 |
|---|---|---|
| `set` | sorted list | `{"a", "b"}` -> `["a", "b"]` |
| `dict` | 原样保留 | `{"axe": 50}` -> `{"axe": 50}` |
| `list` | 原样保留 | `["bing"]` -> `["bing"]` |
| `None` | `null` | - |
| `bool` | `true/false` | - |
| `int/str` | 原样 | - |

### 4.3 LPC 映射表数据结构

```python
@dataclass(frozen=True)
class LPCKeyMapping:
    lpc_key: str           # 如 "skill/axe"
    lpc_scope: str         # "dbase" | "temp"
    component: type        # 如 Skills
    field_path: str        # 如 'levels["axe"]'
    mapped: bool           # False = 后置/未映射
    note: str              # 补充说明（如 "后置：阶段 2 装备系统"）
```

映射表为模块级常量 `LPC_KEY_MAP: dict[str, LPCKeyMapping]`，阶段 1 覆盖 §二.3 映射表中的全部条目。

---

## 五、与引擎集成点

### 5.1 只读快照避免影响 tick

- Inspector 通过 `World.get(eid, comp_type)` / `World.entities_with(*comp_types)` / `World.entities_in_room(room_id)` 读取数据，这些方法在现有 ECS 中已是纯只读（参见 `engine/src/xkx/runtime/ecs.py`）。
- 不注册任何 System、不订阅事件、不注入 tick 调度。
- `snapshot()` 调用 `dataclasses.asdict()` 对组件做浅拷贝，返回值与运行时状态隔离。

### 5.2 并发安全

- 单进程 asyncio：所有查询在事件循环的同步段执行（纯 dict 读取，不 yield），不存在与 tick System 的交错执行。
- 无锁、无线程、无协程切换：`snapshot()` 从调用到返回之间不会被 tick 中断。
- 不需要 asyncio.Lock 或任何同步原语。

### 5.3 性能影响

| 操作 | 复杂度 | 目标延迟 | 说明 |
|---|---|---|---|
| `snapshot(eid)` | O(组件数) | < 0.01ms | 单实体 < 10 组件，dict 读取 + asdict 浅拷贝 |
| `query_by_component(*types)` | O(实体数) | < 0.1ms | 1000 实体遍历，SparseSet 后置后可优化 |
| `query_by_room(room_id)` | O(实体数) | < 0.1ms | 同上，遍历 Position 组件 |
| `query_by_name(keyword)` | O(实体数) | < 0.1ms | 同上，遍历 Identity 组件 |
| `lpc_key_mapping(key)` | O(1) | < 0.001ms | dict 查找 |

性能预算：< 0.1ms/查询，在 1000 实体规模下单次查询不超过 tick 预算（100ms）的 0.1%。阶段 1 的 dict 存储 ECS 已足够；SparseSet 后置后 `entities_with` 可进一步优化但非先决条件。

### 5.4 模块位置

```
engine/src/xkx/runtime/
├── ecs.py              # 现有 World 类
├── components.py       # 现有组件定义
├── inspector.py        # 新增：EntityInspector + LPCKeyMapping
└── inspector_cli.py    # 新增：CLI 命令解析（可选，可合并到 inspector.py）
```

---

## 六、最小实现范围（阶段 1 同步开发）

### 6.1 必须功能

| 功能 | 验收标准 |
|---|---|
| `EntityInspector` 类 | 初始化接收 `World` 实例，提供 `snapshot` / `query_by_component` / `query_by_room` / `query_by_name` / `component_snapshot` / `lpc_key_mapping` 方法 |
| LPC 映射表 | 覆盖 §二.3 映射表中全部"阶段 1"条目，未映射条目标记 `mapped=False` |
| CLI `inspect` 命令 | 支持 §三.1 全部命令格式，输出人类可读文本 |
| 组件序列化 | 全部现有组件（Identity / Position / Attributes / Vitals / Skills / CombatState / NpcBehavior / Inventory / Marks / QuestLog / RoomComp）可序列化为 dict |
| 只读保证 | 无任何写入操作，无副作用，无 System 注册 |
| 测试 | pytest 覆盖：查询正确性、序列化确定性、LPC 映射覆盖、只读不变量 |

### 6.2 不做（阶段 1 范围外）

| 不做项 | 理由 | 何时做 |
|---|---|---|
| 修改组件字段 | 阶段 1 只读 | 后置 §七 |
| 历史快照存档 | 收敛优先，开发期实时读取够用 | 后置 §七 |
| 远程检视（WebSocket） | 单进程开发期工具，无远程需求 | 后置 §七 |
| Tick Profiler 集成 | Tick Profiler 尚未实现，先定 API 接口 | 阶段 1 Tick Profiler 开发时 |
| Combat Replay Viewer 集成 | 同上 | 阶段 1 Replay Viewer 开发时 |
| Web UI | 生产运维后置 | 后置 §七 |
| 存档文件检视 | Inspector 检视内存状态，非存档 | 不做（存档工具另议） |
| apply 掩码展示 | apply/short / apply/name 等 LPC 掩码机制阶段 1 未实现 | 阶段 2 F_NAME 实现后 |
| default_ob 回退查询 | 阶段 1 ECS 无 default_ob 概念 | 阶段 2 如需引入 |

---

## 七、后置能力

以下能力在阶段 1 不实现，预留接口和设计空间，按触发条件推进：

### 7.1 实时修改

- **触发条件**：阶段 2 子系统实现期间，开发者需要快速修改组件字段验证逻辑。
- **设计**：`inspector.set_field(eid, comp_type, field, value)` + 审计日志（记录修改者 / 修改前 / 修改后 / 时间戳）。
- **约束**：修改操作不直接走 Command 管线（开发工具非玩家意图），但需 ROOT 权限门控 + 强制审计（对齐 `force_me = PrivilegedAction` 的保真让步原则）。

### 7.2 历史回溯

- **触发条件**：Tick Profiler 和 Combat Replay Viewer 需要关联历史帧的实体状态。
- **设计**：Inspector 支持 `snapshot_at(tick_id)` 查询历史快照。需要引擎先实现 tick 级快照存档（CombatContext 快照已有，扩展到全实体快照）。
- **约束**：历史快照存储为追加日志（非全量拷贝），采用 dirty-flag 增量记录。与 JSON 存档的崩溃安全约束一致（write-temp + os.replace 原子写）。

### 7.3 远程检视（WebSocket）

- **触发条件**：开发者需要从外部工具（如 Web 调试面板）连接引擎检视实体状态。
- **设计**：Inspector 暴露 WebSocket 端点（复用阶段 1 WS 服务器），JSON 格式返回快照数据。
- **约束**：认证复用阶段 1 HS256 + 内存 session token；不引入独立鉴权体系。单进程内，无跨节点通信。

### 7.4 与 Tick Profiler 联动

- **触发条件**：Tick Profiler 实现后，需要按 entity_id 关联性能数据与实体状态。
- **设计**：Tick Profiler 输出的 per-entity 性能数据可携带 entity_id，Inspector API 提供 `snapshot(eid)` 供 Profiler 前端调用展示实体上下文。
- **约束**：Inspector 不依赖 Tick Profiler，单向被调用。

### 7.5 与 Combat Replay Viewer 联动

- **触发条件**：Combat Replay Viewer 实现后，需要在回放帧中展示实体状态。
- **设计**：Replay Viewer 的回放帧包含 entity_id 列表，Inspector API 提供 `snapshot(eid)` 供 Viewer 在回放时查询实体详情。
- **约束**：Combat 确定性范围 = combat-only，Inspector 查询的是全实体状态（非 combat 快照），两者数据源不同但接口统一。

---

## 八、映射表维护策略

LPC dbase key 到 ECS 组件的映射表是**活的文档**，随子系统实现逐步扩展：

| 阶段 | 新增映射来源 | 维护动作 |
|---|---|---|
| 阶段 1 | 现有 11 组件（S1-S4e 已定义） | 初始映射表，覆盖 §二.3 全部条目 |
| 阶段 2.1 | Query/索引层 + Identity/Position/Inventory 扩展 | 补全 Identity 别名/称号、Inventory 物品详情 |
| 阶段 2.2 | Vitals/Heal/Condition | 补全 condition 状态映射 |
| 阶段 2.3 | Attribute/Skill/Equipment | 补全 ModifierStack 三类语义、装备字段 |
| 阶段 2.4 | Combat | 补全 CombatContext 快照字段映射 |
| 阶段 2.5 | TitleSystem | 补全称谓三元组映射 |
| 阶段 2.6 | WorldGovernanceSystem | 补全治理状态映射 |

映射表更新需在对应阶段的 ADR 中记录变更（新增 key / 修改映射 / 标记后置项转为已映射）。

---

## 九、关联文档

- [04-迁移路径与避坑清单](04-迁移路径与避坑清单.md)：§三阶段 1 工具链同步、§六不做清单最小三件、范围检查点 10
- [06-阶段-1-实施计划](06-阶段-1-实施计划.md)：阶段 1 ECS 骨架与组件定义
- [layer_b_object_base.py](../engine/src/xkx/spec/layer_b_object_base.py)：LPC F_DBASE set/query/set_temp/query_temp 规格规格
- [ADR-0001](../docs/adr/ADR-0001-python-toolchain-and-skeleton.md)：工具链与项目骨架
- [engine/src/xkx/runtime/ecs.py](../engine/src/xkx/runtime/ecs.py)：World 类（Inspector 数据源）
- [engine/src/xkx/runtime/components.py](../engine/src/xkx/runtime/components.py)：组件定义（Inspector 检视目标）

---

*本 PRD 遵循 [04 §一原则 7](04-迁移路径与避坑清单.md) 收敛优先于完备：最小可用即可，不过度设计。后置能力按触发条件推进，不为不存在的需求建设基础设施。*
