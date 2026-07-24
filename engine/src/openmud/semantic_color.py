"""语义色 token（ADR-0011）：校验、剥离、CLI 亮色 ANSI 渲染。

权威文本语法：``<c:name>…</c>``；允许色名仅七色。核心层保留 token；
渲染只在 CLI 适配层。禁止 ANSI 转义、LPC 色宏、嵌套、未知色名、未闭合。
"""

from __future__ import annotations

import re
from collections.abc import Callable

from openmud.errors import SceneLoadError

ALLOWED_COLORS: frozenset[str] = frozenset(
    {"red", "green", "yellow", "blue", "magenta", "cyan", "white"}
)

# 亮色 ANSI（30–37 为暗色；90–97 为亮色）。
_BRIGHT_ANSI: dict[str, str] = {
    "red": "\x1b[91m",
    "green": "\x1b[92m",
    "yellow": "\x1b[93m",
    "blue": "\x1b[94m",
    "magenta": "\x1b[95m",
    "cyan": "\x1b[96m",
    "white": "\x1b[97m",
}
_RESET = "\x1b[0m"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]")
# 常见 LPC 色宏（ASCII 整词；与中文邻接时仍命中，如 HIG草绿NOR）。
_LPC_MACRO_RE = re.compile(
    r"(?<![A-Za-z])(?:HIG|HIR|HIB|HIM|HIC|HIW|HIK|NOR|RED|GRN|YEL|BLU|MAG|CYN|WHT|BLK)(?![A-Za-z])"
)
_OPEN_RE = re.compile(r"<c:([a-zA-Z]+)>")
_CLOSE = "</c>"


def validate_markup(text: str, *, location: str) -> None:
    """校验文本不含非法着色写法；通过则无返回，失败抛 ``SceneLoadError``。"""
    if _ANSI_RE.search(text):
        raise SceneLoadError(f"{location} 含原始 ANSI 转义，请改用 <c:name>…</c>")
    if _LPC_MACRO_RE.search(text):
        raise SceneLoadError(f"{location} 含 LPC 色宏，请改用 <c:name>…</c>")
    _walk(text, location=location, on_span=None)


def strip_tokens(text: str) -> str:
    """剥除语义色 token，留下纯文本（管道 / 测试默认路径）。"""
    parts: list[str] = []

    def on_span(plain: str, _color: str | None) -> None:
        parts.append(plain)

    _walk(text, location="strip", on_span=on_span)
    return "".join(parts)


def render_ansi(text: str) -> str:
    """将语义色 token 映为亮色 ANSI（TTY / ``--color``）。"""
    parts: list[str] = []

    def on_span(plain: str, color: str | None) -> None:
        if color is None:
            parts.append(plain)
        else:
            parts.append(f"{_BRIGHT_ANSI[color]}{plain}{_RESET}")

    _walk(text, location="render", on_span=on_span)
    return "".join(parts)


def _walk(
    text: str,
    *,
    location: str,
    on_span: Callable[[str, str | None], None] | None,
) -> None:
    """顺序扫描：非嵌套 ``<c:name>…</c>``；``on_span(plain, color|None)`` 可选。"""
    pos = 0
    n = len(text)
    while pos < n:
        open_match = _OPEN_RE.search(text, pos)
        if open_match is None:
            plain = text[pos:]
            if on_span is not None and plain:
                on_span(plain, None)
            # 残留的孤立 </c>
            if _CLOSE in plain:
                raise SceneLoadError(f"{location} 语义色 token 未正确配对（多余 </c>）")
            return

        # open 前的纯文本
        if open_match.start() > pos:
            plain = text[pos : open_match.start()]
            if _CLOSE in plain:
                raise SceneLoadError(f"{location} 语义色 token 未正确配对（多余 </c>）")
            if on_span is not None:
                on_span(plain, None)

        color = open_match.group(1).lower()
        if color not in ALLOWED_COLORS:
            raise SceneLoadError(
                f"{location} 未知色名 {open_match.group(1)!r}；"
                f"允许：{', '.join(sorted(ALLOWED_COLORS))}"
            )

        content_start = open_match.end()
        close_at = text.find(_CLOSE, content_start)
        if close_at < 0:
            raise SceneLoadError(f"{location} 语义色 token 未闭合（缺少 </c>）")
        inner = text[content_start:close_at]
        if _OPEN_RE.search(inner) or _CLOSE in inner:
            raise SceneLoadError(f"{location} 不支持嵌套语义色 token")
        if on_span is not None:
            on_span(inner, color)
        pos = close_at + len(_CLOSE)


__all__ = [
    "ALLOWED_COLORS",
    "render_ansi",
    "strip_tokens",
    "validate_markup",
]
