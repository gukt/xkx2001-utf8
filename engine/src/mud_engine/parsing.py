"""命令解析：文本 -> 意图，解析器可插拔链。

确定性解析器（命令别名表 + 方向简写 + 简单语法规则）是 M1 唯一接入的解析器，
但架构上把"解析器可以是一条链，各级共享同一输出格式（``Intent`` | ``ParseFailure``）
与失败信号"这件事定下来（02 号票）：``ParserChain`` 依次尝试各级解析器，首个
产出 ``Intent`` 即返回，全失败返回最后一个 ``ParseFailure``。未来接入 AI 兜底
解析器只需 append 一个新解析器，不动执行层或已有解析器（spec 用户故事 25/26）。

所有目标别名匹配（go 的方向、take/drop 的物品）都在解析阶段用 ``match_target``
完成，``Intent.target`` 装已解析的规范名；执行层不感知原始文本或别名（03 号票
延续 02 的分层：commands 不依赖 matching，目标解析统一在 parsing 层）。

``execute_line`` 是 CLI 的入口：拿一行原始文本 -> 解析 -> 执行 -> 返回消息。
解析失败时把 ``ParseFailure`` 翻译成给玩家的提示，不抛异常。
"""

from __future__ import annotations

from collections.abc import Iterable

from mud_engine.commands import execute, resolve_verb
from mud_engine.components import Container, Exits, Identity, Position
from mud_engine.intent import Intent, ParseFailure, Reason
from mud_engine.matching import Ambiguous, Candidate, Resolved, match_target
from mud_engine.world import EntityId, World

# 方向简写：单独输入一个简写等价于 go <方向>。不走命令别名表（因为 n -> go
# north 不是 verb -> verb 的替换，而是带预填参数），是解析器的语法规则。
DIRECTION_SHORTCUTS: dict[str, str] = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
}


class Parser:
    """解析器基类：文本 + 世界上下文 -> Intent | ParseFailure。

    需要世界上下文是因为目标别名匹配（go 的方向、take/drop 的物品）的候选来自
    当前房间出口表与容器；解析器只读世界，不改世界。各级解析器共享这个签名
    与输出格式。
    """

    def parse(self, line: str, world: World, player_id: EntityId) -> Intent | ParseFailure:
        raise NotImplementedError


