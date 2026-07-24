"""房间风景 details：N1 归一、look 解析、S1 ``名(id)`` 扫描。

供 ``look`` 命令与未来客户端高亮消费。不做从 long 自动登记 aliases
（真·括号语法解析本波明确不做）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from openmud.components import DetailEntry, RoomDetails

# 半角括号内的 id；展示名由括号前缀按别名/启发式回推（见 ``scan_detail_mentions``）。
_ID_IN_PARENS_RE = re.compile(r"\(([^()\n]+)\)")

# 未命中已登记 details 时：括号前拉丁词，或连续汉字段（过长则取末两字，武侠短名惯例）。
_FALLBACK_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*$")
_FALLBACK_CJK_RE = re.compile(r"[\u4e00-\u9fff]+$")
_PUNCT_SPLIT_RE = re.compile(r"[\s'\"「」『』【】\[\]:：,，。、；;！!？?]")

# N1：空格 / ``_`` / ``-`` 与全粘连视为同一骨架；大小写不敏感。
_SEPARATORS = str.maketrans({" ": None, "_": None, "-": None})


def normalize_detail_token(token: str) -> str:
    """N1 骨架归一：去空格/``_``/``-``，再 ``casefold``。"""
    return token.translate(_SEPARATORS).casefold()


def _match_detail_key(details: RoomDetails, token: str) -> str | None:
    """N1 匹配主键或任一 alias，返回 details 主键；无命中返回 None。"""
    needle = normalize_detail_token(token)
    if not needle:
        return None
    for key, entry in details.entries.items():
        names = (key, *entry.aliases)
        if any(normalize_detail_token(name) == needle for name in names):
            return key
    return None


def resolve_detail(details: RoomDetails, token: str) -> DetailEntry | None:
    """按键或任一 alias 做 N1 归一匹配；多条命中时取首次登记的那条。"""
    key = _match_detail_key(details, token)
    return details.entries[key] if key is not None else None


@dataclass(frozen=True)
class DetailMention:
    """可见文本里一处 ``名(id)`` 扫描结果（供客户端高亮/可点判定）。"""

    display: str
    raw_id: str
    start: int
    end: int
    lookable: bool
    detail_key: str | None


def _fallback_display(before: str) -> str:
    """未登记形态：按标点切开后取末段；连续汉字过长时取末两字。"""
    segment = _PUNCT_SPLIT_RE.split(before)[-1]
    latin = _FALLBACK_LATIN_RE.search(segment)
    if latin:
        return latin.group(0)
    cjk = _FALLBACK_CJK_RE.search(segment)
    if cjk:
        run = cjk.group(0)
        return run if len(run) <= 2 else run[-2:]
    return segment


def _display_before_paren(
    before: str, *, detail_key: str | None, details: RoomDetails
) -> str:
    """从 ``(`` 前回推展示名：优先最长匹配的已登记键/别名后缀，否则启发式短名。"""
    if detail_key is not None:
        entry = details.entries[detail_key]
        candidates = sorted({detail_key, *entry.aliases}, key=len, reverse=True)
        for cand in candidates:
            if cand and before.endswith(cand):
                return cand
    return _fallback_display(before)


def scan_detail_mentions(text: str, details: RoomDetails) -> list[DetailMention]:
    """扫描 ``名(id)``；仅当 id（经 N1）命中本房已登记 details 时 ``lookable=True``（S1）。

    无展示名可回推的裸 ``(…)`` 不计入 mention（避免误伤普通括号）。
    """
    hits: list[DetailMention] = []
    for match in _ID_IN_PARENS_RE.finditer(text):
        raw_id = match.group(1)
        detail_key = _match_detail_key(details, raw_id)
        before = text[: match.start()]
        display = _display_before_paren(
            before, detail_key=detail_key, details=details
        )
        if not display:
            continue
        hits.append(
            DetailMention(
                display=display,
                raw_id=raw_id,
                start=match.start() - len(display),
                end=match.end(),
                lookable=detail_key is not None,
                detail_key=detail_key,
            )
        )
    return hits
