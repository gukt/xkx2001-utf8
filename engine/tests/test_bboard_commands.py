"""bboard_commands 引擎层单测（ADR-0059 务实合一）。

覆盖 do_read（从 pilot 18 测试迁移，行为等价）+ do_list（空板/列表/未读高亮/
权限门控）+ do_discard（作者删帖+save 闭环/非作者拒绝/caretaker 放行/越界/
sscanf 失败/无 store 跳过/save 往返/arg 空/token=None）。

用真实 ``PermissionService().issue_token`` + ``cmp_wiz_level`` 构造权限场景
（不 monkeypatch 桩，体现合一核心价值）。
"""

from __future__ import annotations

from typing import Any

from xkx.runtime.action_context import new_context
from xkx.runtime.bboard_commands import do_discard, do_list, do_read
from xkx.runtime.capability import CapabilityToken, PermissionService, WizLevel
from xkx.runtime.commands import Game
from xkx.runtime.components import (
    Attributes,
    BoardLastRead,
    Identity,
    Position,
)
from xkx.runtime.daemon_store import DaemonStore
from xkx.runtime.daemons.bboard import BboardData, Note
from xkx.runtime.ecs import World

# ──────────────────────── 测试辅助 ────────────────────────


def _game(
    *,
    player_family: str = "明教",
    notes: list[Note] | None = None,
    board_id: str = "mingjiao_board",
    wizard_only: bool = False,
    poster_family: str | None = None,
    last_read: dict[str, int] | None = None,
) -> tuple[Game, int, BboardData]:
    """构造 1 玩家 + 1 留言板的最小场景（do_read/do_list 用）。"""
    world = World()
    player = world.new_entity()
    world.add(
        player,
        Identity(
            name="玩家",
            aliases=["player"],
            is_player=True,
            prototype_id="player",
        ),
    )
    world.add(player, Position(room_id="room/test"))
    world.add(player, Attributes(family=player_family, gender="男性", int_=20))
    if last_read is not None:
        world.add(player, BoardLastRead(records=dict(last_read)))
    if notes is None:
        notes = [
            Note(title="第一帖", author="张无忌", time=1000, msg="正文一"),
            Note(title="第二帖", author="韦一笑", time=2000, msg="正文二"),
        ]
    board = BboardData(
        board_id=board_id,
        notes=notes,
        wizard_only=wizard_only,
        poster_family=poster_family,
    )
    return Game(world, {}, rules=[]), player, board


def _game_for_discard(
    *,
    notes: list[Note] | None = None,
    board_id: str = "test_board",
) -> tuple[Game, int, BboardData]:
    """构造 do_discard 专用场景（author 用 name(id) 格式）。"""
    world = World()
    player = world.new_entity()
    world.add(
        player,
        Identity(
            name="玩家",
            aliases=["player"],
            is_player=True,
            prototype_id="player",
        ),
    )
    world.add(player, Position(room_id="room/test"))
    world.add(player, Attributes(family="明教", gender="男性", int_=20))
    if notes is None:
        notes = [
            Note(title="第一帖", author="玩家(player)", time=1000, msg="正文一"),
            Note(title="第二帖", author="他人(other)", time=2000, msg="正文二"),
        ]
    board = BboardData(board_id=board_id, notes=notes)
    return Game(world, {}, rules=[]), player, board


def _token(eid: int, level: WizLevel = WizLevel.PLAYER) -> CapabilityToken:
    """构造真实能力令牌（体现合一：用 PermissionService，不 monkeypatch）。"""
    return PermissionService().issue_token(eid, level)


def _ctx(
    actor: int,
    *,
    raw_args: str = "",
    token: CapabilityToken | None = None,
    verb: str = "read",
):
    """构造 ActionContext（raw_args 为参数源）。"""
    return new_context(
        verb=verb, raw_args=raw_args, actor=actor, capability_token=token
    )


def _last_read(world: World, eid: int) -> dict[str, int]:
    rec = world.get(eid, BoardLastRead)
    return dict(rec.records) if rec is not None else {}


# ──────────────────────── do_read ────────────────────────


