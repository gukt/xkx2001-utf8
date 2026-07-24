"""通用别名匹配工具：给定玩家输入 token 与候选集合，找出匹配的规范名。

与具体目标类型无关--出口方向、物品、（未来）NPC 都用同一套，是 02 号票
落地、03（物品）/04（门）号票直接复用的共享机制（不为目标类型各写一套判断，
见 M1 spec「命令解析」与 02 号票 acceptance）。

匹配规则：

- 大小写不敏感（玩家输入大小写都算）。
- 规范名与别名**同权**：输入命中规范名或任一别名都算命中该候选。
- 多候选同时命中判歧义（``Ambiguous``）；无任何命中判无匹配（``NoMatch``）。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Resolved:
    """唯一命中：玩家输入对应到这个规范名。"""

    canonical: str


@dataclass(frozen=True)
class ResolvedEntity:
    """唯一命中到具体实体（M2-20 同名消歧）。"""

    canonical: str
    entity_id: int


@dataclass(frozen=True)
class NoMatch:
    """无任何候选命中。保留原始 token 供调用方生成提示。"""

    token: str


@dataclass(frozen=True)
class Ambiguous:
    """输入同时命中多个候选：规范名都列出，让调用方决定如何提示。"""

    canonicals: tuple[str, ...]


@dataclass(frozen=True)
class IndexOutOfRange:
    """带序号匹配时序号超出该名下实例数。"""

    name: str
    index: int
    count: int


MatchResult = Resolved | NoMatch | Ambiguous
EntityMatchResult = ResolvedEntity | NoMatch | Ambiguous | IndexOutOfRange

# 每个候选 = (规范名, 别名序列)。别名序列可为空。
Candidate = tuple[str, Sequence[str]]
# 带实体引用的候选（同名多实例消歧）。
EntityCandidate = tuple[str, Sequence[str], int]


def match_target(token: str, candidates: Iterable[Candidate]) -> MatchResult:
    """在候选集合里匹配输入 token，返回 ``Resolved`` / ``NoMatch`` / ``Ambiguous``。

    candidates 每项是 ``(规范名, 别名序列)``；规范名与别名都参与匹配。空白
    token（玩家只输了空格）直接判 ``NoMatch``，不当作合法目标。
    """
    needle = token.strip().lower()
    if not needle:
        return NoMatch(token)

    hits: list[str] = []
    for canonical, aliases in candidates:
        names = (canonical, *aliases)
        if any(name.lower() == needle for name in names):
            hits.append(canonical)

    if not hits:
        return NoMatch(token)
    if len(hits) == 1:
        return Resolved(hits[0])
    return Ambiguous(tuple(hits))


def _split_name_and_index(token: str) -> tuple[str, int | None]:
    """``巡逻兵 2`` → ``("巡逻兵", 2)``；无末尾数字则 index=None。"""
    parts = token.strip().split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return " ".join(parts[:-1]), int(parts[-1])
    return token.strip(), None


def match_entity_target(
    token: str, candidates: Iterable[EntityCandidate]
) -> EntityMatchResult:
    """按名（+可选 1-based 序号）匹配到具体实体。

    - 无序号且唯一命中 → ``ResolvedEntity``
    - 无序号且多命中 → ``Ambiguous``（不静默取第一个）
    - 有序号 → 同名实例按 ``entity_id`` 升序取第 N 个；越界 → ``IndexOutOfRange``
    """
    name_part, index = _split_name_and_index(token)
    needle = name_part.lower()
    if not needle:
        return NoMatch(token)

    hits: list[tuple[str, int]] = []
    for canonical, aliases, entity_id in candidates:
        names = (canonical, *aliases)
        if any(name.lower() == needle for name in names):
            hits.append((canonical, entity_id))

    if not hits:
        return NoMatch(token)

    hits.sort(key=lambda h: h[1])  # 按 entity_id 确定性排序

    if index is None:
        # 无序号：多规范名或同名多实例都算歧义
        if len(hits) == 1:
            return ResolvedEntity(canonical=hits[0][0], entity_id=hits[0][1])
        return Ambiguous(tuple(h[0] for h in hits))

    if index < 1 or index > len(hits):
        return IndexOutOfRange(name=name_part, index=index, count=len(hits))
    chosen = hits[index - 1]
    return ResolvedEntity(canonical=chosen[0], entity_id=chosen[1])


__all__ = [
    "Ambiguous",
    "Candidate",
    "EntityCandidate",
    "EntityMatchResult",
    "IndexOutOfRange",
    "MatchResult",
    "NoMatch",
    "Resolved",
    "ResolvedEntity",
    "match_entity_target",
    "match_target",
]
