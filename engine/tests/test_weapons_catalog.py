"""门派武器 ItemDef 台账测试（ADR-0060 决策 6 + ADR-0062 CPK 接线）。

覆盖 [scenes/wuxia_common/](../scenes/wuxia_common/) +
[scenes/wuxia_<sect>/](../scenes/) 17 个数据层 CPK 的 items.yaml：

- load_items 加载所有武器 YAML -> ItemDef schema 校验通过（pydantic 不抛）。
- compile_scene 编译 -> ir["items"] 含全部条目，kind=="item"。
- 全部 id 唯一（权威源去重，clone/weapon > clone/unique > d/*/obj）。
- load_cpk 加载每个数据层 CPK（manifest 无 entry_points / theme=wuxia）。
- 代表武器行为断言：倚天剑 flag=4/damage=150、血刀纯数据+do_lian 缺口、
  通用钢刀/长剑在 wuxia_common、em 折叠到 wuxia_emei(zhudao)。
- COMBINED_ITEM（falun/shizi/shizi2）整体不进本批（决策 4 留方案 A）。
- damage 走 weapon_prop mapping（决策 1 不变量 2，非标量字段）。

ADR-0062 接线：数据层 CPK 经 cli.py ``_load_theme_data_items`` 合并进
game.item_registry（cli 接线测试见 test_cli_weapon_wiring.py）。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from xkx.dsl.cpk import CpkManifest
from xkx.dsl.cpk_loader import load_cpk
from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_items
from xkx.themes import default_registry

SCENES_DIR = Path(__file__).resolve().parents[1] / "scenes"


def _data_layer_cpks() -> list[Path]:
    """所有 wuxia_* 数据层 CPK 目录（manifest.entry_points 为空，跳过 wuxia_micro 场景）。

    与 cli.py ``_load_theme_data_items`` 发现逻辑一致：glob wuxia_*/ 后按
    entry_points 区分数据层（空）vs 场景（有 main_scene）。
    """
    dirs: list[Path] = []
    for d in sorted(SCENES_DIR.glob("wuxia_*/")):
        m = CpkManifest.model_validate(
            yaml.safe_load((d / "manifest.yaml").read_text(encoding="utf-8"))
        )
        if not m.entry_points:
            dirs.append(d)
    return dirs


def _all_weapon_files() -> list[Path]:
    """wuxia_common/items.yaml + wuxia_<sect>/items.yaml（数据层 CPK）。"""
    return [d / "items.yaml" for d in _data_layer_cpks()]


def _all_items():
    items = []
    for f in _all_weapon_files():
        items += load_items(f)
    return items


def _items_by_id():
    return {i.id: i for i in _all_items()}


def test_data_layer_cpks_count_17():
    """数据层 CPK = 17（wuxia_common + 16 门派；em 折叠到 emei 不独立）。"""
    cpks = _data_layer_cpks()
    names = {p.name for p in cpks}
    assert len(cpks) == 17
    assert "wuxia_common" in names
    assert "wuxia_emei" in names
    assert "wuxia_em" not in names  # em 折叠到 emei


def test_all_weapon_yaml_load_as_itemdef():
    """所有武器 YAML 经 load_items 加载为 ItemDef，schema 校验通过。"""
    items = _all_items()
    # 149 条（草表 267 去重 152 - 3 COMBINED_ITEM 跳过 = 149）
    assert len(items) >= 148


def test_compile_scene_includes_all_items():
    """compile_scene 编译 -> ir["items"] 含全部条目，kind=="item"。"""
    items = _all_items()
    ir = compile_scene([], [], [], items)
    assert len(ir["items"]) == len(items)
    assert all(i["kind"] == "item" for i in ir["items"])


def test_all_ids_unique():
    """权威源去重后全部 id 唯一（em 折叠到 emei，clone/weapon 权威）。"""
    items = _all_items()
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids)), "存在重复 id"


def test_each_data_layer_cpk_loads_via_load_cpk():
    """每个数据层 CPK 经 load_cpk 加载（manifest 校验 + theme=wuxia 已注册）。"""
    registry = default_registry()
    for cpk_dir in _data_layer_cpks():
        manifest, ir, _rules, _skills = load_cpk(cpk_dir, registry=registry)
        assert manifest.theme == "wuxia"
        assert not manifest.entry_points  # 数据层无入口房间
        assert manifest.pack_type == "module_pack"
        # items.yaml -> ir["items"]
        assert len(ir["items"]) == len(load_items(cpk_dir / "items.yaml"))


def test_yitian_jian():
    """倚天剑：init_sword(150) -> flag=4(EDGED)，weight 4000，material steel。"""
    w = _items_by_id()["yitian-jian"]
    assert w.flag == 4  # EDGED（sword.c 自动 |EDGED）
    assert w.weapon_prop["damage"] == 150
    assert w.weight == 4000
    assert w.material == "steel"
    assert w.skill_type == "sword"
    assert w.rigidity == 2000


def test_xuedao_pure_data_with_command_gap():
    """血刀纯数据本批填，do_lian 命令留命令批（缺口在 YAML 注释，数据完整）。"""
    w = _items_by_id()["xuedao"]
    assert w.flag == 4  # EDGED（blade.c 自动 |EDGED）
    assert w.weapon_prop["damage"] == 100
    assert w.weight == 7000
    assert w.rigidity == 1000000


def test_combined_item_skipped():
    """COMBINED_ITEM（falun/shizi/shizi2）整体不进本批（决策 4 留方案 A）。"""
    ids = _items_by_id()
    assert "falun" not in ids
    assert "shizi" not in ids
    assert "shizi2" not in ids


def test_common_weapons_in_common():
    """通用武器（钢刀 gangdao/长剑 changjian，多门派引用）在 wuxia_common/items.yaml。"""
    common = {i.id for i in load_items(SCENES_DIR / "wuxia_common" / "items.yaml")}
    assert "gangdao" in common
    assert "changjian" in common
    assert "yitian-jian" in common  # clone/weapon 权威源


def test_gangdao_blade_edged():
    """钢刀：init_blade(25) -> flag=4(EDGED)，通用武器。"""
    w = _items_by_id()["gangdao"]
    assert w.flag == 4
    assert w.weapon_prop["damage"] == 25
    assert w.skill_type == "blade"


def test_em_folded_to_emei():
    """em 折叠到 emei：zhudao 在 wuxia_emei，无独立 wuxia_em 目录。"""
    emei = {i.id for i in load_items(SCENES_DIR / "wuxia_emei" / "items.yaml")}
    assert "zhudao" in emei
    assert not (SCENES_DIR / "wuxia_em").exists()


def test_bian_whip_flag_zero():
    """羊鞭：init_whip -> flag=0（whip.c 不合并，决策 5 逐类型确认）。"""
    w = _items_by_id()["bian"]
    assert w.flag == 0
    assert w.skill_type == "whip"


def test_damage_in_weapon_prop_mapping():
    """damage 走 weapon_prop mapping（决策 1 不变量 2），非标量字段。"""
    items = _all_items()
    has_damage = [w for w in items if w.weapon_prop]
    assert len(has_damage) > 100
    for w in has_damage:
        assert "damage" in w.weapon_prop


def test_sect_cpks_each_has_items():
    """每个门派数据层 CPK 至少 1 条武器。"""
    sect_cpks = [d for d in _data_layer_cpks() if d.name != "wuxia_common"]
    assert len(sect_cpks) >= 10  # 16 门派
    for d in sect_cpks:
        items = load_items(d / "items.yaml")
        assert len(items) >= 1, f"{d.name} 无武器条目"
