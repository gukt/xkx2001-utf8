"""pilot 样本 id=9：bboard.c:do_read 迁移单元测试。

覆盖读帖主路径 + 关键门控：wizard_only/poster_family 权限门控、notes 空、
arg 空、sscanf 失败、num 越界、new/next 未读定位、board_last_read 更新
（首次 set / 更大时间更新 / 更小时间不更新）。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.bboard_c_do_read import (
    BoardItem,
    BoardLastRead,
    Note,
    bboard_c_do_read,
)
from tools.sampling.pilot.stubs import start_more

from xkx.runtime.capability import WizLevel
from xkx.runtime.commands import Game
from xkx.runtime.components import Attributes, Identity, Position
from xkx.runtime.ecs import World


def _game(
    *,
    player_family: str = "明教",
    notes: list[Note] | None = None,
    board_id: str = "mingjiao_board",
    wizard_only: bool = False,
    poster_family: str | None = None,
    last_read: dict[str, int] | None = None,
) -> tuple[Game, int, BoardItem]:
    """构造 1 玩家 + 1 留言板的最小场景。"""
    world = World()

    player = world.new_entity()
    world.add(player, Identity(
        name="玩家", aliases=["player"], is_player=True, prototype_id="player"
    ))
    world.add(player, Position(room_id="room/test"))
    world.add(player, Attributes(family=player_family, gender="男性", int_=20))
    if last_read is not None:
        world.add(player, BoardLastRead(records=dict(last_read)))

    if notes is None:
        notes = [
            Note(title="第一帖", author="张无忌", time=1000, msg="正文一"),
            Note(title="第二帖", author="韦一笑", time=2000, msg="正文二"),
        ]
    board = BoardItem(
        board_id=board_id,
        notes=notes,
        wizard_only=wizard_only,
        poster_family=poster_family,
    )
    return Game(world, {}, rules=[]), player, board


def _last_read(world: World, eid: int) -> dict[str, int]:
    rec = world.get(eid, BoardLastRead)
    return dict(rec.records) if rec is not None else {}


def test_read_by_number_success() -> None:
    """按号读帖：返回 start_more 包装的留言正文。"""
    game, player, board = _game()
    msgs = bboard_c_do_read(game, player, board, "1")
    # time.ctime(1000) = 'Thu Jan  1 08:16:40 1970'，[0:10] = 'Thu Jan  1'
    # 与实现同构构造期望串，避免手数 %-40s 的空格填充
    expected = (
        f"[1] {'第一帖':<40} 张无忌(Thu Jan  1)\n"
        "----------------------------------------------------------------------\n"
        "正文一"
    )
    assert msgs == start_more(expected)


def test_wizard_only_blocks_mortal(monkeypatch: Any) -> None:
    """wizard_only 板且玩家非 immortal -> 拒绝窥视。"""
    game, player, board = _game(wizard_only=True)
    # cmp_wiz_level 默认 PLAYER < IMMORTAL -> <0 -> 拒绝（无需 monkeypatch）
    assert bboard_c_do_read(game, player, board, "1") == ["内部通讯不得窥视。\n"]


def test_wizard_allows_immortal(monkeypatch: Any) -> None:
    """wizard_only 板但玩家为 immortal -> 放行读帖。"""
    game, player, board = _game(wizard_only=True)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.bboard_c_do_read._entity_wiz_level",
        lambda _world, _eid: WizLevel.IMMORTAL,
    )
    msgs = bboard_c_do_read(game, player, board, "1")
    assert "正文一" in msgs[0]


def test_empty_notes_fails() -> None:
    """notes 为空 -> 拒绝。"""
    game, player, board = _game(notes=[])
    assert bboard_c_do_read(game, player, board, "1") == [
        "留言板上目前没有任何留言。\n"
    ]


def test_poster_family_blocks_outsider() -> None:
    """poster_family 限定且玩家非本派非 immortal -> 拒绝。"""
    game, player, board = _game(
        player_family="雪山派", poster_family="明教"
    )
    assert bboard_c_do_read(game, player, board, "1") == [
        "非本派弟子不得窥视本派内部通讯。\n"
    ]


def test_poster_family_allows_member() -> None:
    """poster_family 限定但玩家本派匹配 -> 放行。"""
    game, player, board = _game(player_family="明教", poster_family="明教")
    msgs = bboard_c_do_read(game, player, board, "1")
    assert "正文一" in msgs[0]


def test_poster_family_allows_immortal(monkeypatch: Any) -> None:
    """poster_family 限定但玩家为 immortal -> 放行（即使门派不匹配）。"""
    game, player, board = _game(
        player_family="雪山派", poster_family="明教"
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.bboard_c_do_read._entity_wiz_level",
        lambda _world, _eid: WizLevel.IMMORTAL,
    )
    msgs = bboard_c_do_read(game, player, board, "1")
    assert "正文一" in msgs[0]


def test_no_arg_fails() -> None:
    """arg 为空 -> 格式提示。"""
    game, player, board = _game()
    assert bboard_c_do_read(game, player, board, None) == [
        "指令格式：read <留言编号>|new|next\n"
    ]


def test_sscanf_fail_fails() -> None:
    """arg 非数字非 new/next -> 失败。"""
    game, player, board = _game()
    assert bboard_c_do_read(game, player, board, "abc") == [
        "你要读第几张留言？\n"
    ]


def test_num_out_of_range_fails() -> None:
    """num 越界 -> 拒绝。"""
    game, player, board = _game()
    assert bboard_c_do_read(game, player, board, "0") == ["没有这张留言。\n"]
    assert bboard_c_do_read(game, player, board, "3") == ["没有这张留言。\n"]


def test_new_first_read_starts_at_one() -> None:
    """new 且无 last_read 记录 -> 从第 1 张读起。"""
    game, player, board = _game()
    msgs = bboard_c_do_read(game, player, board, "new")
    assert "第一帖" in msgs[0]


def test_new_locates_first_unread() -> None:
    """new 且 last_read 记录存在 -> 定位第一张未读。"""
    game, player, board = _game(
        last_read={"mingjiao_board": 1000}
    )
    msgs = bboard_c_do_read(game, player, board, "new")
    # 第二帖 time=2000 > 1000 -> 第一张未读为第 2 张
    assert "第二帖" in msgs[0]


def test_next_same_as_new() -> None:
    """next 与 new 等价定位未读。"""
    game, player, board = _game(
        last_read={"mingjiao_board": 1000}
    )
    msgs = bboard_c_do_read(game, player, board, "next")
    assert "第二帖" in msgs[0]


def test_new_all_read_out_of_range() -> None:
    """new 且所有帖都已读（last_read >= 末帖 time）-> num 越界，无新帖。"""
    game, player, board = _game(
        last_read={"mingjiao_board": 2000}
    )
    assert bboard_c_do_read(game, player, board, "new") == ["没有这张留言。\n"]


def test_last_read_set_on_first_read() -> None:
    """首次读帖（无 BoardLastRead 组件）-> 创建并记录该 board 时间。"""
    game, player, board = _game()
    assert game.world.get(player, BoardLastRead) is None
    bboard_c_do_read(game, player, board, "2")
    assert _last_read(game.world, player) == {"mingjiao_board": 2000}


def test_last_read_updates_with_larger_time() -> None:
    """读更新的帖 -> last_read[myid] 更新为更大时间。"""
    game, player, board = _game(
        last_read={"mingjiao_board": 500}
    )
    bboard_c_do_read(game, player, board, "2")
    assert _last_read(game.world, player) == {"mingjiao_board": 2000}


def test_last_read_keeps_smaller_time() -> None:
    """读更旧的帖 -> last_read[myid] 保持原更大时间不变。"""
    game, player, board = _game(
        last_read={"mingjiao_board": 3000}
    )
    bboard_c_do_read(game, player, board, "1")
    assert _last_read(game.world, player) == {"mingjiao_board": 3000}


def test_last_read_preserves_other_boards() -> None:
    """更新一个 board 记录时保留其他 board 的记录。"""
    game, player, board = _game(
        last_read={"other_board": 999, "mingjiao_board": 500}
    )
    bboard_c_do_read(game, player, board, "2")
    rec = _last_read(game.world, player)
    assert rec["other_board"] == 999
    assert rec["mingjiao_board"] == 2000
