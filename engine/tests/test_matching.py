"""通用别名匹配工具的单元测试：与具体目标类型无关，直接喂候选集合。

覆盖成功 / 无匹配 / 歧义 / 大小写 / 规范名别名同权 / 规范名与别名冲突
（02 号票 acceptance 第 6、7 条）。按 Given/When 分组，方法名只写 Then。
"""

from mud_engine.matching import Ambiguous, NoMatch, Resolved, match_target

# 一组稳定的示例候选：north 带中文别名"北道"与前缀简写"前"，south 只带别名。
CANDIDATES = [
    ("north", ("北道", "前")),
    ("south", ("南道",)),
    ("east", ()),
]


class TestMatchTarget:
    def test_resolves_by_canonical_name(self) -> None:
        assert match_target("north", CANDIDATES) == Resolved("north")

    def test_resolves_by_alias(self) -> None:
        assert match_target("北道", CANDIDATES) == Resolved("north")

    def test_matching_is_case_insensitive(self) -> None:
        assert match_target("NORTH", CANDIDATES) == Resolved("north")

    def test_canonical_and_alias_within_same_candidate_do_not_duplicate(self) -> None:
        # 别名恰好等于自己的规范名不算歧义，仍是唯一命中。
        assert match_target("north", [("north", ("north",))]) == Resolved("north")

    class WhenNoCandidateMatches:
        def test_returns_no_match(self) -> None:
            assert match_target("up", CANDIDATES) == NoMatch("up")

        def test_preserves_the_original_token(self) -> None:
            assert match_target("xyz", CANDIDATES).token == "xyz"

        def test_blank_token_returns_no_match(self) -> None:
            assert match_target("   ", CANDIDATES) == NoMatch("   ")

    class WhenMultipleCanonicalsShareAnAlias:
        def test_returns_ambiguous_with_all_hits(self) -> None:
            candidates = [("north", ("门",)), ("south", ("门",))]
            assert match_target("门", candidates) == Ambiguous(("north", "south"))

    class WhenCanonicalNameOfOneMatchesAliasOfAnother:
        # "north" 既是候选 A 的规范名，又是候选 B 的别名--输入它同时命中两个。
        def test_returns_ambiguous(self) -> None:
            candidates = [("north", ()), ("up", ("north",))]
            assert match_target("north", candidates) == Ambiguous(("north", "up"))
