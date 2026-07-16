# ADR-0063：wield 命令批（消息渲染简化 + WeaponDef 删除 + skill_type 桥接）

- 状态：Accepted
- 日期：2026-07-16
- 阶段：门派迁移批（wield 命令）
- 关联：[ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md)（装备系统机制层）/
  [ADR-0058](ADR-0058-item-catalog-transition-layer.md)（ItemCatalog 方案 B）/
  [ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 决策 1（WeaponDef deprecated）/
  [ADR-0062](ADR-0062-weapon-cpk-wiring-postpone.md) 决策 4（武器 CPK 接线）/
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent（message_vision 3 视角后置）

## 背景

[ADR-0062](ADR-0062-weapon-cpk-wiring-postpone.md) 决策 4 把 149 门派武器接入
`game.item_registry`（flag/weapon_prop/skill_type 字段就绪），为 wield 命令铺路。机制层
[equipment.py](../../engine/src/xkx/runtime/equipment.py) `wield`/`unequip`/`is_equipped`
已实现（[ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md) §3：prop 注入 apply_* +
flag 槽位判定 + reset_action 更新 CombatState），但**命令层 wield/unwield 未实现**
（[commands.py](../../engine/src/xkx/runtime/commands.py) COMMAND_REGISTRY 未注册、
[cli.py](../../engine/src/xkx/cli.py) parse_and_run 无分支）。本批补命令层接线。

LPC 规格源（只读参考）：

- [cmds/std/wield.c](../../cmds/std/wield.c) `main()` 行 8-34 + `do_wield()` 行 36-52：
  参数解析（无参/`all`/present 查找）+ is_busy 门控 + perform condition 门控 +
  调 `ob->wield()` + `message_vision(wield_msg, me, ob)`（默认 `"$N装备$n作武器。\n"`）。
- [cmds/std/unwield.c](../../cmds/std/unwield.c) 行 6-34：类似，默认
  `"$N放下手中的$n。\n"`，副作用 sword + dodge dugu-jiujian 清映射（行 27-29）。
- [feature/equip.c](../../feature/equip.c) `wield()` 行 46-107：机制层（已实现）。

**实施约束 1（wield_msg 的 `$n` 是武器非 entity）**：LPC `message_vision(str, me, ob)`
的 `ob` 是武器对象（有 `name()`），`$n` -> `ob->name()`。[message.py](../../engine/src/xkx/runtime/message.py)
`message_vision(world, msg, me, you)` 的 `you` 是 entity_id，`$n` 走 `_name(world, you)`
（取 entity 的 Identity.name）。greenfield 武器是 `str item_id`（非 ECS 实体，无 Identity
组件，[ADR-0058](ADR-0058-item-catalog-transition-layer.md) 方案 B），`message_vision` 取
不到武器名。且 `you=None` 时 `$n` 不替换（[message.py:72-89](../../engine/src/xkx/runtime/message.py)）。

**实施约束 2（现有命令单视角）**：[commands.py](../../engine/src/xkx/runtime/commands.py)
现有命令（take/drop/drink/look）统一 `return list[str]`（玩家视角"你..."），由
[cli.py](../../engine/src/xkx/cli.py) `_print` 打印，**不走 message_vision 三段视角**。
message_vision 三段视角分发（me/you/room）后置 M3 消息系统
（[ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 简化台账第 9 项）。

## 决策

### 1. wield_msg 单视角 `return list[str]`（不保真 message_vision 三段视角）

wield/unwield 命令遵循现有命令模式：`return list[str]` 玩家视角，不渲染 `$N`/`$n` 模板，
直接拼字符串。

| 命令 | greenfield 消息（玩家视角） | LPC 默认 wield_msg |
|---|---|---|
| wield 成功 | `你装备{name}作武器。` | `$N装备$n作武器。\n`（$N=你，$n=武器名） |
| unwield 成功 | `你放下了{name}。` | `$N放下手中的$n。\n` |

**砍掉**：message_vision 三段视角（房间其他人看不到"张三装备了X"）。后置 M3 消息系统
（多实体分发 + session 分桶，[message.py:5-6](../../engine/src/xkx/runtime/message.py) 注释）。
理由：当前单玩家 demo，房间广播未接通；与 take/drop/drink 一致收敛；保真 wield_msg
模板渲染需扩展 message_vision 支持非 entity 的 `$n`（破坏 you 是 entity 的语义），复杂度
不值。

**砍掉**：wield_msg/unwield_msg 自定义字段。LPC 武器 `create()` 可 `set("wield_msg", "...")`
自定义装备消息，当前 [ItemDef](../../engine/src/xkx/dsl/layer0.py) 无此字段
（[wuxia_common/items.yaml:3](../../engine/scenes/wuxia_common/items.yaml) 注释明确留 wield
命令批），149 武器统一用默认值。自定义 wield_msg 后置（需时扩 ItemDef 加 `wield_msg` 字段）。

### 2. WeaponDef 彻底删除（ADR-0060 决策 1 定夺）

[items.py](../../engine/src/xkx/runtime/items.py) `WeaponDef` + `SAMPLE_WEAPONS` +
`get_weapon_def` 删除。理由：

- **无 src 引用**（grep 确认）：仅 [items.py](../../engine/src/xkx/runtime/items.py) 定义 +
  [test_items.py](../../engine/tests/test_items.py) 测试，无运行时消费者。
- **错误建模**：`WeaponDef.damage` 是标量，丢 `weapon_prop` 子键（speed/dodge，法轮实证），
  [items.py:128-131](../../engine/src/xkx/runtime/items.py) 注释已述。全量武器数据改由
  ItemDef YAML 台账承载（[ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 决策 1 +
  [ADR-0062](ADR-0062-weapon-cpk-wiring-postpone.md) 接线进 item_registry）。
- 149 武器走 `item_registry` dict（含 `weapon_prop`/`flag`/`skill_type` 全字段），
  `item_query(game, item_id, key)` 读台账，无需第二套 WeaponDef schema。

[test_items.py](../../engine/tests/test_items.py) WeaponDef 测试段（行 232-305）删除，
保留 ItemCatalog 函数族测试 + ItemDef 扩展字段测试。
[test_songshan_jian_c_next_sword.py](../../engine/tests/test_songshan_jian_c_next_sword.py) /
[test_shizi_c_bash_weapon.py](../../engine/tests/test_shizi_c_bash_weapon.py) 用 pilot
样本桩（`tools.sampling.pilot.samples`），不引用 WeaponDef，删除安全。

### 3. skill_type 桥接（wield 传 skill -> CombatState.attack_skill）

wield 命令调 `equipment.wield(world, actor_id, item_id, props=spec["weapon_prop"],
flag=spec["flag"], skill=spec["skill_type"], label=spec["name"])`。

- `skill=spec["skill_type"]`：[equipment.py:104-108](../../engine/src/xkx/runtime/equipment.py)
  设 `CombatState.attack_skill = skill`，补全 [ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md)
  reset_action "有武器时 type=weapon skill_type 需 item_registry 桥接（当前未桥接）"的桥接。
- `label=spec["name"]`：设 `CombatState.weapon_label`（武器显示名，对照 LPC reset_action）。
- `props=spec["weapon_prop"]`：weapon_prop mapping 注入 `apply/<key>`（damage->apply_damage
  等 6 key，未知 key 忽略，[equipment.py:39-49](../../engine/src/xkx/runtime/equipment.py)）。
- `flag=spec["flag"]`：TWO_HANDED/SECONDARY 槽位判定（[equipment.py:79-91](../../engine/src/xkx/runtime/equipment.py)）。

**reset_action 完整逻辑后置**：本批只桥接 attack_skill/weapon_label（wield 时设），
reset_action 的招式表推断（actions 闭包 / query_action）后置 M3 combat
（[ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md) §5 简化台账第 3 项）。

### 4. perform condition 门控保真（当前 no-op）

对照 [wield.c:40-42](../../cmds/std/wield.c)：`query_condition("perform")` 非空且
`!= ob->query("skill_type")` -> "你正忙着也。"（perform 期间不能换不同 skill_type 武器）。

greenfield 实现：wield 命令 `query_condition(world, actor_id, "perform") > 0` -> busy。
**当前 perform condition 未实现**（[conditions.py](../../engine/src/xkx/runtime/conditions.py)
无 perform condition 类，`query_condition("perform")` 恒 0），门控 no-op。perform 系统
实现后自动生效（保真逻辑就位，不因后置而补丁）。

`is_busy`（[skill.py:170](../../engine/src/xkx/runtime/skill.py)，BUSY_CONDITIONS=
{exercise, respirate}）作为顶层门控（打坐/吐纳期间不能 wield，对照 wield.c:15）。
perform 是 do_wield 内的细粒度门控（不同 skill_type 切换），两者正交。

### 5. wield all（遍历 inventory 逐个装备）

对照 [wield.c:18-25](../../cmds/std/wield.c)：`arg=="all"` 遍历 `all_inventory(me)`，
跳过已 equipped，逐个 `do_wield`，末尾 `write("Ok.\n")`。greenfield 实现：遍历
`Inventory.items`，跳过 `is_equipped`，逐个调 wield 收集消息，无可装备 -> "你没有可
装备的武器。"，否则返回汇总 + "Ok。"。

## 不做（收敛）

- 不保真 message_vision 三段视角（房间广播后置 M3，决策 1）。
- 不渲染 wield_msg/unwield_msg 的 `$N`/`$n` 模板（单视角直拼，决策 1）。
- 不扩 ItemDef 加 wield_msg/unwield_msg 字段（自定义装备消息后置，决策 1）。
- 不实现 unwield 的 sword + dodge dugu-jiujian 清映射副作用
  （[unwield.c:27-29](../../cmds/std/unwield.c)，dugu-jiujian 是独孤九剑特殊武学，
  dodge 映射未接，后置武学批）。
- 不实现双武器完整切换（辟邪剑/双手互博，后置 2.4 Combat，
  [ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md) §5 简化台账第 5 项）。
- 不自动算物品重量（wield/wear 不调 add_encumbrance，后置 M3 物品系统，
  [ADR-0026](ADR-0026-modifier-stack-and-skill-layers.md) 实现期细化第 6 项）。
- 不实现 reset_action 完整招式表推断（后置 M3 combat，决策 3）。
- 不重构 WeaponDef 为 ItemDef 投影视图（彻底删除，决策 2）。
- 不修改 LPC 源（只读规格）。

## 不变量约束

1. **单台账**：武器数据只走 `item_registry`（ItemDef YAML 台账），不重建第二套数据源
   （延续 [ADR-0058](ADR-0058-item-catalog-transition-layer.md) §1 / [ADR-0060](ADR-0060-weapon-data-extraction-scope.md)
   决策 1）。WeaponDef 删除不破坏单台账。
2. **damage 走 weapon_prop mapping**：wield 注入 `weapon_prop` 子键（damage/speed/dodge 等）
   到 `apply/<key>`，非标量（延续 [ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 不变量 2）。
3. **str item_id 模型不变**：不引入物品实体化（武器是 item_id 非 ECS 实体，延续
   [ADR-0058](ADR-0058-item-catalog-transition-layer.md) 不变量 4 / [ADR-0060](ADR-0060-weapon-data-extraction-scope.md)
   不变量 6）。wield_msg 的 `$n`=武器名由 `_item_name` 取，非 entity name。
4. **Command 仅覆盖外部意图**：wield/unwield 是玩家外部意图命令，走 8 段管线 + CLI 双路径
   （延续 [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md)）。
5. **PronounContext 三元组已落地**：[pronoun.py](../../engine/src/xkx/runtime/pronoun.py)
   `build_context` + [title.py](../../engine/src/xkx/runtime/title.py) RANK_D 7 函数
   （[ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 已实现）。wield 单视角
   `return list[str]` 不直接消费 PronounContext，本批不涉及。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **message_vision 3 视角分发后置**（[ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md)
  简化台账第 9 项）：wield_msg 不走 message_vision 三段视角，单视角 `return list[str]`，
  房间广播后置 M3。本批落地此简化（wield 是首个有 wield_msg 的装备命令）。
- **专家 6（范围纪律）**：本批严守"命令层接线"，不扩 ItemDef 加 wield_msg 字段、不实现
  message_vision 非 entity 适配、不做 reset_action 完整招式表，避免范围过载。

## 产出

- [commands.py](../../engine/src/xkx/runtime/commands.py)：`wield`/`unwield` 终端函数 +
  adapter + COMMAND_REGISTRY 注册。
- [cli.py](../../engine/src/xkx/cli.py) parse_and_run：wield/unwield 分支。
- [items.py](../../engine/src/xkx/runtime/items.py)：删 WeaponDef/SAMPLE_WEAPONS/get_weapon_def。
- [tests/test_items.py](../../engine/tests/test_items.py)：删 WeaponDef 测试段。
- [tests/test_wield_command.py](../../engine/tests/test_wield_command.py)：wield/unwield 命令测试。
- tests 2387 -> 增 wield 测试 - 删 WeaponDef 测试。

*最后更新：2026-07-16*
