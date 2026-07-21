"""命令解析：文本 -> 意图，解析器可插拔链。

确定性解析器（命令别名表 + 方向简写 + 简单语法规则）是 M1 唯一接入的解析器，
但架构上把"解析器可以是一条链，各级共享同一输出格式（``Intent`` | ``ParseFailure``）
与失败信号"这件事定下来（02 号票）：``ParserChain`` 依次尝试各级解析器，首个
产出 ``Intent`` 即返回，全失败返回最后一个 ``ParseFailure``。未来接入 AI 兜底
解析器只需 append 一个新解析器，不动执行层或已有解析器（spec 用户故事 25/26）。

所有目标别名匹配（go 的方向、get/drop/put/look 的物品）都在解析阶段用
``match_target`` 完成，``Intent.target`` 装已解析的规范名；执行层不感知原始文本
或别名（03 号票延续 02 的分层）。04 号票的 open/close/knock/unlock 门命令复用 go
的方向解析。块 C（20/22/23 号票）扩展：``get`` 可选数量与 ``from <容器>``、
``put <物> in <容器>``、``look <物品>``；verify 补齐 ``get/drop all`` 与
``drop <物> <数量>``（规范动词 ``get``，``take`` 为别名）。

``execute_line`` 是 CLI 的入口：拿一行原始文本 -> 解析 -> 执行 -> 返回消息。
解析失败时把 ``ParseFailure`` 翻译成给玩家的提示，不抛异常。
"""

from __future__ import annotations

from collections.abc import Iterable

from mud_engine.commands import execute, resolve_verb
from mud_engine.components import (
    Container,
    Exits,
    Identity,
    Position,
    Stackable,
)
from mud_engine.intent import Intent, ParseFailure, Reason
from mud_engine.lookup import find_reachable_container, iter_lookable_containers
from mud_engine.matching import (
    Ambiguous,
    Candidate,
    EntityCandidate,
    IndexOutOfRange,
    NoMatch,
    Resolved,
    ResolvedEntity,
    match_entity_target,
    match_target,
)
from mud_engine.npc_query import is_askable_npc
from mud_engine.world import EntityId, World

# 方向简写：单独输入一个简写等价于 go <方向>。不走命令别名表（因为 n -> go
# north 不是 verb -> verb 的替换，而是带预填参数），是解析器的语法规则。
DIRECTION_SHORTCUTS: dict[str, str] = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
}