def test_read_by_number_success() -> None:
    """按号读帖：返回 start_more 包装的留言正文。"""
    game, player, board = _game()
    ctx = _ctx(player, raw_args="1", token=_token(player))
    msgs = do_read(game, ctx, board)
    # time.ctime(1000) = 'Thu Jan  1 08:16:40 1970'，[0:10] = 'Thu Jan  1'
    expected = (
        f"[1] {'第一帖':<40} 张无忌(Thu Jan  1)\n"
        "----------------------------------------------------------------------\n"
        "正文一"
    )
    assert msgs == [expected]


def test_wizard_only_blocks_mortal() -> None:
    """wizard_only 板且玩家非 immortal -> 拒绝窥视。"""
    game, player, board = _game(wizard_only=True)
    ctx = _ctx(player, raw_args="1", token=_token(player, WizLevel.PLAYER))
    assert do_read(game, ctx, board) == ["内部通讯不得窥视。\n"]


def test_wizard_allows_immortal() -> None:
    """wizard_only 板但玩家为 immortal -> 放行读帖。"""
    game, player, board = _game(wizard_only=True)
    ctx = _ctx(player, raw_args="1", token=_token(player, WizLevel.IMMORTAL))
    msgs = do_read(game, ctx, board)
    assert "正文一" in msgs[0]


def test_empty_notes_fails() -> None:
    """notes 为空 -> 拒绝。"""
    game, player, board = _game(notes=[])
    ctx = _ctx(player, raw_args="1", token=_token(player))
    assert do_read(game, ctx, board) == ["留言板上目前没有任何留言。\n"]


def test_poster_family_blocks_outsider() -> None:
    """poster_family 限定且玩家非本派非 immortal -> 拒绝。"""
    game, player, board = _game(player_family="雪山派", poster_family="明教")
    ctx = _ctx(player, raw_args="1", token=_token(player))
    assert do_read(game, ctx, board) == ["非本派弟子不得窥视本派内部通讯。\n"]


def test_poster_family_allows_member() -> None:
    """poster_family 限定但玩家本派匹配 -> 放行。"""
    game, player, board = _game(player_family="明教", poster_family="明教")
    ctx = _ctx(player, raw_args="1", token=_token(player))
    msgs = do_read(game, ctx, board)
    assert "正文一" in msgs[0]


def test_poster_family_allows_immortal() -> None:
    """poster_family 限定但玩家为 immortal -> 放行（即使门派不匹配）。"""
    game, player, board = _game(player_family="雪山派", poster_family="明教")
    ctx = _ctx(player, raw_args="1", token=_token(player, WizLevel.IMMORTAL))
    msgs = do_read(game, ctx, board)
    assert "正文一" in msgs[0]


def test_no_arg_fails() -> None:
    """arg 为空 -> 格式提示。"""
    game, player, board = _game()
    ctx = _ctx(player, raw_args="", token=_token(player))
    assert do_read(game, ctx, board) == ["指令格式：read <留言编号>|new|next\n"]


def test_sscanf_fail_fails() -> None:
    """arg 非数字非 new/next -> 失败。"""
    game, player, board = _game()
    ctx = _ctx(player, raw_args="abc", token=_token(player))
    assert do_read(game, ctx, board) == ["你要读第几张留言？\n"]


def test_num_out_of_range_fails() -> None:
    """num 越界 -> 拒绝。"""
    game, player, board = _game()
    ctx0 = _ctx(player, raw_args="0", token=_token(player))
    ctx3 = _ctx(player, raw_args="3", token=_token(player))
    assert do_read(game, ctx0, board) == ["没有这张留言。\n"]
    assert do_read(game, ctx3, board) == ["没有这张留言。\n"]


def test_new_first_read_starts_at_one() -> None:
    """new 且无 last_read 记录 -> 从第 1 张读起。"""
    game, player, board = _game()
    ctx = _ctx(player, raw_args="new", token=_token(player))
    msgs = do_read(game, ctx, board)
    assert "第一帖" in msgs[0]


def test_new_locates_first_unread() -> None:
    """new 且 last_read 记录存在 -> 定位第一张未读。"""
    game, player, board = _game(last_read={"mingjiao_board": 1000})
    ctx = _ctx(player, raw_args="new", token=_token(player))
    msgs = do_read(game, ctx, board)
    # 第二帖 time=2000 > 1000 -> 第一张未读为第 2 张
    assert "第二帖" in msgs[0]


def test_next_same_as_new() -> None:
    """next 与 new 等价定位未读。"""
    game, player, board = _game(last_read={"mingjiao_board": 1000})
    ctx = _ctx(player, raw_args="next", token=_token(player))
    msgs = do_read(game, ctx, board)
    assert "第二帖" in msgs[0]


