# ADR-0062 武器 CPK 接线实施计划

> 执行 [ADR-0062](docs/adr/ADR-0062-weapon-cpk-wiring-postpone.md) 决策 2（CPK 接线）。
> 上批已落 149 条武器 ItemDef 到 `scenes/wuxia_weapons/`（纯资产，无 manifest，未接 cli）。
> 本批正式 CPK 化 + 接入 `game.item_registry`，为 wield 命令批铺路。

## 目标

`cli.py load_game` 加载任意 wuxia scene 后，`game.item_registry` 含全量 149 武器
（公共 98 + 门派 51），供下批 wield 命令消费。**本批只接数据，不实现 wield。**

## 范围与边界（严守 ADR-0062 §不做）

**做**：17 个数据层 CPK 目录 + manifest、cli.py glob 合并、测试演进、删除旧目录。
**不做**：不删 `WeaponDef`/`SAMPLE_WEAPONS`（deprecated，wield 批定夺）；不碰
COMBINED_ITEM 3 个（falun/shizi/shizi2）；不实现 wield/wield_msg/hit_ob/do_cut/do_lian
（各归其批，纯数据已填）；不改 ThemeRegistry（glob 方案不需要）。

## 实施

### 1. 正式 CPK 化：17 个数据层目录

把 `scenes/wuxia_weapons/` 的 yaml 搬入（**搬移非复制**，搬完删旧目录）：

- `scenes/wuxia_common/`：`manifest.yaml` + `items.yaml`（← `common.yaml`，98 条）
- `scenes/wuxia_<sect>/` × 16：各 `manifest.yaml` + `items.yaml`（← `sect/<sect>.yaml`）

16 门派（从现有 `sect/` 确认）：beijing changbai city dali emei gaibang jiaxing
kunlun qilian shenlong taihu taohua village xiakedao xingxiu zhongnan。

**manifest 模板**（数据层，无 entry_points — 这是区分场景 CPK vs 数据层 CPK 的约定）：

```yaml
# CPK manifest（ADR-0062 武器数据层）：武侠公共武器 StdLib 数据层 CPK
# 纯物品台账，无 rooms/entry_points；cli.py 按题材前缀 glob 发现，合并进 item_registry。
cpk_id: wuxia_common   # 门派: wuxia_<sect>
schema_version: 1
theme: wuxia
pack_type: module_pack
version: 0.1.0
license: CC-BY-SA-4.0
author: xkx-core
dependencies: []
capabilities_required: []
# 无 entry_points（数据层，非场景）
```

`items.yaml` 内容 = 原 yaml 原样搬（含头部 `# 后置缺口` 注释与条目）。

**可行性已验证**：`load_cpk` 的 `items.yaml` 可选、`compile_scene([],[],[],items)`
处理空 rooms、`_validate_manifest` 在 `entry_points` 为空时跳过 room 校验、
`theme: wuxia` 已在 `default_registry` 注册。

### 2. cli.py glob 合并（[cli.py:116-123](engine/src/xkx/cli.py#L116-L123)）

新增辅助函数 + 在 `load_game` 合并 item_registry：

```python
def _load_theme_data_items(theme: str, registry: ThemeRegistry) -> list[dict]:
    """加载题材数据层 CPK 物品（ADR-0062 接线）。

    glob scenes/<theme>_*/ 目录，预读 manifest：entry_points 为空的是数据层 CPK
    （纯物品台账），load_cpk 合并其 ir["items"]。有 entry_points 的场景 CPK
    （如 wuxia_micro）跳过。非武侠题材（default）无匹配目录返回空。
    """
    import yaml
    from xkx.dsl.cpk import CpkManifest

    items: list[dict] = []
    for cpk_dir in sorted(SCENES_DIR.glob(f"{theme}_*/")):
        mpath = cpk_dir / "manifest.yaml"
        if not mpath.exists():
            continue
        m = CpkManifest.model_validate(yaml.safe_load(mpath.read_text(encoding="utf-8")))
        if m.entry_points:  # 场景 CPK 跳过
            continue
        _, ir, _, _ = load_cpk(cpk_dir, registry=registry)
        items += ir.get("items", [])
    return items
```

`load_game` 内（取 manifest.theme 后）：

