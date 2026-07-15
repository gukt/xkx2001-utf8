# ADR-0058：ItemCatalog 过渡层（方案 B 最小子集）

- 状态：已采纳
- 日期：2026-07-16
- 阶段：第一批补架构缺口（AI 分批迁移）
- 关联：[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 附录 item-as-entity 方案 B 推荐 /
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 2（物品/消息架构）dissent /
  [ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md) §3（装备 prop 注入）/
  [ADR-0025](ADR-0025-dbase-key-classification.md)（dbase key 分类）

## 背景

pilot 样本 id=5（`songshan-jian.c:next_sword`）/ id=8（`shizi.c:bash_weapon`）暴露
greenfield 物品建模缺口：LPC 武器是物品对象（有 `weight()`/`name()`/`query("rigidity")`/
`unequip()`/`move()`/`set(...)` 方法 + `value`/`weapon_prop` 属性），greenfield 物品仅是
`Inventory.items` / `Equipment.weapon` 槽位里的 `str item_id`，物品自身属性无组件承接。
两样本当前用各自样本桩（`_DictItemRegistry` / `WeaponItem` 台账）适配，重复且不一致
（[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 决策 4：先补架构
缺口层，避免每样本各自 monkeypatch 绕过）。

现状（缺口）：

- `ItemDef`（[layer0.py](../../engine/src/xkx/dsl/layer0.py) L221）仅 8 字段
  （id/name/aliases/drink_supply/food_supply/jing_recover/qi_recover/read_skill），无武器属性。
- `Game.item_registry`（[commands.py](../../engine/src/xkx/runtime/commands.py) L77，
  `dict[str, dict]`）是物品台账后端，但只存消耗品字段，无 weight/value/rigidity/weapon_prop 等。
- dbase key `"weight"` 经 [dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) L83 映射到
  `Equipment.encumbrance`（角色负重标量）；`rigidity`/`value`/`weapon_prop` 是 unknown key，
  `query`/`set` 直接 raise `DbaseKeyError`（[ADR-0025](ADR-0025-dbase-key-classification.md)）。

## 决策

采纳 **方案 B 最小子集**：建 ItemCatalog 台账（`item_id` -> 属性 dict）+
`item_weight`/`item_query`/`item_move_to_room` 函数族（读属性 + move 掉落），**写副作用
维持现状**（per-instance set 不实现）。方案 A 物品实体化（`ItemComp` + 物品 `Position` 组件）
留 M3。

### 1. 复用扩展 `Game.item_registry` 作台账后端（单台账，避免两套）

不新建独立 ItemCatalog 类，而是**复用扩展** `Game.item_registry`（[commands.py](../../engine/src/xkx/runtime/commands.py)
L77）：`ItemDef`（[layer0.py](../../engine/src/xkx/dsl/layer0.py)）扩展加武器/物品属性字段
（带默认值，不破坏现有 8 字段），`compile_item`（[ir.py](../../engine/src/xkx/dsl/ir.py) L32）
编译进 dict，`item_registry` 自然带这些键，函数族读它。收敛单台账，drink/take/give 等读
`item_registry` 的命令语义不变（新字段带默认值，向后兼容）。

台账补字段（从 LPC 武器/物品 set 习惯提取，对照
[djdao.c](../../d/village/obj/djdao.c) / [eyujian.c](../../d/xixia/obj/eyujian.c) /
[shizi.c](../../d/taohua/obj/shizi.c) `create()`）：

- `weight`（int，物品级，默认 0；LPC `set_weight(N)`）
- `value`（int，默认 0；LPC `set("value", N)`）
- `rigidity`（int，默认 0；LPC `set("rigidity", N)`，武器硬度，击碎判定用）
- `weapon_prop`（`dict[str, int]` mapping，默认 `{}`；LPC `set("weapon_prop/damage", N)` 等，
  wield 时遍历注入 `apply/<key>`）
- `unit`（str，默认 `""`；LPC `set("unit", "把")`）
- `long`（str，默认 `""`；LPC `set("long", "...")`）
- `material`（str，默认 `""`；LPC `set("material", "steel")`）
- `flag`（int，默认 0；LPC `set("flag", EDGED)`，武器握持标记位掩码）
- `skill_type`（str，默认 `""`；LPC `set("skill_type", "sword")`，武器技能种类）

### 2. 函数族（[items.py](../../engine/src/xkx/runtime/items.py)，全新模块）

- `item_weight(game: Game, item_id: str) -> int`：读台账 `weight`（物品级）。未注册返回 0。
- `item_query(game: Game, item_id: str, key: str) -> Any`：读台账属性。`weapon_prop` 返回
  `dict[str, int]` mapping。unknown key（不在台账 dict 里）返回 `None`（非 raise：物品台账是
  开放 dict，"未设属性"与"拼写错误"难区分，返回 None 对齐 LPC `query` 未设语义；区别于 dbase
  key 的 unknown-raise，因物品属性不走 dbase_map 分类体系）。
- `item_move_to_room(game: Game, item_id: str, room_id: str) -> None`：把 `item_id` 加入
  `RoomComp.items`（`set[str]`，对照 [commands.py](../../engine/src/xkx/runtime/commands.py)
  take/drop 的 `Room.items` 用法）。`room_id` 由调用方传（对齐样本桩 `move_to_room(item_id,
  room_id)` 签名；函数内经 `game.room_entities` 取 RoomComp）。

签名带 `game: Game` 参数（对齐 commands.py 的 `Game.item_registry` 访问模式，函数族是
Game 上的物品读访问层，非模块级全局态）。

### 3. weight 双重语义（关键不变量）

LPC `feature/move.c` 的 `weight` 是**物品自身的实例字段**（`static int weight`，
`set_weight(w)`/`query_weight()`/`weight()`=自身 weight + 容器 encumb），而 greenfield dbase
key `"weight"` 经 [dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) L83 映射到
**角色级** `Equipment.encumbrance`（角色当前负重标量，[components.py](../../engine/src/xkx/runtime/components.py)
L122）。二者语义不同：

- **角色 weight**：走 dbase key `"weight"` -> `Equipment.encumbrance`
  （`query(world, eid, "weight")` / `set(world, eid, "weight", N)` 经 dbase_map）。
- **物品 weight**：走 ItemCatalog 台账 `item_weight(game, item_id)`，**绝不走 dbase key
  `"weight"`**（那是角色级 encumbrance）。

二者不可混。`item_weight` 读台账 `weight` 字段；`query(eid, "weight")` 读角色
`Equipment.encumbrance`。本 ADR 明确物品 weight 是台账独立字段，不引入 dbase key 路径。

### 4. weapon_prop mapping vs Equipment.weapon_props

LPC `weapon_prop` 是 dbase mapping（子键如 `damage`/`force`，[equip.c](../../feature/equip.c)
L60 `mapp(weapon_prop = query("weapon_prop"))`，wield 时 L100-102 遍历 keys 注入
`apply/<key>`）。greenfield `Equipment.weapon_props`（[components.py](../../engine/src/xkx/runtime/components.py)
L117）是 **per-slot prop 副本**（wield 时存 `dict(props)`，unequip 时按该副本反向扣减
`Skills.apply_*`，[equipment.py](../../engine/src/xkx/runtime/equipment.py) L99/L162），**不是
物品自身属性**，是装备槽的运行时快照。

`item_query(game, item_id, "weapon_prop")` 返回**台账 mapping**（`dict[str, int]`，物品静态
定义），**不复用** `Equipment.weapon_props`（那是某实体装备该物品后的槽位快照，随
wield/unequip 变化，非物品定义）。wield 时调用方从台账 `item_query(..., "weapon_prop")` 取
mapping 传给 `equipment.wield(props=...)`（已有路径，[equipment.py](../../engine/src/xkx/runtime/equipment.py)
L55），wield 内部存 `weapon_props` 副本。两条路径分离：台账是物品静态定义，Equipment 副本是
运行时槽位态。

### 5. 写副作用维持现状的理由（方案 B 滚雪球规避）

LPC `ob->set("name", "断掉的"+name)` / `set("value", 0)` / `set("weapon_prop", 0)` 是
**per-instance** 写（击碎武器改名 + 贬值 + 清 prop，[djdao.c](../../d/village/obj/djdao.c) do_cut
/ [songshan-jian.c](../../kungfu/skill/songshan-jian.c) next_sword L166-172）。方案 B 用
`item_id` -> dict 台账，per-instance set 会污染该 `item_id` 的**全局定义**（同名武器全变
"断掉的"），滚雪球。故：

- `item_set(game, item_id, key, val)` **不实现 per-instance 修改**：no-op + 记日志（标注
  方案 B 限制，per-instance 语义留方案 A M3）。
- 样本 id=5/8 的 `set_name`/`set_value`/`set_weapon_prop` 在样本桩里是 per-instance dict
  改（仅影响该测试注入的副本），不进 `src/xkx`。引擎层 `item_set` 维持现状 no-op。

### 6. WeaponDef schema（机制层，数据后置）

建空 `WeaponDef` schema（并入 [items.py](../../engine/src/xkx/runtime/items.py)，
pydantic BaseModel，字段 `item_id`/`name`/`damage`/`rigidity`/`flag`/`skill_type`/`weight`/`value`/`material`，
对照 LPC `init_blade(damage, flag)` + `set("rigidity")` + `set("skill_type")` +
[blade.c](../../inherit/weapon/blade.c) / [sword.c](../../inherit/weapon/sword.c) `init_*`）。
id=5/8 两武器（songshan-jian 场景的剑 / shizi 小石子对应 LPC 源）手填数据验证 schema 可用。
**全量武器数据提取（逐文件 `init_blade(N)`）是内容生产工作，留后续门派迁移批**，本批只做
schema + 2 个手填样例。

## 不做（收敛，留 M3）

- **ItemComp 物品实体化**（方案 A）：物品无 ECS 实体 / 无 `Position` 组件 / 无 per-instance
  状态。留 M3（[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 附录
  明确标注过渡）。
- **写副作用 per-instance 实现**：`item_set` no-op，per-instance 改名/贬值/清 prop 留方案 A。
- **WeaponDef 全量数据提取**：留门派迁移批。
- **per-object save / DaemonStore**：[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md)
  附录 per-object save 是独立缺口（方案 B DaemonStore），与本 ADR 分离（子任务 A 负责）。
- **str item_id 模型不变**：不做物品实体化，`Inventory.items` / `Equipment.weapon` 仍是
  `str item_id`。

## 不变量约束

1. 物品 weight 不走 dbase key `"weight"`（角色级 `Equipment.encumbrance`），必须是台账独立字段。
2. `weapon_prop` 是 mapping 非 scalar，与 `Equipment.weapon_props`（per-slot 副本）区分，不复用。
3. 方案 B 写副作用维持现状（不实现 per-instance set），否则滚雪球污染全局 `item_id` 定义。
4. `str item_id` 模型不变（不做物品实体化，留 M3）。
5. 不破坏现有 drink/take/give/`_item_name` 等读 `item_registry` 的命令（复用扩展不改其语义，
   新字段带默认值）。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **专家 2（物品/消息架构）dissent**：物品实体化时机 / 物品属性承接。本 ADR 采纳方案 B 过渡
  （台账 + 函数族），明确标注方案 A 实体化留 M3，规避 per-instance 写滚雪球，先让 id=5/8
  类样本不卡（读属性 + move 掉落），实体化等 M3 物品系统统一落地。