def test_new_all_read_out_of_range() -> None:
    """new 且所有帖都已读（last_read >= 末帖 time）-> num 越界，无新帖。"""
    game, player, board = _game(last_read={"mingjiao_board": 2000})
    ctx = _ctx(player, raw_args="new", token=_token(player))
    assert do_read(game, ctx, board) == ["没有这张留言。\n"]


def test_last_read_set_on_first_read() -> None:
    """首次读帖（无 BoardLastRead 组件）-> 创建并记录该 board 时间。"""
    game, player, board = _game()
    assert game.world.get(player, BoardLastRead) is None
    ctx = _ctx(player, raw_args="2", token=_token(player))
    do_read(game, ctx, board)
    assert _last_read(game.world, player) == {"mingjiao_board": 2000}


def test_last_read_updates_with_larger_time() -> None:
    """读更新的帖 -> last_read[myid] 更新为更大时间。"""
    game, player, board = _game(last_read={"mingjiao_board": 500})
    ctx = _ctx(player, raw_args="2", token=_token(player))
    do_read(game, ctx, board)
    assert _last_read(game.world, player) == {"mingjiao_board": 2000}


def test_last_read_keeps_smaller_time() -> None:
    """读更旧的帖 -> last_read[myid] 保持原更大时间不变。"""
    game, player, board = _game(last_read={"mingjiao_board": 3000})
    ctx = _ctx(player, raw_args="1", token=_token(player))
    do_read(game, ctx, board)
    assert _last_read(game.world, player) == {"mingjiao_board": 3000}


def test_last_read_preserves_other_boards() -> None:
    """更新一个 board 记录时保留其他 board 的记录。"""
    game, player, board = _game(
        last_read={"other_board": 999, "mingjiao_board": 500}
    )
    ctx = _ctx(player, raw_args="2", token=_token(player))
    do_read(game, ctx, board)
    rec = _last_read(game.world, player)
    assert rec["other_board"] == 999
    assert rec["mingjiao_board"] == 2000


def test_read_none_token_fail_closed() -> None:
    """token=None fail-closed：wizard_only 板拒绝（不变量 1）。"""
    game, player, board = _game(wizard_only=True)
    ctx = _ctx(player, raw_args="1", token=None)
    assert do_read(game, ctx, board) == ["内部通讯不得窥视。\n"]


# ──────────────────────── do_list ────────────────────────


def test_list_empty_notes() -> None:
    """空板提示。"""
    game, player, board = _game(notes=[])
    ctx = _ctx(player, verb="list", token=_token(player))
    assert do_list(game, ctx, board) == ["留言板上目前没有任何留言。\n"]


def test_list_shows_notes_and_header() -> None:
    """列标题 + 帖子列表。"""
    game, player, board = _game()
    ctx = _ctx(player, verb="list", token=_token(player))
    msg = do_list(game, ctx, board)[0]
    assert "mingjiao_board" in msg
    assert "第一帖" in msg
    assert "第二帖" in msg
    assert "[ 1]" in msg
    assert "[ 2]" in msg


def test_list_marks_unread() -> None:
    """未读帖高亮标记 * 存在。"""
    game, player, board = _game(last_read={"mingjiao_board": 1000})
    ctx = _ctx(player, verb="list", token=_token(player))
    msg = do_list(game, ctx, board)[0]
    # 第一帖 time=1000，last=1000，不大于 -> 已读（无 *）
    # 第二帖 time=2000，last=1000，大于 -> 未读（有 *）
    assert "*[ 2]" in msg
    assert " [ 1]" in msg


def test_list_wizard_only_visible_to_mortal() -> None:
    """行为等价：LPC do_list 无门控，wizard_only 板标题列表凡人可见。

    LPC short/long/do_list 均无 wizard_only 检查，仅读正文 do_read 才拒。
    引擎层严格对齐（不擅自补门控，ADR-0059）。
    """
    game, player, board = _game(wizard_only=True)
    ctx = _ctx(player, verb="list", token=_token(player))
    msg = do_list(game, ctx, board)[0]
    assert "第一帖" in msg


def test_list_poster_family_visible_to_outsider() -> None:
    """行为等价：LPC do_list 无门控，poster_family 板标题列表外人可见。"""
    game, player, board = _game(player_family="雪山派", poster_family="明教")
    ctx = _ctx(player, verb="list", token=_token(player))
    msg = do_list(game, ctx, board)[0]
    assert "第一帖" in msg


