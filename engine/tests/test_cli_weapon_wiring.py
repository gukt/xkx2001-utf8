"""cli.py 武器 CPK 接线测试（ADR-0062 决策 2 落地）。

验证 ``load_game`` 后 ``game.item_registry`` 含全量 149 武器（公共 + 门派数据层
CPK 经 ``_load_theme_data_items`` 合并），供 wield 命令批消费。非武侠题材无数据层
CPK，不注入武侠武器。

本批只接数据进 item_registry，不实现 wield 命令（wield 留下批）。
"""

from __future__ import annotations

from xkx.cli import _load_theme_data_items, load_game
from xkx.themes import default_registry


def test_xueshan_item_registry_has_all_weapons():
    """load_game(xueshan_micro) 后 item_registry 含全量武器（>=148）。"""
    game, _pid = load_game("xueshan_micro")
    ids = set(game.item_registry.keys())
    assert len(ids) >= 148
    # 公共武器（wuxia_common 数据层 CPK）
    assert "yitian-jian" in ids
    assert "gangdao" in ids
    assert "changjian" in ids
    # 门派专属（wuxia_emei 数据层 CPK）
    assert "zhudao" in ids


def test_default_theme_no_data_items():
    """非武侠题材（default）无数据层 CPK，_load_theme_data_items 返回空。"""
    reg = default_registry()
    assert _load_theme_data_items("default", reg) == []
