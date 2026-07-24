"""出口方向内置同义词与展示标签（Polishing A1+A2）。

Canonical 键仍为英文十向。解析候选与 ``look`` 出口列表共用本模块数据源，
避免 ``parsing`` / ``commands`` 各写一套同义词表。
"""

from __future__ import annotations

from collections.abc import Sequence

# 方向键 → (英文简写, 中文)。自身英文全写由键提供；不含 in/out（本批十向）。
DIRECTION_FORMS: dict[str, tuple[str, str]] = {
    "north": ("n", "北"),
    "south": ("s", "南"),
    "east": ("e", "东"),
    "west": ("w", "西"),
    "northeast": ("ne", "东北"),
    "northwest": ("nw", "西北"),
    "southeast": ("se", "东南"),
    "southwest": ("sw", "西南"),
    "up": ("u", "上"),
    "down": ("d", "下"),
}


def builtin_aliases(direction: str) -> tuple[str, ...]:
    """某方向键的内置默认同义词：(英文全写, 英文简写, 中文)。未知键返回空。"""
    form = DIRECTION_FORMS.get(direction)
    if form is None:
        return ()
    short, chinese = form
    return (direction, short, chinese)


# 由 DIRECTION_FORMS 一次派生，避免英文/中文解析各扫一遍表。
_ENGLISH_BARE_TO_DIRECTION: dict[str, str] = {
    token: direction
    for direction, (short, _zh) in DIRECTION_FORMS.items()
    for token in (direction, short)
}
_CHINESE_TO_DIRECTION: dict[str, str] = {
    chinese: direction for direction, (_short, chinese) in DIRECTION_FORMS.items()
}


def resolve_english_bare(token: str) -> str | None:
    """裸英文全写/简写 → 方向键；非英文方向表内则 None。"""
    needle = token.strip().lower()
    return _ENGLISH_BARE_TO_DIRECTION.get(needle) if needle else None


def resolve_chinese_builtin(token: str) -> str | None:
    """内置中文方位 → 方向键；否则 None。"""
    needle = token.strip()
    return _CHINESE_TO_DIRECTION.get(needle) if needle else None


def has_cjk(token: str) -> bool:
    """token 是否含 CJK 统一汉字（用于区分裸中文地名 vs 裸英文绰号）。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in token)


def merge_exit_match_names(
    direction: str,
    exit_aliases: Sequence[str],
    *,
    target_name: str | None = None,
    target_aliases: Sequence[str] = (),
) -> tuple[str, ...]:
    """按层合并出口匹配名并去重（先出现者保留）。

    顺序：① 出口 ``aliases`` → ② 目标房 ``name`` / ``aliases`` → ③ 方向内置同义词。
    内置项与自定义重名时只保留一次（自定义层优先占位）。
    返回值供 ``match_target`` 作别名序列用；规范方向键仍由调用方作 canonical。
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(name: str) -> None:
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(name)

    for alias in exit_aliases:
        _add(alias)
    if target_name:
        _add(target_name)
    for alias in target_aliases:
        _add(alias)
    for name in builtin_aliases(direction):
        _add(name)
    return tuple(ordered)


def exit_display_label(direction: str) -> str:
    """``look`` 出口方向标签（不含门状态后缀）：十向为「中(english)」，其余为原键。"""
    form = DIRECTION_FORMS.get(direction)
    if form is None:
        return direction
    _short, chinese = form
    return f"{chinese}({direction})"


__all__ = [
    "DIRECTION_FORMS",
    "builtin_aliases",
    "exit_display_label",
    "has_cjk",
    "merge_exit_match_names",
    "resolve_chinese_builtin",
    "resolve_english_bare",
]
