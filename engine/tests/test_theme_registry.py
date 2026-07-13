"""ThemeRegistry 静态加载测试（M3-2，ADR-0031 决策 3）。"""

from __future__ import annotations

import inspect

import pytest

from xkx.runtime.theme_registry import ThemeDescriptor, ThemeRegistry
from xkx.themes import default_registry
from xkx.themes.default import PIRATE_BONUS, build_default_descriptor
from xkx.themes.wuxia import WUDANG_BONUS, build_wuxia_descriptor


class TestThemeRegistry:
    """ThemeRegistry 静态加载（wuxia + default 2 题材）。"""

    def test_default_registry_two_themes(self) -> None:
        """default_registry 注册 wuxia + default 2 题材。"""
        r = default_registry()
        assert "wuxia" in r
        assert "default" in r
        assert set(r.theme_ids()) == {"wuxia", "default"}

    def test_require_returns_descriptor(self) -> None:
        """require 返回 ThemeDescriptor，未注册 raise KeyError。"""
        r = default_registry()
        w = r.require("wuxia")
        assert w.theme_id == "wuxia"
        with pytest.raises(KeyError):
            r.require("nonexistent")

    def test_get_returns_none_if_unregistered(self) -> None:
        """get 未注册返回 None。"""
        r = default_registry()
        assert r.get("nonexistent") is None

    def test_wuxia_descriptor(self) -> None:
        """wuxia 题材：HUMAN_PROFILE + 武当派 FamilyBonus + ThemeConfig.wuxia()。"""
        w = build_wuxia_descriptor()
        assert w.theme_id == "wuxia"
        assert w.race_profile is not None
        assert len(w.family_bonuses) == 1
        assert w.family_bonuses[0] is WUDANG_BONUS
        assert w.family_bonuses[0].family_name == "武当派"
        assert w.theme_config is not None
        assert w.theme_config.start_room == "xueshan/shanmen"

    def test_default_descriptor(self) -> None:
        """default 题材：HUMAN_PROFILE + 海盗帮 FamilyBonus + ThemeConfig.default()。"""
        d = build_default_descriptor()
        assert d.theme_id == "default"
        assert len(d.family_bonuses) == 1
        assert d.family_bonuses[0] is PIRATE_BONUS
        assert d.family_bonuses[0].family_name == "海盗帮"
        assert d.theme_config is not None
        assert d.theme_config.start_room == "test/start"

    def test_theme_registry_no_wuxia_literals(self) -> None:
        """主题无关性硬门禁：theme_registry.py 无门派名/武侠字面量。

        题材包具体数据（武当派/海盗帮 FamilyBonus）在 xkx.themes 模块（题材包
        数据层），runtime/theme_registry.py 只提供注册机制。
        """
        from xkx.runtime import theme_registry as mod

        source = inspect.getsource(mod)
        # 门派名黑名单（ADR-0030 决策 4）
        for literal in ["武当", "少林", "峨嵋", "华山", "丐帮", "雪山派", "海盗"]:
            assert literal not in source, (
                f"theme_registry.py 含题材字面量: {literal}"
            )

    def test_register_overwrites(self) -> None:
        """register 重复注册覆盖。"""
        r = ThemeRegistry()
        d1 = build_wuxia_descriptor()
        r.register(d1)
        r.register(d1)  # 重复
        assert len(r.theme_ids()) == 1

    def test_themedescriptor_frozen(self) -> None:
        """ThemeDescriptor frozen dataclass（赋值 raise）。"""
        d = build_wuxia_descriptor()
        with pytest.raises(AttributeError):
            d.theme_id = "other"  # type: ignore[misc]

    def test_descriptor_default_fields(self) -> None:
        """ThemeDescriptor 默认字段（class_tables/predicates/verbs 空闭环）。"""
        d = ThemeDescriptor(theme_id="test", race_profile=build_wuxia_descriptor().race_profile)
        assert d.family_bonuses == []
        assert d.theme_config is None
        assert d.class_tables == {}
        assert d.condition_predicates == set()
        assert d.action_verbs == set()
        assert d.governance_policies == {}