# 门命令（04 号票）：方向目标解析与 go 共用 _parse_direction，只是动词不同。
# 门名即出口方向名，候选同 go（当前房间 Exits.by_direction），不另起一套匹配。
DOOR_VERBS: frozenset[str] = frozenset({"open", "close", "knock", "unlock"})


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
            return self._parse_direction(rest, world, player_id, verb="go")
        if verb in DOOR_VERBS:
            return self._parse_direction(rest, world, player_id, verb=verb)
        if verb == "get":
            return self._parse_get(rest, world, player_id)
        if verb == "drop":
            return self._parse_drop(rest, world, player_id)
        if verb == "put":
            return self._parse_put(rest, world, player_id)
        if verb == "look":
            return self._parse_look(rest, world, player_id)
        if verb == "ask":
            return self._parse_ask(rest, world, player_id)
        if verb == "attack":
            return self._parse_attack(rest, world, player_id)
        if verb == "say":
            # say 保留原文空格：取首 token 之后的整段。
            text = stripped.split(None, 1)[1] if len(tokens) > 1 else ""
            return Intent(verb="say", target=None, args=(text,) if text else ())
        # help / inventory / quit 无目标参数；多余参数本阶段忽略（M1 不校验）。
        return Intent(verb=verb, target=None, args=tuple(rest))

    def _parse_direction(
        self, args: list[str], world: World, player_id: EntityId, *, verb: str
    ) -> Intent | ParseFailure:
        """go 与门命令共用的方向目标解析：方向候选 + match_target（04 号票复用）。

        缺方向参数：算可执行意图但 target 缺失，由执行层给用法提示（保持 01 号票
        "go"无参的提示行为，不归为解析失败）。
        """
        if not args:
            return Intent(verb=verb, target=None)

        token = args[0]
        candidates = self._direction_candidates(world, player_id)
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

    def _parse_get(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        """``get <物> [数量] [from <容器>]`` / ``get all``（20/22 号票 + verify）。

        - 无 from：物品候选来自房间地面。
        - 有 from：物品候选来自该容器；容器候选来自房间地面 + 玩家物品栏。
        - 数量（纯数字）写入 ``Intent.args`` 供执行层拆堆。
        """
        if not args:
            return Intent(verb="get", target=None)
        if len(args) == 1 and args[0].lower() == "all":
            return Intent(verb="get", target="all")

        from_idx = _index_of(args, "from")
        if from_idx is not None:
            return self._parse_get_from(args, from_idx, world, player_id)

        # get <item> [qty]
        item_token = args[0]
        qty_args: list[str] = []
        if len(args) >= 2 and args[1].isdigit():
            qty_args = [args[1]]
        matched = self._match_item_token(
            item_token, self._item_candidates(world, player_id, "room"), verb="get"
        )
        if isinstance(matched, ParseFailure):
            return matched
        return Intent(verb="get", target=matched, args=tuple(qty_args))

    def _parse_drop(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        """``drop <物> [数量]`` / ``drop all``。"""
        if not args:
            return Intent(verb="drop", target=None)
        if len(args) == 1 and args[0].lower() == "all":
            return Intent(verb="drop", target="all")

        item_token = args[0]
        qty_args: list[str] = []
        if len(args) >= 2 and args[1].isdigit():
            qty_args = [args[1]]
        matched = self._match_item_token(
            item_token,
            self._item_candidates(world, player_id, "player"),
            verb="drop",
        )
        if isinstance(matched, ParseFailure):
            return matched
        return Intent(verb="drop", target=matched, args=tuple(qty_args))

    def _parse_get_from(
        self,
        args: list[str],
        from_idx: int,
        world: World,
        player_id: EntityId,
    ) -> Intent | ParseFailure:
        """解析 ``get <物> [数量] from <容器>``。"""
        before = args[:from_idx]
        after = args[from_idx + 1 :]
        if not before or not after:
            return Intent(verb="get", target=None)

        item_token = before[0]
        qty: str | None = None
        if len(before) >= 2 and before[1].isdigit():
            qty = before[1]

        container_token = after[0]
        container_matched = self._match_item_token(
            container_token,
            self._reachable_container_candidates(world, player_id),
            verb="get",
        )
        if isinstance(container_matched, ParseFailure):
            return container_matched

        # 物品候选来自已解析的容器实体（按规范名找，走共享 lookup，30 号票）。
        container_id = find_reachable_container(world, player_id, container_matched)
        if container_id is None:
            return ParseFailure(Reason.NO_TARGET_MATCH, original=container_token, verb="get")
        nested = world.require_component(container_id, Container)
        item_candidates = self._candidates_from_container(world, nested)
        item_matched = self._match_item_token(item_token, item_candidates, verb="get")
        if isinstance(item_matched, ParseFailure):
            return item_matched

        out_args: list[str] = []
        if qty is not None:
            out_args.append(qty)
        out_args.extend(["from", container_matched])
        return Intent(verb="get", target=item_matched, args=tuple(out_args))

    def _parse_put(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        """``put <物品> in <容器>``：物品来自玩家栏，容器来自房间或玩家栏（22 号票）。"""
        if not args:
            return Intent(verb="put", target=None)
        in_idx = _index_of(args, "in")
        if in_idx is None or in_idx == 0 or in_idx >= len(args) - 1:
            # 缺 in / 缺一侧：交给执行层用法提示（可执行但 target/args 不完整）。
            if args:
                # 仍尝试解析物品名，便于执行层说"你没有 X"。
                matched = self._match_item_token(
                    args[0],
                    self._item_candidates(world, player_id, "player"),
                    verb="put",
                )
                if isinstance(matched, ParseFailure):
                    return matched
                return Intent(verb="put", target=matched, args=())
            return Intent(verb="put", target=None)

        item_token = args[0]
        container_token = args[in_idx + 1]
        item_matched = self._match_item_token(
            item_token,
            self._item_candidates(world, player_id, "player"),
            verb="put",
        )
        if isinstance(item_matched, ParseFailure):
            return item_matched
        container_matched = self._match_item_token(
            container_token,
            self._reachable_container_candidates(world, player_id),
            verb="put",
        )
        if isinstance(container_matched, ParseFailure):
            return container_matched
        return Intent(verb="put", target=item_matched, args=(container_matched,))

    def _parse_look(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        """无参 look 看房间；有参则匹配房间地面 / 物品栏 / 嵌套容器内物品（23 号票）。"""
        if not args:
            return Intent(verb="look", target=None)
        token = args[0]
        candidates = self._look_item_candidates(world, player_id)
        matched = self._match_item_token(token, candidates, verb="look")
        if isinstance(matched, ParseFailure):
            return matched
        return Intent(verb="look", target=matched)

    def _parse_ask(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        """``ask <npc> [序号] about <topic>``：支持同名序号消歧（M2-20）。"""
        about_idx = _index_of(args, "about")
        if about_idx is None or about_idx == 0 or about_idx >= len(args) - 1:
            # 缺 about / 缺 npc / 缺 topic：交给执行层给用法提示。
            return Intent(verb="ask", target=None)
        npc_token = args[0]
        # 允许多词 npc 名（about 前全部拼接）与多词 topic。
        if about_idx > 1:
            npc_token = " ".join(args[:about_idx])
        topic = " ".join(args[about_idx + 1 :])
        candidates = self._npc_entity_candidates(world, player_id)
        matched = self._match_entity_token(npc_token, candidates, verb="ask")
        if isinstance(matched, ParseFailure):
            return matched
        canonical, entity_id = matched
        return Intent(verb="ask", target=canonical, args=(topic,), target_id=entity_id)

    def _parse_attack(
        self, args: list[str], world: World, player_id: EntityId
    ) -> Intent | ParseFailure:
        """``attack <名> [序号]``：同名消歧（M2-20）。"""
        if not args:
            return Intent(verb="attack", target=None)
        token = " ".join(args)
        candidates = self._combat_entity_candidates(world, player_id)
        matched = self._match_entity_token(token, candidates, verb="attack")
        if isinstance(matched, ParseFailure):
            return matched
        canonical, entity_id = matched
        return Intent(verb="attack", target=canonical, target_id=entity_id)

    @staticmethod
    def _match_entity_token(
        token: str, candidates: list[EntityCandidate], *, verb: str
    ) -> tuple[str, int] | ParseFailure:
        result = match_entity_target(token, candidates)
        if isinstance(result, ResolvedEntity):
            return result.canonical, result.entity_id
        if isinstance(result, Ambiguous):
            return ParseFailure(
                Reason.AMBIGUOUS_TARGET,
                original=token,
                verb=verb,
                candidates=result.canonicals,
            )
        if isinstance(result, IndexOutOfRange):
            return ParseFailure(
                Reason.INDEX_OUT_OF_RANGE,
                original=token,
                verb=verb,
                candidates=(result.name, str(result.index), str(result.count)),
            )
        return ParseFailure(Reason.NO_TARGET_MATCH, original=token, verb=verb)

    @staticmethod
    def _match_item_token(
        token: str, candidates: list[Candidate], *, verb: str
    ) -> str | ParseFailure:
        result = match_target(token, candidates)
        if isinstance(result, Resolved):
            return result.canonical
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
        return DeterministicParser._candidates_from_container(world, container)

    @staticmethod
    def _candidates_from_container(world: World, container: Container) -> list[Candidate]:
        # 同名 Stackable 视为一堆（spec C3 自动合并）：去重避免 match_target
        # 判 Ambiguous；同名非 Stackable 仍多候选 -> Ambiguous（同名不同物需歧义）。
        candidates: list[Candidate] = []
        seen_stackable: set[str] = set()
        for item in container.items:
            identity = world.require_component(item, Identity)
            if world.get_component(item, Stackable) is not None:
                if identity.name in seen_stackable:
                    continue
                seen_stackable.add(identity.name)
            candidates.append((identity.name, identity.aliases))
        return candidates

    @staticmethod
    def _reachable_container_candidates(world: World, player_id: EntityId) -> list[Candidate]:
        """房间地面 + 玩家物品栏里挂有 Container 的物品。"""
        room = world.require_component(player_id, Position).room
        candidates: list[Candidate] = []
        for holder in (room, player_id):
            container = world.get_component(holder, Container)
            if container is None:
                continue
            for item in container.items:
                if world.get_component(item, Container) is None:
                    continue
                identity = world.require_component(item, Identity)
                candidates.append((identity.name, identity.aliases))
        return candidates

    @staticmethod
    def _look_item_candidates(world: World, player_id: EntityId) -> list[Candidate]:
        """look 物品候选：房间地面、玩家栏、以及其中一层嵌套容器内的物品。

        遍历结构走共享的 ``iter_lookable_containers``（30 号票与
        ``commands._find_lookable_item`` 去重）；候选去重按规范名（同名 Stackable
        视为一堆）。遍历顺序由 holder 分组（原为 per-item 交错，候选集合不变、
        顺序变为直接容器先于其嵌套；无测试断言候选顺序）。
        """
        candidates: list[Candidate] = []
        seen: set[str] = set()
        for container in iter_lookable_containers(world, player_id):
            for item in container.items:
                identity = world.require_component(item, Identity)
                if identity.name not in seen:
                    candidates.append((identity.name, identity.aliases))
                    seen.add(identity.name)
        return candidates

    @staticmethod
    def _npc_candidates(world: World, player_id: EntityId) -> list[Candidate]:
        """同房间可 ask 的 NPC（``is_askable_npc``：Inquiry 或 NpcSpawnMeta）。

        房间内实体遍历走 ``world.entities_in_room``（34 号票去重）。
        """
        return [
            (name, aliases)
            for name, aliases, _eid in DeterministicParser._npc_entity_candidates(
                world, player_id
            )
        ]

    @staticmethod
    def _npc_entity_candidates(world: World, player_id: EntityId) -> list[EntityCandidate]:
        room = world.require_component(player_id, Position).room
        candidates: list[EntityCandidate] = []
        for entity in sorted(world.entities_in_room(room, exclude=player_id)):
            if not is_askable_npc(world, entity):
                continue
            identity = world.get_component(entity, Identity)
            if identity is not None:
                candidates.append((identity.name, identity.aliases, entity))
        return candidates

    @staticmethod
    def _combat_entity_candidates(world: World, player_id: EntityId) -> list[EntityCandidate]:
        room = world.require_component(player_id, Position).room
        candidates: list[EntityCandidate] = []
        for entity in sorted(world.entities_in_room(room, exclude=player_id)):
            identity = world.get_component(entity, Identity)
            if identity is None:
                continue
            candidates.append((identity.name, identity.aliases, entity))
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
    失败翻译成提示，不抛异常（保持 01 号票对未知命令/无匹配的行为）。
    """
    if not line.strip():
        return []

    chain = ParserChain([DeterministicParser()])
    result = chain.parse(line, world, player_id)
    if isinstance(result, Intent):
        return execute(world, player_id, result)
    return _failure_message(result)


def _index_of(tokens: list[str], word: str) -> int | None:
    """大小写不敏感找词；找不到返回 None。"""
    lower = word.lower()
    for i, token in enumerate(tokens):
        if token.lower() == lower:
            return i
    return None


def _failure_message(failure: ParseFailure) -> list[str]:
    """把结构化解析失败翻译成给玩家的一句提示。"""
    if failure.reason is Reason.UNKNOWN_VERB:
        return [f"未知命令：{failure.original}。输入 help 查看当前支持的命令列表。"]
    if failure.reason is Reason.AMBIGUOUS_TARGET:
        candidates = "、".join(failure.candidates)
        return [f"不确定你指的是哪个：{candidates}。"]
    if failure.reason is Reason.INDEX_OUT_OF_RANGE:
        name = failure.candidates[0] if failure.candidates else failure.original
        index = failure.candidates[1] if len(failure.candidates) > 1 else "?"
        return [f"这里没有第 {index} 个「{name}」。"]
    # NO_TARGET_MATCH：按命令给不同措辞。
    if failure.verb == "get":
        return [f"这里没有 {failure.original}。"]
    if failure.verb == "drop":
        return [f"你没有 {failure.original}。"]
    if failure.verb == "put":
        return [f"找不到 {failure.original}。"]
    if failure.verb == "look":
        return [f"这里没有 {failure.original}。"]
    if failure.verb in ("ask", "attack"):
        return [f"这里没有 {failure.original}。"]
    return [f"那个方向（{failure.original}）没有出口。"]  # go / 门命令 / 默认


__all__ = ["DeterministicParser", "Parser", "ParserChain", "execute_line"]
