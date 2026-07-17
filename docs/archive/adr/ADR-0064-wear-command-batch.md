# ADR-0064：wear 命令批（护甲数据提取 + ItemDef 扩 armor 字段 + wear/remove 命令）

- 状态：Accepted
- 日期：2026-07-16
- 阶段：门派迁移批（wear 命令，wield 批配对）
- 关联：[ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md)（装备系统机制层）/
  [ADR-0058](ADR-0058-item-catalog-transition-layer.md)（ItemCatalog 方案 B）/
  [ADR-0060](ADR-0060-weapon-data-extraction-scope.md)（武器提取范围，护甲对称）/
  [ADR-0062](ADR-0062-weapon-cpk-wiring-postpone.md)（武器 CPK 接线，护甲追加同路径）/
  [ADR-0063](ADR-0063-wield-command-batch.md)（wield 批，wear 直接配对复用决策）/
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent（message_vision 3 视角后置）

## 背景

[ADR-0063](ADR-0063-wield-command-batch.md) 完成 wield/unwield 命令批（149 武器可用 +
attack_skill 桥接 combat）。wear 是 wield 的自然配对：机制层
[equipment.py](../../engine/src/xkx/runtime/equipment.py) `wear`/`unequip`/`is_equipped`
已实现（[ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md) §3：prop 注入 apply_* +
armor_type 槽位判定 + per-slot prop 副本反向扣减），但**命令层 wear/remove 未实现**
（COMMAND_REGISTRY 未注册、cli.py 无分支），且**护甲数据未提取填表**（不像武器 149
条已落 17 数据层 CPK）。本批补护甲数据提取填表 + wear/remove 命令接线。

LPC 规格源（只读参考）：

- [cmds/std/wear.c](../../cmds/std/wear.c) `main()` 行 10-34 + `do_wear()` 行 36-69：
  无参/"all"/present 查找 + is_busy 门控 + female_only 性别门控 + 调 `ob->wear()` +
  **wear_msg 按 armor_type 分支**（cloth/armor/boots"$N穿上一{unit}$n"、
  head/neck/wrists/finger/hands"$N戴上一{unit}$n"、waist"$N将一{unit}$n绑在腰间"、
  default"$N装备$n"）。
- [cmds/std/remove.c](../../cmds/std/remove.c) `main()` 行 10-31 + `do_remove()` 行 33+：
  **卸护甲命令名是 remove（非 unwear）**，检查 `equipped=="worn"` 只管护甲槽
  （武器槽用 unwield），**remove_msg 按 armor_type 分支**（cloth/armor/surcoat/boots
  "$N将$n脱了下来"、bandage"$N将$n从伤口处拆了下来"、default"$N卸除$n的装备"）。
- [feature/equip.c](../../feature/equip.c) `wear()` 行 7-44：机制层（已实现）。前置
  `!query("armor_prop/armor")` -> "你只能穿戴可当作护具的东西。"（护甲必须有 armor 子键）。

**实施约束 1（wear_msg/remove_msg 按 armor_type 分支，但单视角）**：与 wield 单句
"你装备X作武器。"不同，wear/remove 的消息按 armor_type 分三类动词（穿/戴/绑；脱/拆/
卸）。仍遵循 [ADR-0063](ADR-0063-wield-command-batch.md) 决策 1：单视角 `return list[str]`
直拼，不保真 message_vision 三段视角（`$n`=护甲非 entity，房间广播后置 M3）。

**实施约束 2（护甲 create() 无 init_/flag，armor_type 由 inherit 宏推断）**：与武器
`init_<type>(damage, flag)` 不同，护甲 create() 是 `set("armor_prop/armor", N)` +
`setup()`（[inherit/armor/<type>.c](../../inherit/armor/) 的 setup 设 `armor_type` =
TYPE_*）。armor_type 由 `inherit HEAD/CLOTH/ARMOR/...` 宏推断（11 类型，对照
[armor.h](../../include/armor.h) TYPE_*），**无 flag 合并位语义**（护甲没有 init_ 的
TWO_HANDED/EDGED 位掩码）。setup() 副作用：weight>3000 且无 armor_apply/dodge 时
自动设 `armor_prop/dodge = -weight/3000`（重甲降闪避，[armor.c:13-15](../../inherit/armor/armor.c)）。

## 决策

### 1. wear_msg/remove_msg 单视角 `return list[str]`（按 armor_type 分支，不保真三段视角）

wear/remove 命令遵循 [ADR-0063](ADR-0063-wield-command-batch.md) 决策 1 单视角模式，
但消息按 armor_type 分支选动词（对照 wear.c:46-64 / remove.c:38-52）：

