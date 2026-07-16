# ADR-0060：门派武器数据填表的范围边界裁决

- 状态：Accepted
- 日期：2026-07-16
- 阶段：门派迁移批（武器数据提取）
- 关联：[ADR-0058](ADR-0058-item-catalog-transition-layer.md) §6（WeaponDef schema + 全量提取留门派批）/
  [ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 附录（方案 A 物品实体化留 M3）/
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 2（物品/消息架构）dissent（物品实体化时机/物品属性承接）/
  专家 3 承重论断 1（七步管线文本与副作用交织）/ 承重论断 2（PronounContext 携带 viewer）/
  专家 4 承重论断 2（三层粒度 Theme > Module Pack > UGC CPK）

## 背景

[ADR-0058](ADR-0058-item-catalog-transition-layer.md) §6 已建 `WeaponDef` schema
（[items.py](../../engine/src/xkx/runtime/items.py) L128，9 字段 item_id/name/damage/rigidity/
flag/skill_type/weight/value/material）+ `SAMPLE_WEAPONS` 2 个手填样例
（songshan-jian/shizi）+ `get_weapon_def`，并明确"全量武器数据提取（逐文件
`init_blade(N)`）是内容生产工作，留后续门派迁移批"。本 ADR 执行该预留项的**范围边界
裁决**--不是开工填数据，而是先裁决"填到哪、填什么、不填什么、怎么填"。

调研确认的事实（关键处已读文件核对行号）：

1. **`ItemDef` 比 `WeaponDef` 更完整**。[layer0.py](../../engine/src/xkx/dsl/layer0.py) L221
   的 `ItemDef` 已在 ADR-0058 §1 扩展全部武器字段：weight/value/rigidity/
   `weapon_prop: dict[str, int]` mapping/unit/long/material/flag/skill_type + 基础字段
   （id/name/aliases/消耗品/read_skill）。`WeaponDef`（items.py L128）只有标量 `damage`，
   **会丢 `weapon_prop` 的 speed/dodge 子键**（法轮 `set_amount` 动态写
   weapon_prop/damage|dodge|speed，见 [falun.c](../../clone/weapon/falun.c) L13-15）。
2. **数据流已打通**。`items.yaml` -> `load_items`（layer0.py L297）-> `ItemDef` ->
   `compile_item`（[ir.py](../../engine/src/xkx/dsl/ir.py) L32，`{"kind":"item",
   **item.model_dump()}`）-> IR -> cli.py 构 `item_registry` -> `Game.item_registry` ->
   [items.py](../../engine/src/xkx/runtime/items.py) 函数族（item_weight/item_query/
   item_move_to_room/item_set）。`ItemDef` 是这条链的**数据入口**，`WeaponDef` 不在链上
   （仅 `SAMPLE_WEAPONS` 独立 dict + `get_weapon_def`）。
3. **`init_*` 的 flag 合并语义因类型而异**（决策点 5 的关键依据，已逐文件核对）：
   - `init_sword`（[sword.c](../../inherit/weapon/sword.c) L17）：`set("flag", (int)flag | EDGED)`
     --第 2 参自动 `|EDGED(4)`。
   - `init_blade`（[blade.c](../../inherit/weapon/blade.c) L18）：同上，`|EDGED`。
   - `init_hammer`（[hammer.c](../../inherit/weapon/hammer.c) L17）：`set("flag", flag)`
     --**不自动合并**，直接用第 2 参。
   - `init_throwing`（[throwing.c](../../inherit/weapon/throwing.c) L14）：`set("flag", flag)`
     --**不自动合并**。
   - 即"sword/blade 自动 |EDGED"不是普适规则，其余类型逐个查 `inherit/weapon/<type>.c`
     的 `set("flag", ...)` 表达式才能确定默认合并位。
4. **flag 位掩码常量**（[weapon.h](../../include/weapon.h) L8-13）：TWO_HANDED=1/SECONDARY=2/
   EDGED=4/POINTED=8/LONG=16/SELF_ACTION=32。
5. **LPC 武器分布**：inherit/weapon 约 29 个类型父类 + clone/weapon 103 + clone/unique 24
   （F_UNIQUE）+ d/\<sect\>/obj 255。纯数据型 228（去重后约 120-150），带 do_cut 等自定义
   命令 29，hit_ob 特效 13，COMBINED_ITEM 堆叠 31。weapon_prop 子键分布：damage(76)/
   speed(6)/dodge(6)。
6. **wield_msg/unwield_msg**：125/131 武器有，含 `$N`/`$n` 代词变量 + ANSI 颜色码（如
   [yitian-jian.c](../../clone/weapon/yitian-jian.c) L21-23
   `HIG"...$N...$n...\n"NOR`）。`ItemDef`/`WeaponDef` 均未承接。
7. **em/ 与 emei/ 大量复制粘贴**（如 gangdao.c 完全相同），LPC 自身已有重复债。
8. **代表武器（实测 clone/weapon，以实际文件为准）**：
   - 倚天剑 [yitian-jian.c](../../clone/weapon/yitian-jian.c)：init_sword(150)，weight 4000，
     rigidity 2000，value 10000，material steel，有 wield_msg/unwield_msg/unequip_msg。
   - 血刀 [xuedao.c](../../clone/weapon/xuedao.c)：init_blade(100)，weight 7000，rigidity
     1000000，value 7000000，有 `do_lian` 命令（练功）+ wield_msg。
   - 玄铁重剑 [xuantie-jian.c](../../clone/weapon/xuantie-jian.c)：init_sword(280)，weight
     20000，rigidity 200，有 `do_lian` 命令。
   - 法轮 [falun.c](../../clone/weapon/falun.c)：COMBINED_ITEM + init_hammer(25)，base_weight
     6000，`set_amount(v)` 动态写 weapon_prop/damage=v\*base_weapon、dodge=v\*base_dodge、
     speed=v\*base_speed、rigidity=v\*base_rigidity，wield 前置检查 riyue-lun/hammer 技能 +
     str + longxiang-banruo。

## 决策

本 ADR 裁决门派武器数据填表的 6 个范围边界。核心立场：**延续 ADR-0058 方案 B（台账
+ 函数族），数据统一进 `ItemDef` YAML，本批只做纯数据填表，命令/特效/堆叠按维度拆分
后置**。不引入物品实体化（方案 A 留 M3），不扩 `item_set` 写副作用。

### 1. 数据填 `ItemDef` 而非 `WeaponDef`（单台账原则）

**推荐：全量武器数据填 `ItemDef`（items.yaml），`WeaponDef` 降级为 deprecated。**

理由：

- `ItemDef` 字段更完整：`weapon_prop: dict[str, int]` mapping 承接 damage/speed/dodge
  全部子键（法轮三子键都能进），且有 `unit`/`long`/`aliases`。`WeaponDef` 的标量 `damage`
  会丢 speed/dodge 子键，是错误建模。
- `ItemDef` 是数据流入口（items.yaml -> load_items -> compile_item -> item_registry ->
  items.py 函数族），[ADR-0058](ADR-0058-item-catalog-transition-layer.md) §1 单台账原则已确立
  `item_registry` 为唯一台账。`WeaponDef`/`SAMPLE_WEAPONS` 是链外的第二套数据源，维护两套
  schema 同步得不偿失。
- damage 进 `ItemDef.weapon_prop.damage`（对齐 LPC `set("weapon_prop/damage", N)`，init_*
  L16 实证），不是标量字段。

`WeaponDef` 处置：**本批不删除**（避免破坏 `SAMPLE_WEAPONS`/`get_weapon_def` 现有引用，
且本 ADR 只裁决范围不改代码），但标注 deprecated--全量武器数据不再由 `WeaponDef`/
`SAMPLE_WEAPONS` 承载。`WeaponDef` 标量 `damage` 模型错误（丢 mapping 子键），wield 命令批
再定夺：若需强类型武器视图则从 `ItemDef` 台账投影重构（而非保留标量 damage 的
`WeaponDef`），否则彻底删除。届时 `SAMPLE_WEAPONS` 2 个样例迁为 `ItemDef` YAML 条目。

### 2. 去重策略：通用武器进公共 CPK，门派专属进门派 CPK

**推荐：共享通用武器（钢刀/长剑等多门派/区域引用的）放公共 CPK（如 common/items.yaml），
门派专属武器（倚天剑/血刀等）放门派 CPK。**

判定规则：

- 武器在 LPC 里被多个门派/区域 `clone_ob` 引用，或为通用基础武器 -> 公共 CPK。
- 武器只被单一门派引用、带门派专属设定 -> 门派 CPK。

理由：

- 去重避免维护负担（LPC em/ 与 emei/ 已有复制粘贴债，gangdao.c 完全相同；greenfield
  不得继承该债）。
- 对齐三层粒度 Theme > Module Pack > UGC CPK（[05](../xkx-arch/05-第三轮专家对抗复审报告.md)
  专家 4 承重论断 2：门派是 wuxia 题材下的 module pack 不是独立题材）。通用武器不属任何
  门派，归公共层；门派专属归门派 module pack。
- 权威源选取：同一武器在 clone/weapon、clone/unique、d/\<sect\>/obj 多处出现时（如
  yitian-jian），取 clone/weapon 为定义权威源，d/\<sect\>/obj 作门派引用记录（标注引用
  关系，不重复填数据）。

跨 CPK 去重靠公共层抽取；同一 CPK 内若仍有重复（如门派内多个变体），保持 YAML 平铺
可读性，靠人工校验，不引入跨文件 YAML anchor。

### 3. wield_msg/unwield_msg：留 wield 命令批

**推荐：本批不扩 `ItemDef` 承接 wield_msg/unwield_msg，留 wield 命令批统一处理。**

理由：

- wield_msg 含 `$N`/`$n` 代词变量 + ANSI 颜色码（yitian-jian.c L21 实证
  `HIG"...$N...$n...\n"NOR`）。代词求值依赖 PronounContext 三元组（speaker/viewer/
  target，[05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 3 承重论断 2 实证 `this_player()`
  依赖），与 wield 命令上下文强耦合。
- 本批聚焦**标量数值 + weapon_prop mapping**（damage/rigidity/weight/value/material/
  flag/skill_type/weapon_prop），wield_msg 是表现层文本，职责不同。混入会模糊数据批与
  命令批边界，且 `ItemDef` schema 过早膨胀（收缩原则，[05](../xkx-arch/05-第三轮专家对抗复审报告.md)
  专家 6 范围纪律）。
- wield_msg/unwield_msg/unequip_msg 连同代词渲染在 wield 命令批承接，那时 PronounContext
  + 消息渲染管线就绪。

折中（避免二次翻 LPC）：脚本提取阶段（决策 6）顺带把 wield_msg/unwield_msg 原文 dump 到
中间产物（非 `ItemDef` schema），wield 批承接时直接取用，不重新遍历 228 个文件。

### 4. 范围与结构差异分类：按维度拆分，不按文件整体推迟

**推荐：按"纯数据 / 自定义命令 / hit_ob 特效 / COMBINED_ITEM 堆叠"四维拆分，混合型武器
按维度各归其批。**

| 分类 | 数量 | 归属批次 | 理由 |
|---|---|---|---|
| 纯数据填表 | 228（去重约 120-150） | **本批** | create() 仅 set_*/init_*/set_name/set_weight + 静态标量/weapon_prop |
| do_cut/do_lian 等自定义命令 | 29 | 命令迁移批 | do_cut 击碎改名涉及 per-instance set（ADR-0058 §5 `item_set` no-op 限制），归 wield/do_cut 命令批 |
| hit_ob 特效 | 13 | M3 combat 招式表 | hit_ob 是 do_attack 七步管线钩子，文本与副作用交织不可分离（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 3 承重论断 1） |
| COMBINED_ITEM 堆叠 | 31 | 方案 A（M3 物品实体化） | `set_amount` 动态写 weapon_prop/rigidity，per-instance 动态属性需 ItemComp 承接（ADR-0056 附录） |

关键裁决：**按维度拆分而非按文件整体推迟**。混合型武器（如血刀=纯数据+`do_lian`、
玄铁重剑=纯数据+`do_lian`）的**纯数据部分本批提取填 `ItemDef`**，`do_lian` 命令部分留
命令批。本批对带命令/特效/堆叠的武器产出的是"不完整定义"（缺命令行为/特效/堆叠语义），
须在数据或旁注标注缺口（哪些维度后置、归哪个批次），避免后续误判为完整。

本批 `ItemDef` 覆盖范围：228 个纯数据武器的 create() 标量数值 + 静态 weapon_prop mapping
（非 `set_amount` 动态）。法轮等 COMBINED_ITEM 的**静态 base_\* 定义**（base_weapon=25 等）
可顺带记录到中间产物供方案 A 批取用，但不进本批 `ItemDef`（无 set_amount 语义无法表达
动态 weapon_prop）。

### 5. flag 位掩码合并语义：逐类型确认默认合并位

**推荐：最终 flag = `flag_arg | <type 默认合并位>`，默认合并位因 init_\<type\> 而异，逐类型查
`inherit/weapon/<type>.c` 的 `set("flag", ...)` 表达式确认。**

提取规则：

1. 解析 `init_<type>(damage, flag_arg?)` 调用：第 1 参 damage -> `weapon_prop.damage`；
   第 2 参 flag_arg（varargs 可缺省，缺省=0）。
2. 默认合并位（已核对）：
   - init_sword / init_blade：`|EDGED(4)`（sword.c L17 / blade.c L18 实证
     `set("flag", (int)flag | EDGED)`）。
   - init_hammer / init_throwing：**不合并**（hammer.c L17 / throwing.c L14 实证
     `set("flag", flag)`）。
   - 其余 init_*（axe/dagger/fork/pike/staff/club/stick/whip/hook/bow 等）：逐个查
     `inherit/weapon/<type>.c` 的 `set("flag", ...)` 表达式，脚本提取时建一张
     `<type> -> 默认合并位` 映射表。
3. 若 create() 在 init_* 之后有显式 `set("flag", X)`：以**最终值**为准（LPC `set` 是覆盖
   语义）。但 set 表达式可能是赋值/`|`/`&`，脚本标注需人工校验。
4. varargs 缺省：`init_sword(150)` 不传 flag -> flag_arg=0 -> 最终 flag = 0|EDGED = 4
   （倚天剑实证：init_sword(150) -> flag=4）。
5. **人工校验**：flag 提取易错（varargs 缺省 + 多处 set 混合 + 类型差异），脚本生成草表
   后必须人工核对位掩码，对照 weapon.h 常量。

### 6. 数据填表方式：脚本辅助半自动

**推荐：tools/ 脚本（grep/正则）提取 create() 的 set_*/init_* -> YAML 草表 + 人工校验。**

- 脚本提取：set_name/set_weight/set("value")/set("rigidity")/set("material")/set("unit")/
  set("long")/init_*(damage, flag) -> 生成 `ItemDef` YAML 草表（含 weapon_prop mapping）。
- 脚本识别并标注后置（不强行提取）：带 `do_cut`/`do_lian`/`hit_ob`/`COMBINED_ITEM` 的武器
  打标，按决策 4 归对应批次。
- 人工校验重点：flag 位掩码（决策 5）、weapon_prop 子键完整性、去重（em/emei 复制粘贴）、
  COMBINED_ITEM 动态属性识别跳过、long 文本的 ANSI 颜色码与转义。
- 顺带 dump：wield_msg/unwield_msg 原文（决策 3）、COMBINED_ITEM 的 base_\* 静态定义
  （决策 4）到中间产物，供后续批次取用，避免二次翻 LPC。
- 工具落点：仓库根 justfile 的 tools recipe（`uv run` 自带 cd）。

## 不做（收敛，留后续批次）

- **ItemComp 物品实体化（方案 A）**：本批只做方案 B 台账填表，不引入 ECS 实体/Position
  组件/per-instance 状态。留 M3（ADR-0056 附录）。
- **`item_set` 写副作用 per-instance 实现**：维持 ADR-0058 §5 no-op 现状。do_cut 击碎改名
  等留命令批（届时 per-instance 语义由方案 A 承接，或命令批内局部适配）。
- **wield_msg/unwield_msg 承接**：留 wield 命令批（决策 3）。
- **hit_ob 特效**：13 个留 M3 combat 招式表（七步管线）。
- **COMBINED_ITEM 堆叠**：31 个留方案 A M3（set_amount 动态属性）。
- **WeaponDef 删除**：本批只标 deprecated，不删代码（避免破坏现有引用，wield 批定夺去留）。
- **str item_id 模型不变**：不做物品实体化，`Inventory.items`/`Equipment.weapon` 仍是
  `str item_id`（延续 ADR-0058 不变量 4）。

## 不变量约束

1. **单台账**：武器数据填 `ItemDef` YAML（item_registry 唯一台账），不重建 `WeaponDef`/
   `SAMPLE_WEAPONS` 第二套数据源（延续 ADR-0058 §1）。
2. **damage 走 weapon_prop mapping**：填 `weapon_prop.damage`（对齐 LPC
   `set("weapon_prop/damage", N)`），不是标量字段。speed/dodge 子键照填（承接法轮等）。
   --`WeaponDef` 标量 damage 违反此不变量，故降级。
3. **物品 weight 不走 dbase key "weight"**：物品 weight 是台账字段，非角色级
   `Equipment.encumbrance`（延续 ADR-0058 不变量 1）。
4. **按维度拆分**：混合型武器的纯数据部分本批提取，命令/特效/堆叠各归其批，标注缺口。
5. **flag 逐类型确认合并位**：不得假设所有 init_* 都 `|EDGED`（hammer/throwing 不合并）。
6. **str item_id 模型不变**：不引入物品实体化（延续 ADR-0058 不变量 4）。
7. **不破坏现有 drink/take/give/`_item_name` 读 item_registry 的命令**：新 `ItemDef` 武器
   条目带默认值，向后兼容（延续 ADR-0058 不变量 5）。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **专家 2（物品/消息架构）dissent--物品实体化时机/物品属性承接**：本 ADR 延续 ADR-0058
  的方案 B 过渡裁决并细化范围。**实体化时机**：本批确认方案 A 物品实体化留 M3--COMBINED_ITEM
  31 个的 per-instance 动态属性（set_amount 写 weapon_prop/rigidity）需 ItemComp 承接，
  hit_ob 13 个需七步管线承接，本批只做纯数据台账，不引入 ItemComp。**物品属性承接**：本批
  用 `ItemDef.weapon_prop` mapping 承接 damage/speed/dodge 全部子键，修复 `WeaponDef` 标量
  damage 丢子键的缺陷；wield_msg/unwield_msg 表现层文本留 wield 命令批（代词求值依赖
  PronounContext 三元组）。属性承接按"数据层（本批）vs 表现层（wield 批）vs 动态实体层
  （M3 方案 A）"分批，避免一次性膨胀，与专家 2 对"先让样本不卡、实体化等 M3 统一落地"的
  主张一致。
- **专家 3 承重论断 1（七步管线文本与副作用交织不可分离）**：本批据此把 hit_ob 13 个后置
  M3 combat 招式表，不试图把 hit_ob 特效压进纯数据台账（会割裂文本与副作用）。
- **专家 3 承重论断 2（PronounContext 携带 viewer）**：本批据此把 wield_msg/unwield_msg
  留 wield 命令批（代词 `$N`/`$n` 求值依赖 viewer），本批不承接表现层文本。
- **专家 4 承重论断 2（三层粒度 Theme > Module Pack > UGC CPK）**：本批去重策略据此把通用
  武器归公共 CPK、门派专属归门派 module pack，不把门派当独立题材。
- **专家 6（范围纪律）**：本批范围严守"纯数据填表"，命令/特效/堆叠全部后置，不扩 schema
  承接表现层文本，避免范围过载。
