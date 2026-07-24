"""解析层测试：确定性解析器、解析失败信号、解析器链。

直接驱动 DeterministicParser.parse 与 ParserChain.parse，断言产出 Intent 或
ParseFailure 的形状（02 号票 acceptance 第 1、3、4 条）；execute_line 的端到端
行为在 test_commands 覆盖。按 Given/When 场景分组成嵌套类，方法名只写 Then。
"""

from openmud.components import Exit, Exits, Position
from openmud.intent import Intent, ParseFailure, Reason
from openmud.parsing import DeterministicParser, Parser, ParserChain
from openmud.scenes import build_world
from openmud.world import EntityId, World


def _parse(line: str) -> Intent | ParseFailure:
    """用确定性解析器解析一行（默认 start_yard 场景）。"""
    world, player_id = build_world()
    return DeterministicParser().parse(line, world, player_id)


class _StubParser(Parser):
    """返回预设结果的解析器桩，供 ParserChain 测试--不读输入也不读世界。"""

    def __init__(self, result: Intent | ParseFailure) -> None:
        self._result = result

    def parse(self, line: str, world: World, player_id: EntityId) -> Intent | ParseFailure:
        return self._result


class TestDeterministicParser:
    def test_look_parses_to_a_look_intent(self) -> None:
        assert _parse("look") == Intent(verb="look", target=None)

    def test_command_alias_l_resolves_to_look(self) -> None:
        assert _parse("l") == Intent(verb="look", target=None)

    def test_help_and_its_alias_h_resolve_to_help(self) -> None:
        assert _parse("help") == Intent(verb="help", target=None)
        assert _parse("h") == Intent(verb="help", target=None)

    def test_quit_parses_to_a_quit_intent(self) -> None:
        assert _parse("quit") == Intent(verb="quit", target=None)

    def test_go_with_canonical_direction_resolves_target(self) -> None:
        assert _parse("go north") == Intent(verb="go", target="north")

    def test_go_with_direction_alias_resolves_to_canonical(self) -> None:
        assert _parse("go 北道") == Intent(verb="go", target="north")

    def test_direction_shortcut_n_resolves_to_go_north(self) -> None:
        assert _parse("n") == Intent(verb="go", target="north")

    def test_verb_matching_is_case_insensitive(self) -> None:
        assert _parse("LOOK") == Intent(verb="look", target=None)

    class WhenVerbIsUnknown:
        def test_returns_unknown_verb_failure_preserving_the_token(self) -> None:
            assert _parse("fly") == ParseFailure(Reason.UNKNOWN_VERB, original="fly")

    class WhenDirectionHasNoMatchingExit:
        def test_returns_no_target_match_failure(self) -> None:
            assert _parse("go up") == ParseFailure(Reason.NO_TARGET_MATCH, original="up", verb="go")

    class WhenDirectionAliasMatchesMultipleExits:
        def test_returns_ambiguous_failure_with_all_candidates(self) -> None:
            # 构造一个两个出口共享别名"门"的房间，验证歧义信号带全部候选。
            world, player_id = build_world()
            room = world.require_component(player_id, Position).room
            exits = world.require_component(room, Exits)
            north_target = exits.by_direction["north"].target
            exits.by_direction["north"] = Exit(target=north_target, aliases=("门",))
            other = world.create_entity()
            exits.by_direction["east"] = Exit(target=other, aliases=("门",))

            result = DeterministicParser().parse("go 门", world, player_id)

            assert isinstance(result, ParseFailure)
            assert result.reason is Reason.AMBIGUOUS_TARGET
            assert result.original == "门"
            assert set(result.candidates) == {"north", "east"}

    class WhenUsingBuiltinDirectionSynonyms:
        def test_go_with_chinese_cardinal_resolves(self) -> None:
            assert _parse("go 北") == Intent(verb="go", target="north")

        def test_bare_english_full_resolves_to_go(self) -> None:
            assert _parse("east") == Intent(verb="go", target="east")

        def test_bare_english_diagonal_shortcut_resolves_to_go(self) -> None:
            # 默认场景无 northeast 出口；解析仍落到 Intent，执行层再报无出口。
            world, player_id = build_world()
            result = DeterministicParser().parse("ne", world, player_id)
            assert result == Intent(verb="go", target="northeast")

        def test_bare_chinese_cardinal_requires_go(self) -> None:
            result = _parse("东")
            assert result == ParseFailure(Reason.REQUIRES_GO, original="东")

        def test_bare_chinese_place_alias_requires_go(self) -> None:
            # 北道是 corridor 房间 aliases（经目标房回退可 go 北道）。
            result = _parse("北道")
            assert result == ParseFailure(Reason.REQUIRES_GO, original="北道")

        def test_go_to_target_room_name_resolves(self) -> None:
            # corridor 房间 name=长廊；经目标房回退可 go 长廊。
            assert _parse("go 长廊") == Intent(verb="go", target="north")

        def test_unknown_bare_token_is_still_unknown_verb(self) -> None:
            assert _parse("fly") == ParseFailure(Reason.UNKNOWN_VERB, original="fly")


class TestParserChain:
    def test_returns_the_first_successful_intent_without_calling_later_parsers(
        self,
    ) -> None:
        intent = Intent(verb="look", target=None)
        chain = ParserChain(
            [_StubParser(intent), _StubParser(ParseFailure(Reason.UNKNOWN_VERB, "unused"))]
        )
        world, player_id = build_world()
        assert chain.parse("anything", world, player_id) is intent

    def test_returns_the_last_failure_when_all_parsers_fail(self) -> None:
        first = ParseFailure(Reason.UNKNOWN_VERB, "a")
        second = ParseFailure(Reason.NO_TARGET_MATCH, "b")
        chain = ParserChain([_StubParser(first), _StubParser(second)])
        world, player_id = build_world()
        assert chain.parse("x", world, player_id) == second
