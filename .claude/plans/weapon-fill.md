# 门派武器数据填表（ADR-0060 落地）

> 阶段：门派迁移批（武器数据）。关联 [ADR-0060](../../docs/adr/ADR-0060-weapon-data-extraction-scope.md)。
> 状态：plan，待批准后执行。

## 目标

把 `weapon_extract.py` 提取的 267 武器草表（`/tmp/weapons_all.yaml`，session 内可重跑生成）
落地为可被 `load_items` / `compile_scene` 加载编译的 `ItemDef` YAML，行为等价于 LPC
`create()` 的标量数值 + 静态 `weapon_prop` mapping。这是 ADR-0060 决策 6 的"脚本辅助半自动
填表"收尾，**纯数据层**，不含命令/特效/堆叠/wield_msg。

## 已确认事实（决策依据，已读文件核对）

1. **草表规模**：267 记录 -> 权威源去重后 **152 唯一 id**（115 重复折叠）；其中 19 后置混合型
   + 133 纯数据。60 个 id 跨目录重复。
2. **来源分布**：clone/weapon 90（权威）+ clone/unique 21（F_UNIQUE 名器）+ d/*/obj 156。
   em(10) vs emei(10) 印证 ADR-0060 点名的复制债（zhujian/zhudao/yitian-jian 等完全相同）。
3. **后置 19 个维度**（去重后唯一）：自定义命令 ~9（血刀/玄铁剑/eyujian/yangdao/youlong/
   yuandao/zhenwu/taomu/djdao）+ hit_ob ~7（qijue/chain/dulong-bian/taomu-jian/taomujian/
   dushi/xianglu-dao）+ COMBINED_ITEM 4（falun/falun5/shizi/shizi2）。
4. **ItemDef schema 匹配**：[layer0.py:221](../../engine/src/xkx/dsl/layer0.py#L221) 字段
   id/name/aliases/skill_type/weapon_prop/flag/weight/value/rigidity/material/unit/long 与草表
   对齐。草表元字段 `_path`/`_postpone`/`_flag_unknown` 需去除（不进 schema）。
5. **加载链就绪**：items.yaml -> `load_items`（layer0.py:297）-> ItemDef -> `compile_item`
   （ir.py:32 `{"kind":"item",**model_dump()}`）-> `compile_scene` ir["items"] -> cli.py
   `item_registry={i["id"]:i for i in ir["items"]}` -> Game.item_registry。
6. **cli.py 只加载单 scene CPK，无跨 CPK 合并**（[cli.py:116](../../engine/src/xkx/cli.py#L116)）：
   `load_cpk(SCENES_DIR/scene)` 一次一个目录，无公共层/多 CPK 合并机制。
7. **无公共层 CPK 概念**：grep cpk.py/orchestrator 无 common/public/shared。现有 5 个
   scenes/*_micro 都是独立完整 CPK（含 manifest+rooms+npcs），wuxia_micro 无 items.yaml。
8. **WeaponDef 是链外第二套数据源**：[items.py:128](../../engine/src/xkx/runtime/items.py#L128)
   `WeaponDef` + `SAMPLE_WEAPONS` 2 样例 + `get_weapon_def`，不在 items.yaml->load_items 链上。
   标量 `damage` 丢 weapon_prop 子键（ADR-0060 决策 1 已定降级）。

## 裁定方案

### 落点：纯数据资产文件，按公共/门派物理拆分，不接 cli.py

**新建 `engine/scenes/wuxia_weapons/`**（纯数据资产目录，**非正式 CPK**，无 manifest）：

- `common.yaml`：公共通用武器。权威源是 clone/weapon 或 clone/unique 的全部 + 多门派引用
  的 d/*/obj 通用武器（钢刀 gangdao/长剑 changjian/竹剑 zhujian 等被 4-7 门派引用的）。
- `sect/<sect>.yaml`：门派专属武器。权威源是 d/\<sect\>/obj 且该 id 仅单门派出现的
  （如 d/dali/obj chain、d/xingxiu/obj dushi 等门派独有）。

