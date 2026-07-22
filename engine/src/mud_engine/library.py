"""藏书：书档解析、TOC、分页（Pre-M4-04）。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from mud_engine.components import BookDef, LibraryRoom, MoreBuffer, ReadingSession
from mud_engine.errors import SceneLoadError
from mud_engine.world import EntityId, World

MORE_PAGE_SIZE = 8


def parse_book_catalog(raw: object, scene_path: Path) -> dict[str, BookDef]:
    """解析顶层 ``books:`` 目录。"""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 'books' 段应是映射，实际是 {type(raw).__name__}"
        )
    catalog: dict[str, BookDef] = {}
    for book_id, entry in raw.items():
        bid = str(book_id)
        if not isinstance(entry, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 books['{bid}'] 应是映射，实际是 {type(entry).__name__}"
            )
        catalog[bid] = _parse_book_def(bid, entry, scene_path)
    return catalog


def _parse_book_def(book_id: str, entry: Mapping, scene_path: Path) -> BookDef:
    title = entry.get("title")
    if not title:
        raise SceneLoadError(f"场景文件 {scene_path} 的 books['{book_id}'] 缺少 'title'")
    abbrevs_raw = entry.get("abbrevs") or entry.get("abbrev") or ()
    if isinstance(abbrevs_raw, str):
        abbrevs = (abbrevs_raw,)
    elif isinstance(abbrevs_raw, (list, tuple)):
        abbrevs = tuple(str(a) for a in abbrevs_raw)
    else:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 books['{book_id}'].abbrevs 应是字符串或列表"
        )
    cost = entry.get("chapter_cost", 0)
    try:
        chapter_cost = int(cost)
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 books['{book_id}'].chapter_cost 应是整数"
        ) from exc
    if chapter_cost < 0:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 books['{book_id}'].chapter_cost 不能为负"
        )
    chapters_raw = entry.get("chapters")
    if not isinstance(chapters_raw, (list, tuple)) or not chapters_raw:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 books['{book_id}'].chapters 应是非空列表"
        )
    chapters = tuple(str(c) for c in chapters_raw)
    return BookDef(
        book_id=book_id,
        title=str(title),
        abbrevs=abbrevs,
        chapter_cost=chapter_cost,
        chapters=chapters,
    )


def resolve_library_books(
    world: World, catalog: Mapping[str, BookDef], scene_path: Path
) -> None:
    """把 ``LibraryRoom.pending_book_ids`` 解析为 ``books``。"""
    for entity in world.entities_with(LibraryRoom):
        lib = world.require_component(entity, LibraryRoom)
        if not lib.pending_book_ids:
            continue
        resolved: list[BookDef] = []
        for bid in lib.pending_book_ids:
            book = catalog.get(bid)
            if book is None:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的 library.books 引用了未定义的书档 '{bid}'"
                )
            resolved.append(book)
        lib.books = tuple(resolved)
        lib.pending_book_ids = ()


def format_toc(lib: LibraryRoom) -> list[str]:
    """书架 TOC 文案。"""
    if not lib.books:
        return ["书架上暂时没有书。"]
    lines = ["书架上陈列着这些书目："]
    for i, book in enumerate(lib.books, start=1):
        abbrev = "、".join(book.abbrevs) if book.abbrevs else book.book_id
        lines.append(f"  {i}. 《{book.title}》（缩写：{abbrev}）")
    lines.append("用法：read <缩写或书名> 选书；选书后 read <章号> 付费阅读。")
    return lines


def find_book(lib: LibraryRoom, token: str) -> BookDef | None:
    """按 id / 书名 / 缩写解析书档。"""
    needle = token.strip()
    if not needle:
        return None
    lower = needle.lower()
    for book in lib.books:
        if book.book_id.lower() == lower:
            return book
        if book.title == needle:
            return book
        for ab in book.abbrevs:
            if ab.lower() == lower:
                return book
    return None


def page_lines(lines: list[str], *, page_size: int = MORE_PAGE_SIZE) -> tuple[list[str], list[str]]:
    """切出一页；返回 (本页含提示, 剩余行)。"""
    if len(lines) <= page_size:
        return list(lines), []
    head = list(lines[:page_size])
    rest = list(lines[page_size:])
    head.append("（还有下文，输入 more 继续）")
    return head, rest


def start_more(world: World, player_id: EntityId, lines: list[str]) -> list[str]:
    """展示首屏并挂/更新 ``MoreBuffer``。"""
    shown, rest = page_lines(lines)
    existing = world.get_component(player_id, MoreBuffer)
    if rest:
        if existing is None:
            world.add_component(player_id, MoreBuffer(lines=rest))
        else:
            existing.lines = rest
    elif existing is not None:
        world.remove_component(player_id, MoreBuffer)
    return shown


def continue_more(world: World, player_id: EntityId) -> list[str]:
    """``more``：继续 ``MoreBuffer``。"""
    buf = world.get_component(player_id, MoreBuffer)
    if buf is None or not buf.lines:
        return ["没有更多内容了。"]
    return start_more(world, player_id, list(buf.lines))


def set_reading(
    world: World, player_id: EntityId, *, book_id: str, room: EntityId
) -> None:
    """选定当前书。"""
    session = world.get_component(player_id, ReadingSession)
    if session is None:
        world.add_component(player_id, ReadingSession(book_id=book_id, room=room))
    else:
        session.book_id = book_id
        session.room = room


def clear_reading(world: World, player_id: EntityId) -> None:
    if world.has_component(player_id, ReadingSession):
        world.remove_component(player_id, ReadingSession)


__all__ = [
    "MORE_PAGE_SIZE",
    "clear_reading",
    "continue_more",
    "find_book",
    "format_toc",
    "page_lines",
    "parse_book_catalog",
    "resolve_library_books",
    "set_reading",
    "start_more",
]
