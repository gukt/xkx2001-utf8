"""门派武器 ItemDef 台账测试（ADR-0060 决策 6 落地）。

覆盖 [scenes/wuxia_weapons/](../scenes/wuxia_weapons/) 产出的 common.yaml + sect/*.yaml：

- load_items 加载所有武器 YAML -> ItemDef schema 校验通过（pydantic 不抛）。
- compile_scene 编译 -> ir["items"] 含全部条目，kind=="item"。
- 全部 id 唯一（权威源去重，clone/weapon > clone/unique > d/*/obj）。
- 代表武器行为断言：倚天剑 flag=4(EDGED)/damage=150、血刀纯数据+do_lian 缺口、
  通用钢刀/长剑在 common、em 折叠到 emei(zhudao)。
- COMBINED_ITEM（falun/shizi/shizi2）整体不进本批（决策 4 留方案 A）。
- damage 走 weapon_prop mapping（决策 1 不变量 2，非标量字段）。

不接 cli.py（CPK 接线后置 ADR-0062），直接测 load_items + compile_scene。
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_items

WEAPONS_DIR = Path(__file__).resolve().parents[1] / "scenes" / "wuxia_weapons"


def _all_weapon_files() -> list[Path]:
    """common.yaml + sect/*.yaml。"""
    files = [WEAPONS_DIR / "common.yaml"]
    files += sorted((WEAPONS_DIR / "sect").glob("*.yaml"))
    return files


def _all_items():
    items = []
    for f in _all_weapon_files():
        items += load_items(f)
    return items


def _items_by_id():
    return {i.id: i for i in _all_items()}


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
    """通用武器（钢刀 gangdao/长剑 changjian，多门派引用）在 common.yaml。"""
    common = {i.id for i in load_items(WEAPONS_DIR / "common.yaml")}
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
    """em 折叠到 emei：zhudao 在 em/emei 复制，折叠成 1 条进 sect/emei。"""
    emei = {i.id for i in load_items(WEAPONS_DIR / "sect" / "emei.yaml")}
    assert "zhudao" in emei
    # em 不应作为独立门派目录出现（已折叠到 emei）
    assert not (WEAPONS_DIR / "sect" / "em.yaml").exists()


def test_bian_whip_flag_zero():
    """羊鞭：init_whip -> flag=0（whip.c 不合并，决策 5 逐类型确认）。"""
    w = _items_by_id()["bian"]
    assert w.flag == 0
    assert w.skill_type == "whip"


def test_damage_in_weapon_prop_mapping():
    """damage 走 weapon_prop mapping（决策 1 不变量 2），非标量字段。"""
    items = _all_items()
    # 有 weapon_prop 的武器，damage 在 mapping 内
    has_damage = [w for w in items if w.weapon_prop]
    assert len(has_damage) > 100
    for w in has_damage:
        assert "damage" in w.weapon_prop


def test_sect_files_each_has_items():
    """每个门派 sect 文件至少 1 条武器。"""
    sect_files = list((WEAPONS_DIR / "sect").glob("*.yaml"))
    assert len(sect_files) >= 10  # 16 门派
    for f in sect_files:
        items = load_items(f)
        assert len(items) >= 1, f"{f.name} 无武器条目"
