"""Pre-M4-02：语义色 token 校验 + CLI 渲染（ADR-0011）。

接缝：S2 ``load_scene`` / validate；S1 ``execute_line`` 权威回文保留 token；
CLI 适配层 ``run_repl(..., color=...)``。
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from openmud.cli import run_repl
from openmud.errors import SceneLoadError
from openmud.parsing import execute_line
from openmud.scene_loader import load_scene
from openmud.semantic_color import render_ansi, strip_tokens, validate_markup


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _scene_with_long(long: str) -> str:
    return f"""rooms:
  yard:
    name: 院子
    long: {long!r}
    exits: {{}}
player:
  name: 你
  start_room: yard
"""


class TestValidateMarkup:
    def test_allows_seven_colors(self) -> None:
        for name in ("red", "green", "yellow", "blue", "magenta", "cyan", "white"):
            validate_markup(f"<c:{name}>字</c>", location="t")

    def test_rejects_unknown_color(self) -> None:
        with pytest.raises(SceneLoadError, match="未知色名"):
            validate_markup("<c:purple>字</c>", location="t")

    def test_rejects_unclosed(self) -> None:
        with pytest.raises(SceneLoadError, match="未闭合"):
            validate_markup("<c:green>字", location="t")

    def test_rejects_nested(self) -> None:
        with pytest.raises(SceneLoadError, match="嵌套"):
            validate_markup("<c:green><c:red>字</c></c>", location="t")

    def test_rejects_ansi_escape(self) -> None:
        with pytest.raises(SceneLoadError, match="ANSI"):
            validate_markup("\x1b[32m绿\x1b[0m", location="t")

    def test_rejects_lpc_macro(self) -> None:
        with pytest.raises(SceneLoadError, match="LPC"):
            validate_markup("HIG草绿NOR", location="t")


class TestLoadRejectsBadMarkup:
    def test_bad_color_in_long_fails_load(self, tmp_path: Path) -> None:
        with pytest.raises(SceneLoadError, match="未知色名"):
            load_scene(_write_scene(tmp_path, _scene_with_long("<c:purple>坏</c>")))

    def test_ansi_in_details_fails_load(self, tmp_path: Path) -> None:
        # YAML 双引号 ``\x1b`` 解成 ESC；加载期 validate 拒 ANSI。
        path = tmp_path / "scene.yaml"
        path.write_text(
            "rooms:\n  yard:\n    name: 院子\n    long: ok\n    details:\n"
            '      牌: "\\x1b[31m红\\x1b[0m"\n    exits: {}\n'
            "player:\n  name: 你\n  start_room: yard\n",
            encoding="utf-8",
        )
        with pytest.raises(SceneLoadError, match="ANSI"):
            load_scene(path)

    def test_bad_color_in_npc_long_fails_load(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    long: ok
    exits: {}
    objects:
      guard: 1
npcs:
  guard:
    name: 守卫
    long: <c:purple>坏色</c>
    inquiry:
      default: 哼。
player:
  name: 你
  start_room: yard
"""
        with pytest.raises(SceneLoadError, match="未知色名"):
            load_scene(_write_scene(tmp_path, scene))


class TestAuthorityKeepsTokens:
    def test_look_detail_keeps_semantic_tokens(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    long: 院子里有棵树。
    details:
      树: <c:green>一棵青松</c>
    exits: {}
player:
  name: 你
  start_room: yard
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "look 树")
        assert any("<c:green>" in line and "</c>" in line for line in lines)
        assert not any("\x1b[" in line for line in lines)


class TestStripAndRender:
    def test_strip_removes_tokens(self) -> None:
        assert strip_tokens("<c:green>青松</c>") == "青松"

    def test_render_bright_ansi(self) -> None:
        out = render_ansi("<c:green>青松</c>")
        assert "\x1b[92m" in out
        assert "\x1b[0m" in out
        assert "青松" in out
        assert "<c:" not in out


class TestCliColorAdapter:
    def test_default_strips_tokens(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    long: <c:green>青砖院</c>
    exits: {}
player:
  name: 你
  start_room: yard
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        out = io.StringIO()
        run_repl(world, player_id, input_stream=io.StringIO("quit\n"), output_stream=out)
        text = out.getvalue()
        assert "青砖院" in text
        assert "<c:green>" not in text
        assert "\x1b[" not in text

    def test_color_true_renders_ansi(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    long: <c:green>青砖院</c>
    exits: {}
player:
  name: 你
  start_room: yard
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        out = io.StringIO()
        run_repl(
            world,
            player_id,
            input_stream=io.StringIO("quit\n"),
            output_stream=out,
            color=True,
        )
        text = out.getvalue()
        assert "\x1b[92m" in text
        assert "青砖院" in text
        assert "<c:green>" not in text