class DeterministicParser(Parser):
    """确定性解析器：命令别名表 + 方向简写 + 简单语法（动词 + 位置参数）。"""

    def parse(self, line: str, world: World, player_id: EntityId) -> Intent | ParseFailure:
        stripped = line.strip()
        if not stripped:
            # 空输入归 UNKNOWN_VERB（防御）：execute_line 先把空输入短路成无操作，
            # 不调解析器；直接调用解析器时空输入按"没识别出动词"处理。
            return ParseFailure(Reason.UNKNOWN_VERB, original=stripped)

        tokens = stripped.split()
        head, rest = tokens[0].lower(), tokens[1:]

        # 方向简写：单独输入 n/s/e/w -> go <对应方向>（方向是确定值，无需候选匹配）。
        if head in DIRECTION_SHORTCUTS and not rest:
            return Intent(verb="go", target=DIRECTION_SHORTCUTS[head])

        verb = resolve_verb(head)
        if verb is None:
            return ParseFailure(Reason.UNKNOWN_VERB, original=head)

        if verb == "go":
            return self._parse_go(rest, world, player_id)
        if verb == "take":
            return self._parse_item(rest, world, player_id, verb="take", source="room")
        if verb == "drop":
            return self._parse_item(rest, world, player_id, verb="drop", source="player")
        # look / help / inventory / quit 无目标参数；多余参数本阶段忽略（M1 不校验）。
        return Intent(verb=verb, target=None, args=tuple(rest))

    def _parse_go(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        if not args:
            # 缺方向参数：算可执行意图但 target 缺失，由执行层给用法提示
            # （保持 01 号票"go"无参的提示行为，不归为解析失败）。
            return Intent(verb="go", target=None)

        token = args[0]
        candidates = self._direction_candidates(world, player_id)
        result = match_target(token, candidates)
        if isinstance(result, Resolved):
            return Intent(verb="go", target=result.canonical)
        if isinstance(result, Ambiguous):
            return ParseFailure(
                Reason.AMBIGUOUS_TARGET,
                original=token,
                verb="go",
                candidates=result.canonicals,
            )
        return ParseFailure(Reason.NO_TARGET_MATCH, original=token, verb="go")

    def _parse_item(
        self,
        args: list[str],
        world: World,
        player_id: EntityId,
        verb: str,
        source: str,
    ) -> Intent | ParseFailure:
        """take/drop 共用的物品目标解析：source 决定从哪个容器取候选。

        source="room" 取当前房间地面容器（take），source="player" 取玩家物品栏（drop）。
        """
        if not args:
            return Intent(verb=verb, target=None)
        token = args[0]
        candidates = self._item_candidates(world, player_id, source)
        result = match_target(token, candidates)
        if isinstance(result, Resolved):
            return Intent(verb=verb, target=result.canonical)
        if isinstance(result, Ambiguous):
            return ParseFailure(
                Reason.AMBIGUOUS_TARGET,
                original=token,
                verb=verb,
                candidates=result.canonicals,
            )
        return ParseFailure(Reason.NO_TARGET_MATCH, original=token, verb=verb)

    @staticmethod
    def _direction_candidates(world: World, player_id: EntityId) -> list[Candidate]:
        room = world.require_component(player_id, Position).room
        exits = world.require_component(room, Exits)
        return [(direction, passage.aliases) for direction, passage in exits.by_direction.items()]

    @staticmethod
    def _item_candidates(world: World, player_id: EntityId, source: str) -> list[Candidate]:
        holder = (
            world.require_component(player_id, Position).room if source == "room" else player_id
        )
        container = world.get_component(holder, Container)
        if container is None:
            return []
        candidates: list[Candidate] = []
        for item in container.items:
            identity = world.require_component(item, Identity)
            candidates.append((identity.name, identity.aliases))
        return candidates


class ParserChain:
    """解析器链：依次尝试各级解析器，首个产出 Intent 即返回，否则返回最后失败。

    M1 只放入一个 DeterministicParser；未来接入 AI 兜底解析器即 append 一个，
    其失败信号（ParseFailure.reason）帮助兜底器判断该不该接手。
    """

    def __init__(self, parsers: Iterable[Parser]) -> None:
        self._parsers = list(parsers)

    def parse(self, line: str, world: World, player_id: EntityId) -> Intent | ParseFailure:
        last_failure = ParseFailure(Reason.UNKNOWN_VERB, original=line.strip())
        for parser in self._parsers:
            result = parser.parse(line, world, player_id)
            if isinstance(result, Intent):
                return result
            last_failure = result
        return last_failure


def execute_line(world: World, player_id: EntityId, line: str) -> list[str]:
    """给定一行原始输入文本，解析并执行，返回展示给玩家的消息。

    空输入（玩家只敲了回车）是无操作，直接返回空消息，不进解析器；其他解析
    失败翻译成提示，不抛未捕获异常（保持 01 号票对未知命令/无匹配的行为）。
    """
    if not line.strip():
        return []

    chain = ParserChain([DeterministicParser()])
    result = chain.parse(line, world, player_id)
    if isinstance(result, Intent):
        return execute(world, player_id, result)
    return _failure_message(result)


def _failure_message(failure: ParseFailure) -> list[str]:
    """把结构化解析失败翻译成给玩家的一句提示。"""
    if failure.reason is Reason.UNKNOWN_VERB:
        return [f"未知命令：{failure.original}。输入 help 查看当前支持的命令列表。"]
    if failure.reason is Reason.AMBIGUOUS_TARGET:
        candidates = "、".join(failure.candidates)
        return [f"不确定你指的是哪个：{candidates}。"]
    # NO_TARGET_MATCH：按命令给不同措辞。
    if failure.verb == "take":
        return [f"这里没有 {failure.original}。"]
    if failure.verb == "drop":
        return [f"你没有 {failure.original}。"]
    return [f"那个方向（{failure.original}）没有出口。"]  # go / 默认


__all__ = ["DeterministicParser", "Parser", "ParserChain", "execute_line"]
