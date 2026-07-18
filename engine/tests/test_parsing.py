"""解析层测试：确定性解析器、解析失败信号、解析器链。

直接驱动 DeterministicParser.parse 与 ParserChain.parse，断言产出 Intent 或
ParseFailure 的形状（02 号票 acceptance 第 1、3、4 条）；execute_line 的端到端
行为在 test_commands 覆盖。按 Given/When 场景分组成嵌套类，方法名只写 Then。
"""

from mud_engine.components import Exit, Exits, Position
from mud_engine.intent import Intent, ParseFailure, Reason
from mud_engine.parsing import DeterministicParser, Parser, ParserChain
from mud_engine.scenes import build_world
from mud_engine.world import EntityId, World


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