| 命令 | armor_type | greenfield 消息（玩家视角） |
|---|---|---|
| wear 成功 | cloth/armor/boots/surcoat | `你穿上一{unit}{name}。` |
| wear 成功 | head/neck/wrists/finger/hands | `你戴上一{unit}{name}。` |
| wear 成功 | waist | `你将一{unit}{name}绑在腰间。` |
| wear 成功 | 其余（shield 等） | `你装备{name}。` |
| remove 成功 | cloth/armor/surcoat/boots | `你将{name}脱了下来。` |
| remove 成功 | 其余 | `你卸除{name}。` |

**砍掉**：message_vision 三段视角（房间广播后置 M3，同 ADR-0063）。**砍掉**：
wear_msg/remove_msg/unwear_msg 自定义字段（hupi.c 等有自定义消息，后置需时扩 ItemDef，
同 ADR-0063 决策 1 对 wield_msg 的处理）。**砍掉**：bandage 类型特化"从伤口处拆下来"
（绷带是特殊护甲，后置医疗批，default 分支"卸除"兜底）。

### 2. ItemDef 扩 armor_prop + armor_type（对称 weapon_prop + skill_type，单台账）

[layer0.py](../../engine/src/xkx/dsl/layer0.py) `ItemDef` 加两字段：

- `armor_prop: dict[str, int]`：护甲属性 mapping（armor/dodge 等，对照 weapon_prop，
  承接 armor_prop/armor + armor_prop/dodge 全部子键）。
- `armor_type: str`：护甲槽位类型（head/cloth/armor/boots/...，对照 skill_type 但用于
  护甲槽位判定，题材数据声明内核不枚举，[equipment.py:128](../../engine/src/xkx/runtime/equipment.py)）。

