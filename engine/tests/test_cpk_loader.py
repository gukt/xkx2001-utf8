"""CPK 加载器测试（M3-2，ADR-0031 决策 4）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from xkx.dsl.cpk_loader import load_cpk
from xkx.runtime.theme_registry import ThemeRegistry
from xkx.themes import default_registry

SCENES = Path(__file__).resolve().parent.parent / "scenes"


class TestCpkLoader:
    """load_cpk 加载器（manifest -> IR + rules）。"""

    def test_load_xueshan_micro(self) -> None:
        """加载 xueshan_micro（wuxia 旗舰，8 房间）。"""
        r = default_registry()
        m, ir, rules, _skills = load_cpk(SCENES / "xueshan_micro", registry=r)
        assert m.cpk_id == "wuxia_xueshan_micro"
        assert m.theme == "wuxia"
        assert len(ir["rooms"]) == 8
        assert m.entry_points["main_scene"] == "xueshan/dshanlu"
        assert len(rules) >= 1

    @pytest.mark.parametrize(
        "name,cpk_id,theme,room_count",
        [
            ("xueshan_micro", "wuxia_xueshan_micro", "wuxia", 8),
            ("zhongnan_micro", "wuxia_zhongnan_micro", "wuxia", 3),
            ("wuxia_micro", "wuxia_micro", "wuxia", 2),
            ("academy_micro", "academy_micro", "default", 2),
            ("age_of_sail_micro", "age_of_sail_micro", "default", 2),
        ],
    )
    def test_load_all_5_micro_scenes(
        self, name: str, cpk_id: str, theme: str, room_count: int
    ) -> None:
        """加载全部 5 微场景（ADR-0031 决策 5）。"""
        r = default_registry()
        m, ir, rules, _skills = load_cpk(SCENES / name, registry=r)
        assert m.cpk_id == cpk_id
        assert m.theme == theme
        assert len(ir["rooms"]) == room_count
        # main_scene 在 rooms
        room_ids = {room["id"] for room in ir["rooms"]}
        assert m.entry_points["main_scene"] in room_ids

    def test_manifest_missing_raises(self) -> None:
        """manifest.yaml 缺失 raise FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_cpk(SCENES)  # scenes 根目录无 manifest.yaml

    def test_theme_not_registered_raises(self) -> None:
        """theme 未注册 raise ValueError（registry 校验）。"""
        empty = ThemeRegistry()
        with pytest.raises(ValueError, match="未注册"):
            load_cpk(SCENES / "xueshan_micro", registry=empty)

    def test_no_registry_skips_theme_check(self) -> None:
        """不传 registry 跳过 theme 校验（仍校验 entry_points）。"""
        m, ir, rules, _skills = load_cpk(SCENES / "academy_micro")
        assert m.theme == "default"

    def test_main_scene_not_in_rooms_raises(self, tmp_path: Path) -> None:
        """main_scene 不在 rooms raise ValueError。"""
        (tmp_path / "manifest.yaml").write_text(
            "cpk_id: bad\ntheme: wuxia\nentry_points:\n  main_scene: nonexistent\n",
            encoding="utf-8",
        )
        (tmp_path / "rooms.yaml").write_text(
            "- id: real_room\n  short: s\n  long: l\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="不在 rooms"):
            load_cpk(tmp_path)

    def test_missing_asset_files_skipped(self, tmp_path: Path) -> None:
        """缺失资产文件跳过（非每个 CPK 都有 quests/items）。"""
        (tmp_path / "manifest.yaml").write_text(
            "cpk_id: minimal\ntheme: wuxia\nentry_points:\n  main_scene: r1\n",
            encoding="utf-8",
        )
        (tmp_path / "rooms.yaml").write_text(
            "- id: r1\n  short: s\n  long: l\n",
            encoding="utf-8",
        )
        # 只有 rooms，无 npcs/quests/items/rules
        m, ir, rules, _skills = load_cpk(tmp_path)
        assert len(ir["rooms"]) == 1
        assert ir["npcs"] == []
        assert ir["quests"] == []
        assert rules == []

    def test_skills_yaml_loaded(self, tmp_path: Path) -> None:
        """skills.yaml 加载为 SkillDef 列表（ADR-0036 武学内容 CPK 资产）。"""
        (tmp_path / "manifest.yaml").write_text(
            "cpk_id: with_skills\ntheme: wuxia\nentry_points:\n  main_scene: r1\n",
            encoding="utf-8",
        )
        (tmp_path / "rooms.yaml").write_text(
            "- id: r1\n  short: s\n  long: l\n",
            encoding="utf-8",
        )
        (tmp_path / "skills.yaml").write_text(
            "- skill_id: longxiang-banruo\n"
            "  skill_type: martial\n"
            "  valid_learn: true\n"
            "  practice_skill: true\n"
            "  valid_enable: [force]\n"
            "- skill_id: lamaism\n"
            "  skill_type: knowledge\n"
            "  valid_learn: true\n"
            "  practice_skill: false\n"
            "  valid_enable: []\n",
            encoding="utf-8",
        )
        m, ir, rules, skills = load_cpk(tmp_path)
        assert len(skills) == 2
        assert skills[0].skill_id == "longxiang-banruo"
        assert skills[0].skill_type == "martial"
        assert skills[0].valid_enable == ["force"]
        assert skills[1].skill_id == "lamaism"
        assert skills[1].practice_skill is False

    def test_manifest_market_fields_loaded(self) -> None:
        """manifest market 字段加载（Day1 预留）。"""
        r = default_registry()
        m, ir, rules, _skills = load_cpk(SCENES / "xueshan_micro", registry=r)
        # manifest.yaml 未写 market，用默认 MarketFields
        assert m.market.title == ""
        assert m.market.tags == []
        assert m.market.revenue_share == 0.0
