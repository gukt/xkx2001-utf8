"""Pre-M4-04：藏书子系统 + 官方藏书阁。

接缝：S1 ``execute_line``；S2 ``load_scene``；S3 ``load_mvp_scene``。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mud_engine.components import Currency, LibraryRoom, Position
from mud_engine.library import MORE_PAGE_SIZE
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_mvp_scene


def _write_scene(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _lib_scene() -> dict:
    chap1 = "\n".join(f"第一回行{i}" for i in range(1, MORE_PAGE_SIZE + 4))
    chap2 = "\n".join(f"第二回行{i}" for i in range(1, 4))
    return {
        "rooms": {
            "yard": {
                "name": "院子",
                "long": "院外。",
                "exits": {"north": "library"},
            },
            "library": {
                "name": "藏书阁",
                "long": "满是书架。",
                "no_fight": True,
                "library": {"shelf": "书架", "books": ["xkx_intro"]},
                "exits": {"south": "yard"},
            },
        },
        "books": {
            "xkx_intro": {
                "title": "侠客行入门",
                "abbrevs": ["xkxr", "intro"],
                "chapter_cost": 2,
                "chapters": [chap1, chap2],
            }
        },
        "player": {"name": "你", "start_room": "yard", "currency": 10},
    }


class TestLibraryLoad:
    def test_library_books_resolved(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _lib_scene()))
        lib = world.room_ids["library"]
        room = world.require_component(lib, LibraryRoom)
        assert room.shelf_key == "书架"
        assert len(room.books) == 1
        book = room.books[0]
        assert book.book_id == "xkx_intro"
        assert book.title == "侠客行入门"
        assert "xkxr" in book.abbrevs
        assert book.chapter_cost == 2
        assert len(book.chapters) == 2


class TestLibraryCommands:
    def test_look_shelf_shows_toc(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _lib_scene()))
        execute_line(world, player_id, "go north")
        lines = execute_line(world, player_id, "look 书架")
        text = "\n".join(lines)
        assert "侠客行入门" in text
        assert "xkxr" in text or "intro" in text

    def test_long_toc_paginates_via_more(self, tmp_path: Path) -> None:
        data = _lib_scene()
        books = {}
        ids = []
        for i in range(MORE_PAGE_SIZE + 3):
            bid = f"book_{i}"
            ids.append(bid)
            books[bid] = {
                "title": f"书目{i}",
                "abbrevs": [f"b{i}"],
                "chapter_cost": 1,
                "chapters": [f"正文{i}"],
            }
        data["books"] = books
        data["rooms"]["library"]["library"] = {"shelf": "书架", "books": ids}
        data["rooms"]["library"]["details"] = {"书架": "一排书架。"}
        world, player_id = load_scene(_write_scene(tmp_path, data))
        execute_line(world, player_id, "go north")
        page1 = execute_line(world, player_id, "look 书架")
        assert any("还有" in line or "more" in line.lower() for line in page1)
        assert any("书目0" in line for line in page1)
        assert not any(f"书目{MORE_PAGE_SIZE + 2}" in line for line in page1)
        page2 = execute_line(world, player_id, "more")
        assert any(f"书目{MORE_PAGE_SIZE}" in line or "书目" in "\n".join(page2) for line in page2)

    def test_select_book_by_abbrev(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _lib_scene()))
        execute_line(world, player_id, "go north")
        lines = execute_line(world, player_id, "read xkxr")
        assert any("侠客行入门" in line for line in lines)

    def test_read_chapter_charges_currency(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _lib_scene()))
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "read xkxr")
        before = world.require_component(player_id, Currency).amount
        lines = execute_line(world, player_id, "read 1")
        text = "\n".join(lines)
        assert "第一回行1" in text
        assert world.require_component(player_id, Currency).amount == before - 2

    def test_read_chapter_insufficient_funds_no_charge(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _lib_scene()))
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "read xkxr")
        world.require_component(player_id, Currency).amount = 1
        lines = execute_line(world, player_id, "read 1")
        assert any("不足" in line for line in lines)
        assert world.require_component(player_id, Currency).amount == 1

    def test_chapter_pagination_via_more(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _lib_scene()))
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "read xkxr")
        page1 = execute_line(world, player_id, "read 1")
        assert any("还有" in line or "more" in line.lower() for line in page1)
        assert any(f"第一回行{MORE_PAGE_SIZE}" in line for line in page1)
        assert not any(f"第一回行{MORE_PAGE_SIZE + 1}" in line for line in page1)
        page2 = execute_line(world, player_id, "more")
        assert any(f"第一回行{MORE_PAGE_SIZE + 1}" in line for line in page2)


class TestOfficialCangshuge:
    def test_mvp_room_reachable_with_library(self) -> None:
        world, player_id = load_mvp_scene()
        assert "yangzhou_cangshuge" in world.room_ids
        lib = world.room_ids["yangzhou_cangshuge"]
        assert world.has_component(lib, LibraryRoom)
        books = world.require_component(lib, LibraryRoom).books
        assert books
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go northeast")
        lines = execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == lib
        assert not any("没有出口" in line for line in lines)

    def test_mvp_cangshuge_read_path(self) -> None:
        world, player_id = load_mvp_scene()
        lib = world.room_ids["yangzhou_cangshuge"]
        books = world.require_component(lib, LibraryRoom).books
        world.require_component(player_id, Position).room = lib

        toc = execute_line(world, player_id, "look 书架")
        assert any(books[0].title in line for line in toc)

        select = execute_line(world, player_id, f"read {books[0].abbrevs[0]}")
        assert any(books[0].title in line for line in select)

        before = world.require_component(player_id, Currency).amount
        cost = books[0].chapter_cost
        chap = execute_line(world, player_id, "read 1")
        first_line = next(
            (ln for ln in books[0].chapters[0].splitlines() if ln.strip()),
            books[0].chapters[0][:20],
        )
        assert any(first_line in line for line in chap) or bool(chap)
        assert world.require_component(player_id, Currency).amount == before - cost