**不改 cli.py / 不建公共层加载机制**：cli.py 当前只加载单 scene CPK。本批是 ADR-0060
纯数据填表，同步建"公共武器 CPK 合并进 game.item_registry"会引入跨 CPK 合并基础设施，
超 ADR-0060 范围 + 违反收缩原则（六条约束：收敛优先于完备）。正式 CPK 化（公共/门派 CPK
目录 + manifest + cli.py 多 CPK 合并）**后置 ADR-0062**。

`load_items` 测试直接加载这些 YAML 验证 schema + compile_scene，不经 cli.py。

### 范围：按维度拆分，约 148 条进 ItemDef

按 ADR-0060 决策 4"按维度拆分而非按文件整体推迟"：

| 类别 | 数量 | 本批处理 | 缺口标注 |
|---|---|---|---|
| 纯数据 | 133 | 全填 | 无 |
| 自定义命令（do_lian/do_cut） | ~9 | 纯数据填 | 命令行为留命令批 |
| hit_ob 特效 | ~7 | 纯数据填 | hit_ob 留 M3 招式表 |
| COMBINED_ITEM 堆叠 | 4 | **不进本批** | 整体留方案 A M3 |

- COMBINED_ITEM（falun/falun5/shizi/shizi2）：ADR-0060 决策 4 明确"法轮等不进本批 ItemDef
  （无 set_amount 语义无法表达动态 weapon_prop）"。整体跳过，仅记录到中间产物清单。
- 混合型条目（自定义命令/hit_ob 类）的**纯数据部分本批填**（damage/weight/flag/skill_type/
  rigidity/value/material/unit/long），在该条目 YAML 注释标缺口（哪些维度后置、归哪个批次），
  避免后续误判为完整定义（ADR-0060 决策 4 关键裁决）。

### 去重：权威源规则 + em 折叠

