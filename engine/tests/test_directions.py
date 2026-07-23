"""内置十向同义词表单元测试（Polishing A1）。"""

from mud_engine.directions import (
    DIRECTION_FORMS,
    builtin_aliases,
    exit_display_base,
    merge_exit_match_names,
    resolve_chinese_builtin,
    resolve_english_bare,
)

_TEN = (
    "north",
    "south",
    "east",
    "west",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
    "up",
    "down",
)


class TestDirectionFormsMatrix:
    def test_covers_exactly_ten_cardinal_directions(self) -> None:
        assert set(DIRECTION_FORMS) == set(_TEN)

    def test_each_direction_has_english_full_short_and_chinese(self) -> None:
        for direction in _TEN:
            full, short, chinese = builtin_aliases(direction)
            assert full == direction
            assert short == DIRECTION_FORMS[direction][0]
            assert chinese == DIRECTION_FORMS[direction][1]
            assert resolve_english_bare(full) == direction
            assert resolve_english_bare(short) == direction
            assert resolve_chinese_builtin(chinese) == direction

    def test_diagonal_chinese_follows_english_gloss(self) -> None:
        assert resolve_chinese_builtin("东南") == "southeast"
        assert resolve_chinese_builtin("西南") == "southwest"
        assert resolve_chinese_builtin("东北") == "northeast"
        assert resolve_chinese_builtin("西北") == "northwest"

    def test_english_bare_is_case_insensitive(self) -> None:
        assert resolve_english_bare("East") == "east"
        assert resolve_english_bare("NE") == "northeast"

    def test_unknown_tokens_resolve_to_none(self) -> None:
        assert resolve_english_bare("in") is None
        assert resolve_chinese_builtin("里面") is None


class TestMergeAndDisplay:
    def test_merge_order_exit_then_room_then_builtin(self) -> None:
        merged = merge_exit_match_names(
            "north",
            ("密道",),
            target_name="秘道",
            target_aliases=("暗道",),
        )
        assert merged[:3] == ("密道", "秘道", "暗道")
        assert "north" in merged and "n" in merged and "北" in merged

    def test_dedup_keeps_custom_before_dropping_builtin_duplicate(self) -> None:
        # 出口已写「北」时，内置「北」不重复出现。
        merged = merge_exit_match_names("north", ("北", "北道"), target_name="长廊")
        assert merged.count("北") == 1
        assert merged.index("北") < merged.index("north")

    def test_look_label_is_chinese_parenthetical_english(self) -> None:
        assert exit_display_base("east") == "东(east)"
        assert exit_display_base("southeast") == "东南(southeast)"
        assert exit_display_base("cave") == "cave"