# ──────────────────────── do_discard ────────────────────────


def test_discard_own_note_saves(tmp_path: Any) -> None:
    """作者删自己帖成功 + save 闭环（存档文件生成 + notes 少一条）。"""
    game, player, board = _game_for_discard()
    store = DaemonStore(str(tmp_path))
    store.register("bboard_test_board", board)
    game.world.daemon_store = store
    ctx = _ctx(player, raw_args="1", verb="discard", token=_token(player))
    msgs = do_discard(game, ctx, board)
    assert "删除第 1 号留言" in msgs[0]
    assert len(board.notes) == 1
    assert board.notes[0].title == "第二帖"
    target = tmp_path / "daemon" / "bboard_test_board.json"
    assert target.exists()


def test_discard_others_note_blocked() -> None:
    """非作者非 caretaker -> 拒绝删他人帖。"""
    game, player, board = _game_for_discard()
    ctx = _ctx(player, raw_args="2", verb="discard", token=_token(player))
    assert do_discard(game, ctx, board) == ["这个留言不是你写的。\n"]
    assert len(board.notes) == 2


def test_discard_caretaker_allows() -> None:
    """caretaker+ 放行删他人帖。"""
    game, player, board = _game_for_discard()
    ctx = _ctx(
        player, raw_args="2", verb="discard", token=_token(player, WizLevel.CARETAKER)
    )
    msgs = do_discard(game, ctx, board)
    assert "删除第 2 号留言" in msgs[0]
    assert len(board.notes) == 1
    assert board.notes[0].title == "第一帖"


def test_discard_out_of_range() -> None:
    """编号越界拒绝。"""
    game, player, board = _game_for_discard()
    ctx0 = _ctx(player, raw_args="0", verb="discard", token=_token(player))
    ctx3 = _ctx(player, raw_args="3", verb="discard", token=_token(player))
    assert do_discard(game, ctx0, board) == ["没有这张留言。\n"]
    assert do_discard(game, ctx3, board) == ["没有这张留言。\n"]


def test_discard_sscanf_fail() -> None:
    """sscanf 失败 -> 格式提示。"""
    game, player, board = _game_for_discard()
    ctx = _ctx(player, raw_args="abc", verb="discard", token=_token(player))
    assert do_discard(game, ctx, board) == ["指令格式：discard <留言编号>\n"]


def test_discard_no_arg() -> None:
    """arg 为空 -> 格式提示。"""
    game, player, board = _game_for_discard()
    ctx = _ctx(player, raw_args="", verb="discard", token=_token(player))
    assert do_discard(game, ctx, board) == ["指令格式：discard <留言编号>\n"]


def test_discard_no_daemon_store_skips_save() -> None:
    """无 daemon_store 时跳过 save（warning 不 raise）。"""
    game, player, board = _game_for_discard()
    ctx = _ctx(player, raw_args="1", verb="discard", token=_token(player))
    msgs = do_discard(game, ctx, board)
    assert "删除第 1 号留言" in msgs[0]
    assert len(board.notes) == 1


def test_discard_save_roundtrip(tmp_path: Any) -> None:
    """删帖后 save -> restore_all 往返一致（notes 少一条）。"""
    game, player, board = _game_for_discard()
    store = DaemonStore(str(tmp_path))
    store.register("bboard_test_board", board)
    game.world.daemon_store = store
    ctx = _ctx(player, raw_args="1", verb="discard", token=_token(player))
    do_discard(game, ctx, board)

    # 新 store 模拟冷重启：restore_all 反序列化 re-register
    store2 = DaemonStore(str(tmp_path))
    store2.register("bboard_test_board", BboardData(board_id="test_board"))
    store2.restore_all()
    restored = store2.get("bboard_test_board")
    assert restored is not None
    notes = restored.notes
    assert len(notes) == 1
    assert notes[0].title == "第二帖"


def test_discard_none_token_fail_closed() -> None:
    """token=None fail-closed：非作者且非 caretaker -> 拒绝（不变量 1）。"""
    game, player, board = _game_for_discard()
    ctx = _ctx(player, raw_args="2", verb="discard", token=None)
    assert do_discard(game, ctx, board) == ["这个留言不是你写的。\n"]
