# ADR-0062：门派武器数据落纯资产文件、CPK 接线后置

- 状态：Accepted
- 日期：2026-07-16
- 阶段：门派迁移批（武器数据填表）
- 关联：[ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 决策 2（公共/门派 CPK 切分目标）/
  [ADR-0058](ADR-0058-item-catalog-transition-layer.md)（ItemCatalog 单台账）/
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 4 承重论断 2（三层粒度）/
  专家 6（范围纪律）

## 背景

[ADR-0060](ADR-0060-weapon-data-extraction-scope.md) 决策 2 裁定"通用武器放公共 CPK
（如 common/items.yaml），门派专属放门派 CPK"，对齐三层粒度 Theme > Module Pack > UGC CPK。
本批执行 ADR-0060 决策 6 的脚本辅助半自动填表时，确认一个实施约束：

**当前引擎无公共层 CPK 加载机制**。[cli.py:116](../../engine/src/xkx/cli.py#L116) 的
`load_cpk(SCENES_DIR / scene)` 一次加载单个 scene CPK 目录，
`item_registry = {i["id"]: i for i in ir["items"]}` 只取该单 CPK 的 items，
**无跨 CPK 合并 / 公共层注入**。[cpk_loader.py](../../engine/src/xkx/dsl/cpk_loader.py)
的 `load_cpk` 同理一次一目录。grep cpk.py / orchestrator 无 common / public / shared
公共层概念。现有 5 个 scenes/*_micro 都是独立完整 CPK（manifest + rooms + npcs + ...），
各自封闭。

若本批严格按 ADR-0060 决策 2 拆"公共武器 CPK + 各门派 CPK"并接入 game.item_registry，
须同步新建：(a) 公共层 CPK 目录 + manifest + ThemeRegistry 公共层注册；(b) cli.py 多 CPK
合并（公共层 items 注入每个 scene 的 item_registry）；(c) 门派 CPK 目录 + manifest。这是
CPK 加载基础设施工作，**超出 ADR-0060"纯数据填表"范围**（决策 6 + 收敛原则），且与 wield
命令批 / 门派 CPK 正式化等后续批次的工作重叠。

## 决策

**本批武器数据落"纯数据资产文件"，按公共/门派物理拆分体现决策 2 组织意图，但不建 manifest、
不接 cli.py。正式 CPK 化（公共/门派 CPK 目录 + manifest + cli.py 多 CPK 合并）后置。**

### 1. 落点：scenes/wuxia_weapons/ 纯资产目录（非正式 CPK）

- `common.yaml`：公共通用武器（权威源 clone/weapon + clone/unique + 多门派引用的通用武器）。
- `sect/<sect>.yaml`：门派专属武器（权威源 d/\<sect\>/obj 且单门派引用）。
- **无 manifest.yaml**：非正式 CPK，不经 `load_cpk` 加载、不进 ThemeRegistry。
- **不接 cli.py**：`load_items` 直接加载这些 YAML 验证 schema + `compile_scene` 编译，
  不进 game.item_registry（cli.py 接线后置）。
- 物理拆分已体现 ADR-0060 决策 2 的公共/门派组织意图（通用 vs 门派专属分文件），未来正式
  CPK 化时文件直接搬入对应 CPK 目录，无需重新拆分。

### 2. CPK 接线后置：待门派 CPK 正式化批

正式 CPK 化（含 cli.py 多 CPK 合并 + 公共层注入 + ThemeRegistry 公共层注册）后置到
"门派 CPK 正式化"批次统一落地，不在本批引入。后置触发条件：wield 命令批或门派迁移批需要
game.item_registry 含全量武器数据时。届时：

- `scenes/wuxia_weapons/{common,sect/*}.yaml` 搬入 `scenes/wuxia_common/` +
  `scenes/wuxia_<sect>/` 正式 CPK 目录，补 manifest。
- cli.py 扩展支持加载公共层 CPK + 合并进每个 scene 的 item_registry（或 Game 构造时合并）。
- ThemeRegistry 扩展公共层 module pack 注册。

### 3. 后置缺口标注（延续 ADR-0060 决策 4）

混合型武器（自定义命令 do_lian/do_cut、hit_ob 特效）的纯数据部分本批填，条目前 `# 后置缺口`
注释标维度归属。COMBINED_ITEM（falun/shizi/shizi2）整体不进本批（决策 4 留方案 A）。

## 不做（收敛）

- 不建公共层 CPK 加载机制 / ThemeRegistry 公共层注册（后置）。
- 不改 cli.py 多 CPK 合并（后置）。
- 不建门派 CPK 目录 + manifest（后置）。
- 不删 WeaponDef / SAMPLE_WEAPONS（ADR-0060 决策 1，标 deprecated，wield 批定夺）。
- 不填 COMBINED_ITEM 3 个（falun/shizi/shizi2，留方案 A M3）。
- 不填 wield_msg / hit_ob 行为 / do_cut/do_lian 命令（各归其批，纯数据部分已填）。

## 不变量约束

1. **单台账**：武器数据填 ItemDef YAML（item_registry 唯一台账目标），不重建第二套数据源
   （延续 ADR-0058 §1 / ADR-0060 决策 1）。本批 YAML 是台账的数据源，正式 CPK 化后直接接入。
2. **damage 走 weapon_prop mapping**：填 weapon_prop.damage（非标量），speed/dodge 照填
   （延续 ADR-0060 不变量 2）。
3. **str item_id 模型不变**：不引入物品实体化（延续 ADR-0058 不变量 4 / ADR-0060 不变量 6）。
4. **物理拆分即组织**：common vs sect 文件归属已对齐决策 2 公共/门派切分，正式 CPK 化只搬目录
   不重拆。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **专家 4 承重论断 2（三层粒度 Theme > Module Pack > UGC CPK）**：本批物理拆分 common（公共）
  vs sect（门派专属）已体现三层粒度组织意图（通用武器归公共层、门派专属归门派 module pack）。
  正式 CPK 化后置不违反此论断--本批落地了数据与组织，CPK 加载基础设施是工程接线非架构决策，
  待门派 CPK 正式化批统一接入。
- **专家 6（范围纪律）**：本批严守"纯数据填表"，不同步建 CPK 加载基础设施（公共层注入 /
  cli.py 多 CPK 合并 / ThemeRegistry 注册），避免范围过载。数据与接线解耦，各自归批。

## 产出

- [scenes/wuxia_weapons/common.yaml](../../engine/scenes/wuxia_weapons/common.yaml)（98 条公共武器）。
- [scenes/wuxia_weapons/sect/](../../engine/scenes/wuxia_weapons/sect/)（16 门派 51 条）。
- [tools/weapon_finalize.py](../../engine/tools/weapon_finalize.py)（草表 -> 去重分类）。
- [tests/test_weapons_catalog.py](../../engine/tests/test_weapons_catalog.py)（12 tests）。
- [items.py](../../engine/src/xkx/runtime/items.py) WeaponDef 标 deprecated。
- justfile `weapons-load` recipe。
- tests 2371 -> 2383。