- 权威源优先级：clone/weapon > clone/unique > d/*/obj。同一 id 多处出现取最高优先级源
  （如 yitian-jian 取 clone/weapon，d/em、d/emei 作引用记录不重复填）。
- em/emei 折叠：两者完全复制的武器取 emei 为权威，em 作复制债丢弃（不重复落表）。
- 别名 aliases 去重：同一武器多个来源的 aliases 合并去重。

### WeaponDef 降级：标 deprecated，不删代码

[items.py](../../engine/src/xkx/runtime/items.py) `WeaponDef`/`SAMPLE_WEAPONS`/`get_weapon_def`
加 `# DEPRECATED（ADR-0060 决策 1）：全量武器数据改由 ItemDef YAML 台账承载，本 schema
标量 damage 丢 weapon_prop 子键，wield 命令批定夺去留` 注释。**不删代码**（避免破坏
SAMPLE_WEAPONS 现有引用 + 本批只裁决范围不改机制，ADR-0060 决策 1 明确）。

## 执行步骤

1. **写 `engine/tools/weapon_finalize.py`**：读草表 `/tmp/weapons_all.yaml`（或重跑
   `weapon_extract.py` 生成）-> 去元字段（_path/_postpone/_flag_unknown）-> 权威源去重
   -> 自动分类公共/门派（clone/* 或多门派引用 -> common；d/\<sect\> 单门派 -> sect/\<sect\>）
   -> 跳过 COMBINED_ITEM -> 混合型条目加缺口注释 -> 产出 `scenes/wuxia_weapons/common.yaml`
   + `sect/<sect>.yaml`。复用 yaml.safe_dump 保留可读性。
2. **人工抽样校验**（ADR-0060 决策 5/6 人工校验重点）：
   - flag 位掩码：倚天剑 init_sword(150) -> flag=4（EDGED）、血刀 init_blade(100) -> flag=4、
     法轮跳过、throwing/hammer flag=0（不合并）。
   - weapon_prop 子键：damage 进 mapping（非标量）。
   - long 文本：ANSI 颜色码已 strip、多行 \n 保留。
   - em/emei 折叠正确性：emei 保留、em 丢弃。
3. **新建 `engine/tests/test_weapons_catalog.py`**：
   - `load_items` 加载 common.yaml + 每个 sect/*.yaml -> ItemDef schema 全通过（pydantic 不抛）。
   - `compile_scene([], [], [], items)` 编译 -> ir["items"] 条目数 == 输入。
   - 代表武器行为断言：倚天剑 flag=4/weapon_prop.damage=150/weight=4000/material=steel；
     血刀 flag=4/damage=100；通用钢刀 gangdao 存在公共层；门派专属在对应 sect 文件。
   - 不接 cli.py（接线后置）。
4. **items.py WeaponDef/SAMPLE_WEAPONS/get_weapon_def 加 deprecated 注释**。
5. **justfile 加 `weapons-load` recipe**（可选）：`cd engine && uv run python tools/weapon_finalize.py`。
6. **`just test` + `just lint` 全绿**。
7. **更新 PROGRESS.md**：In Progress -> Done + 日期 + tests 数。
8. **写 ADR-0062**：记录"武器数据落纯资产文件非正式 CPK + cli.py 接线后置"偏离 ADR-0060
   决策 2 的裁决（决策 2 目标是公共/门派 CPK 切分，但当前无公共层加载机制，本批纯数据填表
   不同步建基础设施），关联 05 专家 4 三层粒度 + 专家 6 范围纪律。

## 测试策略

- **schema 校验**：所有 148 条 ItemDef 经 `ItemDef(**dict)` 不抛 ValidationError。
- **编译校验**：`compile_scene` 产出 ir["items"] 含全部条目，每条 `kind=="item"`。
- **行为断言**：代表武器字段值与 LPC 源文件核对（倚天剑/血刀/通用钢刀/门派专属各抽 1-2）。
- **去重断言**：common + sect 全部 id 唯一无重复；em 武器不出现（折叠到 emei）。
- **缺口标注断言**：混合型条目存在后置注释（19 个里进的 ~16 个有注释）。

## 不做（收敛，留后续批次）

- 不接 cli.py（CPK 接线后置 ADR-0062）。
- 不建公共层 CPK 加载 / 跨 CPK 合并机制。
- 不删 WeaponDef 代码（标 deprecated，wield 批定夺）。
- 不填 COMBINED_ITEM 4 个（留方案 A M3，set_amount 动态属性）。
- 不填 wield_msg/unwield_msg（决策 3 留 wield 命令批）。
- 不填 hit_ob 特效行为（留 M3 招式表，纯数据部分填）。
- 不填 do_cut/do_lian 命令行为（留命令批，纯数据部分填）。
- 不做物品实体化（方案 A 留 M3）。
- 不扩 item_set 写副作用（维持 ADR-0058 §5 no-op）。

## 风险与校验

- **flag 位掩码易错**：脚本已确认 14 类型合并位（FLAG_MERGE），flag 未确认 0 个。仍需人工
  抽样核对 varargs 缺省（init_sword(150) -> flag=4）+ 多处 set 混合。
- **long 文本颜色码/转义**：草表 long 经 `_strip_ansi_macros` 去 ANSI，多行 \n 保留。人工
  抽查 fumo-dao 等多行 long。
- **分类误判**：自动分类"多门派引用 -> 公共"可能把个别门派专属误归公共。人工抽查边界
  case（如某武器仅在 2 门派出现但实为门派专属）。分类只影响文件归属，不影响数据正确性。
- **去重遗漏**：em/emei 折叠靠文件名规则，若 em 有 emei 没的独有武器需保留。脚本产出后
  人工对账 em vs emei 文件清单。

## 交付物

- `engine/scenes/wuxia_weapons/common.yaml` + `sect/<sect>.yaml`（~148 条 ItemDef）。
- `engine/tools/weapon_finalize.py`（草表 -> 去重分类 -> YAML）。
- `engine/tests/test_weapons_catalog.py`（load_items + compile_scene + 行为断言）。
- `engine/src/xkx/runtime/items.py` WeaponDef deprecated 注释。
- justfile `weapons-load` recipe（可选）。
- ADR-0062（CPK 接线后置裁决）。
- PROGRESS.md 更新。
- 预期 tests 2371 -> ~2420+。