理由（延续 [ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 决策 1 单台账 + ADR-0058
§1）：护甲数据进 `ItemDef` YAML（item_registry 唯一台账），`compile_item`（[ir.py:32-34](../../engine/src/xkx/dsl/ir.py)
`**item.model_dump()`）自动透传护甲字段进 item_registry dict。wear 命令查 spec 取
armor_prop/armor_type 调 `equipment.wear`，无需第二套 ArmorDef schema。两字段全带
默认值（空），不破坏现有 ItemDef 8 字段 + drink/take/give/wield 命令语义。

### 3. wear 前置检查 armor_prop（必须有 armor 子键）

对照 [equip.c:25-26](../../feature/equip.c)：`!query("armor_prop/armor")` ->
"你只能穿戴可当作护具的东西。"。wear 命令查 spec，**无 armor_prop 或无 armor 子键**
-> "你只能穿戴可当作护具的东西。"（对称 wield 的"只能装备可当作武器的东西"）。
`equipment.wear` 已检查 armor_type 非空 + 同类型槽位冲突，命令层只补 armor_prop 前置。

### 4. perform condition 门控保真（当前 no-op，同 ADR-0063 决策 4）

wear/remove 同 wield/unwield：`is_busy`（exercise/respirate）顶层门控 +
`query_condition("perform") > 0` 细粒度门控。当前 perform condition 未实现（恒 0），
门控 no-op，perform 系统实现后自动生效。

### 5. wear all / remove all（遍历 inventory 逐个穿脱，同 ADR-0063 决策 5）

对照 [wear.c:17-25](../../cmds/std/wear.c) / [remove.c:17-25](../../cmds/std/remove.c)：
`all` 遍历 `Inventory.items`，wear all 跳过 `is_equipped` 逐个穿，remove all 逐个卸
（do_remove 内检查 equipped 兜底）。无可穿脱 -> 提示，否则汇总 + "Ok。"。

### 6. 护甲提取/finalize 脚本（armor_prop/* 解析 + inherit 宏推断 armor_type + setup dodge 副作用）

[tools/armor_extract.py](../../engine/tools/armor_extract.py)（对标
[weapon_extract.py](../../engine/tools/weapon_extract.py)）：

- 扫 `clone/armor/*.c` + `d/*/obj/*.c` 下 `inherit (ARMOR|CLOTH|HEAD|NECK|SURCOAT|WAIST|
  WRISTS|SHIELD|FINGER|HANDS|BOOTS)` 的护甲（clone/unique 无护甲）。
- inherit 宏 -> armor_type（11 类型映射，对照 armor.h TYPE_*）。
- `set("armor_prop/<key>", N)` 解析全部 armor_prop 子键（armor/dodge 等）。
- weight 兼容两种写法：`set_weight(N)` 和 `set("weight", N)`（earring 等用后者）。
- **setup() dodge 副作用模拟**：weight>3000 且无 armor_apply/dodge 且无显式
  armor_prop/dodge -> `armor_prop/dodge = -weight/3000`。
- 后置标注：do_tear（cloth.c 撕布）/ hit_by（cloth.c 中毒反击）/ 自定义命令 /
  female_only / COMBINED_ITEM（如有）。

[tools/armor_finalize.py](../../engine/tools/armor_finalize.py)（对标
[weapon_finalize.py](../../engine/tools/weapon_finalize.py)）：

- 草表 -> 去重分类（clone/armor > d/*/obj 权威源，em->emei 折叠）。
- **merge 进现有 items.yaml（不覆盖武器）**：护甲条目追加进武器已落的
  `wuxia_common/items.yaml` + `wuxia_<sect>/items.yaml`，按 id 去重（护甲 id 不与
  武器冲突），读现有 + 追加 + 写回。weapon_finalize 不重跑（避免覆盖护甲）。
- 后置缺口注释标维度归属。

## 不做（收敛，延续 ADR-0063）

- 不保真 message_vision 三段视角（房间广播后置 M3，决策 1）。
- 不渲染 wear_msg/remove_msg 的 `$N`/`$n` 模板（单视角直拼，决策 1）。
- 不扩 ItemDef 加 wear_msg/remove_msg/unwear_msg 字段（自定义消息后置，决策 1）。
- 不实现 female_only 性别门控（earring-diamond 等饰品有，后置物品系统批，标注）。
- 不实现 cloth.c do_tear 撕布 / hit_by 中毒反击（后置命令批 / M3 招式表）。
- 不自动算物品重量（wear/remove 不调 add_encumbrance，同 ADR-0063）。
- 不实现 bandage 类型特化 remove_msg（后置医疗批）。
- 不修改 LPC 源（只读规格）。

## 不变量约束

1. **单台账**：护甲数据进 `ItemDef` YAML（item_registry 唯一台账），不重建 ArmorDef
   第二套数据源（延续 [ADR-0058](ADR-0058-item-catalog-transition-layer.md) §1 /
   [ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 决策 1）。
2. **armor_prop 走 mapping**：armor/dodge 走 `armor_prop` 子键（对齐 LPC
   `set("armor_prop/armor", N)`），非标量。wear 注入 `apply/<key>`（APPLY_SUBPATH_MAP
   含 armor/dodge 等 6 key，[dbase_map.py:123-130](../../engine/src/xkx/runtime/dbase_map.py)）。
3. **str item_id 模型不变**：护甲是 item_id 非 ECS 实体（延续 ADR-0058 不变量 4）。
4. **Command 仅覆盖外部意图**：wear/remove 是玩家外部意图命令，走 8 段管线 + CLI 双路径
   （延续 [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md)）。
5. **PronounContext 三元组已落地**（[ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md)）：
   wear 单视角 `return list[str]` 不直接消费，本批不涉及。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **message_vision 3 视角分发后置**（ADR-0028 简化台账第 9 项）：wear_msg/remove_msg
  不走三段视角，单视角 `return list[str]`，房间广播后置 M3（延续 ADR-0063）。
- **专家 6（范围纪律）**：本批严守"护甲数据 + 命令接线"，不扩 ItemDef 加自定义消息字段、
  不实现 female_only/do_tear/hit_by，避免范围过载。

## 产出

- [layer0.py](../../engine/src/xkx/dsl/layer0.py)：`ItemDef` 加 `armor_prop` + `armor_type`。
- [tools/armor_extract.py](../../engine/tools/armor_extract.py) + [armor_finalize.py](../../engine/tools/armor_finalize.py)。
- [scenes/wuxia_common/items.yaml](../../engine/scenes/wuxia_common/) +
  `wuxia_<sect>/items.yaml`：追加护甲条目（merge，不覆盖武器）。
- [commands.py](../../engine/src/xkx/runtime/commands.py)：`wear`/`remove` 终端函数 +
  adapter + COMMAND_REGISTRY 注册。
- [cli.py](../../engine/src/xkx/cli.py) parse_and_run：wear/remove 分支。
- [tests/test_wear_command.py](../../engine/tests/test_wear_command.py)：wear/remove 命令测试。
- justfile `armor-load` recipe。
- tests 2397 -> 增 wear 测试 + ItemDef 扩字段测试。

*最后更新：2026-07-16*