```python
# ADR-0062 接线：合并题材数据层 CPK 物品（wuxia_common + 16 门派武器 = 149）
data_items = _load_theme_data_items(manifest.theme, registry)
item_registry = {i["id"]: i for i in ir.get("items", []) + data_items}
```

`ThemeRegistry` 类型注解需 import（TYPE_CHECKING 或运行时）。cli.py 顶部已有
`from xkx.themes import default_registry`；`ThemeRegistry` 类型走 TYPE_CHECKING。

### 3. 删除旧 `scenes/wuxia_weapons/` + 更新引用

- 搬移后 `git rm -r scenes/wuxia_weapons/`（或搬完目录自然消失）。
- [weapon_finalize.py](engine/tools/weapon_finalize.py)：`_DEFAULT_OUT` 与
  `main()` 写出逻辑更新为写 `wuxia_common/items.yaml` + `wuxia_<sect>/items.yaml`
  （幂等刷 items.yaml，不碰 manifest—manifest 一次定稿手工维护）。`_HEADER` 注释
  更新路径。`just weapons-load` 仍可从 LPC 草表重建数据到正式 CPK 结构。
- [items.py:127](engine/src/xkx/runtime/items.py#L127) 注释路径 `wuxia_weapons` →
  `wuxia_common` + `wuxia_<sect>`。
- [justfile](justfile) `weapons-load` recipe 不变（仍跑脚本）。

### 4. 测试演进

**[test_weapons_catalog.py](engine/tests/test_weapons_catalog.py)（12 tests）重构**：
`WEAPONS_DIR` 概念改为"遍历 wuxia_* 数据层 CPK"。仍测：load_items schema 校验、
compile_scene、id 唯一、代表武器断言（倚天剑/血刀/钢刀/em 折叠/羊鞭/damage 走
weapon_prop）、COMBINED_ITEM 跳过、各 CPK 至少 1 条。新增：每个 wuxia_* 目录
`load_cpk` 加载成功（manifest 校验 + 返回 items）。

**新增 cli 接线测试**（新文件或扩展现有 cli 测试）：
- `load_game("xueshan_micro")` 后 `game.item_registry` 含全量武器（>=148）。
- 含公共武器 `yitian-jian`/`gangdao`/`changjian` + 门派 `zhudao`（emei）。
- 非武侠 `load_game("academy_micro")` 的 `item_registry` 不含 `yitian-jian`
  （glob `default_*` 无匹配）。

### 5. ADR + PROGRESS 更新

- [ADR-0062](docs/adr/ADR-0062-weapon-cpk-wiring-postpone.md) 末尾补
  `### 4. 实施落地（接线批）`：记录 glob 发现约定 + 无 entry_points 区分场景/数据层
  CPK + 17 CPK 目录落定 + cli 合并。不偏离基线，不另开 ADR 编号。
- [PROGRESS.md](PROGRESS.md)：Done 加本批（≤2 行 + ADR-0062 链 + tests 数），
  In Progress 清空该接力项，Next Up 移除"门派武器 CPK 接线"。

## 验收标准

1. 17 个 CPK 目录各含 `manifest.yaml`（无 entry_points / theme=wuxia / module_pack）
   + `items.yaml`；`scenes/wuxia_weapons/` 删除。
2. `load_game("xueshan_micro")` 后 `game.item_registry` 含 149 武器（公共+门派）。
3. 非武侠 scene 不注入武侠武器。
4. 演进后 test_weapons_catalog.py 数据完整性断言全过 + 新增 CPK 加载/接线测试绿。
5. 全量 tests 绿（2383 → 演进后基线），`just lint` 过。
6. WeaponDef/SAMPLE_WEAPONS 不动；COMBINED_ITEM 不碰；wield 未实现。

## 执行顺序

1. 建 17 目录 + 搬 items.yaml + 写 manifest（bash 搬移 + Write manifest）。
2. 删 wuxia_weapons。
3. 改 cli.py（glob 合并）。
4. 改 weapon_finalize.py（写出新结构）+ items.py 注释。
5. 重构 test_weapons_catalog.py + 新增 cli 接线测试。
6. `just lint && just test` 全绿。
7. ADR-0062 补实施小节 + PROGRESS 更新。
