"""job_commands 引擎层单测（ADR-0061）。

覆盖 do_check_menpai_job（pilot 正式化 + can_used 门控 + 参数解析 +
11 门派循环）+ do_check_player（只读查询 + 无此玩家）+ do_cut_job
（can_used + 删除 + save 闭环 + reset）+ do_check_do_job（三组任务
列表 + 在线过滤）。

用真实 ``PermissionService().issue_token`` + ``cmp_wiz_level`` 构造权限
场景（不 monkeypatch 桩，体现合一核心价值）。
"""

from __future__ import annotations

import json
from typing import Any

from xkx.runtime.action_context import new_context
from xkx.runtime.capability import CapabilityToken, PermissionService, WizLevel
from xkx.runtime.commands import Game
from xkx.runtime.components import Identity, Position
from xkx.runtime.daemon_store import DaemonStore
from xkx.runtime.daemons.job_data import ActiveJob, JobData
from xkx.runtime.ecs import World
from xkx.runtime.job_commands import (
    do_check_do_job,
    do_check_menpai_job,
    do_check_player,
    do_cut_job,
)

# ──────────────────────── 测试辅助 ────────────────────────


def _job_data() -> JobData:
    """构造测试用 JobData（2 门派 + 3 活跃任务）。"""
    return JobData(
        assess={"wd": 7000, "xx": 5000},
        strategy={
            "wd": {"protect": 30, "generally": 40},
            "xx": {"plunder": 30, "generally": 40},
        },
        luck={"wd": 3, "xx": 2},
        luck_rate={"wd": 30, "xx": 20},
        money={"wd": 5, "xx": 15},
        power={
            "wd": {"南疆": 5, "中原": 20},
            "xx": {"西域": 30, "中原": 0},
        },
        job_datas=[
            ActiveJob(
                job_player="player1",
                job_menpai="武当派",
                job_strategy="oppose_pker",
                job_askjob=1,
                job_command_mode="传话",
            ),
            ActiveJob(
                job_player="player2",
                job_menpai="少林派",
                job_strategy="protect",
                job_oppose_pker_place="/d/test",
                job_oppose_pker_mode="npc",
            ),
            ActiveJob(
                job_player="player3",
                job_menpai="武当派",
                job_strategy="business",
                job_askjob=1,
            ),
        ],
        family_job_data=[
            {
                "family_name": "武当派",
                "job_contribute": 1000,
                "alice": 500,
                "bob": 300,
                "charlie": 200,
            },
            {
                "family_name": "星宿派",
                "job_contribute": 800,
                "dave": 800,
            },
        ],
        start_job_system=1,
    )


def _game(
    *,
    actor_id: str = "server",
    actor_level: WizLevel = WizLevel.ADMIN,
    online_players: list[str] | None = None,
    daemon_store: DaemonStore | None = None,
) -> tuple[Game, int]:
    """构造 1 wizard 玩家 + 可选在线玩家的最小场景。"""
    world = World()
    actor = world.new_entity()
    world.add(
        actor,
        Identity(
            name="巫师",
            aliases=["wizard"],
            is_player=True,
            prototype_id=actor_id,
        ),
    )
    world.add(actor, Position(room_id="room/test"))
    # 在线玩家
    if online_players:
        for name in online_players:
            eid = world.new_entity()
            world.add(
                eid,
                Identity(
                    name=name,
                    aliases=[name],
                    is_player=True,
                    prototype_id=name,
                ),
            )
            world.add(eid, Position(room_id="room/test"))
    if daemon_store is not None:
        world.daemon_store = daemon_store  # type: ignore[attr-defined]
    return Game(world, {}, rules=[]), actor


def _token(eid: int, level: WizLevel = WizLevel.ADMIN) -> CapabilityToken:
    """构造真实能力令牌。"""
    return PermissionService().issue_token(eid, level)


def _ctx(
    actor: int,
    *,
    raw_args: str = "",
    token: CapabilityToken | None = None,
    verb: str = "check_menpai_job",
):
    return new_context(
        verb=verb, raw_args=raw_args, actor=actor, capability_token=token
    )


# ──────────────────────── do_check_menpai_job ────────────────────────


def test_menpai_no_arg() -> None:
    """无参数 -> 格式提示。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="", token=_token(actor))
    result = do_check_menpai_job(game, ctx, _job_data())
    assert result == ["格式check_menpai_job -menpai_name。\n"]


def test_menpai_can_used_id_not_allowed() -> None:
    """id 不在白名单 -> 门控失败。"""
    game, actor = _game(actor_id="unknown")
    ctx = _ctx(actor, raw_args="-wudang", token=_token(actor))
    result = do_check_menpai_job(game, ctx, _job_data())
    assert "只能由高级巫师" in result[0]


def test_menpai_can_used_not_wizard() -> None:
    """id 在白名单但非 wizard -> 门控失败。"""
    game, actor = _game(actor_id="server", actor_level=WizLevel.PLAYER)
    ctx = _ctx(actor, raw_args="-wudang", token=_token(actor, WizLevel.PLAYER))
    result = do_check_menpai_job(game, ctx, _job_data())
    assert "神仙的法力" in result[0]


def test_menpai_unknown_flag() -> None:
    """非门派参数 -> "你要查什么门派?"。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="-unknown", token=_token(actor))
    result = do_check_menpai_job(game, ctx, _job_data())
    assert result == ["你要查什么门派?\n"]


def test_menpai_single_family() -> None:
    """单门派查询 -> 包含门派名 + 贡献度文本。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="-wudang", token=_token(actor))
    result = do_check_menpai_job(game, ctx, _job_data())
    msg = result[0]
    assert "武当派" in msg
    assert "1000" in msg  # job_contribute
    assert "alice" in msg  # good 玩家
    assert "charlie" in msg  # bad 玩家


def test_menpai_multiple_families() -> None:
    """多门派查询 -> 包含两个门派文本。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="-wudang -xingxiu", token=_token(actor))
    result = do_check_menpai_job(game, ctx, _job_data())
    msg = result[0]
    assert "武当派" in msg
    assert "星宿派" in msg


# ──────────────────────── do_check_player ────────────────────────


def test_check_player_no_arg() -> None:
    """无参数 -> 提示。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="", verb="do_check_player")
    result = do_check_player(game, ctx, _job_data())
    assert result == ["do_check_player player_name。\n"]


def test_check_player_not_found() -> None:
    """无此玩家 -> "没有这个player的信息。" """
    game, actor = _game()
    ctx = _ctx(actor, raw_args="nobody", verb="do_check_player")
    result = do_check_player(game, ctx, _job_data())
    assert "没有这个player的信息" in result[0]


def test_check_player_found() -> None:
    """有此玩家 -> 包含任务信息。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="player1", verb="do_check_player")
    result = do_check_player(game, ctx, _job_data())
    msg = result[0]
    assert "player1" in msg
    assert "武当派" in msg


# ──────────────────────── do_cut_job ────────────────────────


def test_cut_job_can_used_fail() -> None:
    """can_used 门控失败。"""
    game, actor = _game(actor_id="unknown")
    ctx = _ctx(actor, raw_args="player1", verb="job_cut")
    result = do_cut_job(game, ctx, _job_data())
    assert "只能由高级巫师" in result[0]


def test_cut_job_no_arg() -> None:
    """无参数 -> 提示。"""
    game, actor = _game()
    ctx = _ctx(actor, raw_args="", verb="job_cut", token=_token(actor))
    result = do_cut_job(game, ctx, _job_data())
    assert result == ["job_cut player_name。\n"]


def test_cut_job_deletes_player(tmp_path: Any) -> None:
    """删除特定玩家 -> detract + save 闭环。"""
    store = DaemonStore(str(tmp_path))
    data = _job_data()
    store.register("job_data", data)
    game, actor = _game(daemon_store=store)
    ctx = _ctx(actor, raw_args="player1", verb="job_cut", token=_token(actor))

    result = do_cut_job(game, ctx, data)
    msg = result[0]
    assert "你现在删除player1所有的任务" in msg
    # job_datas 减少 1（player1 被删）
    assert len(data.job_datas) == 2
    assert all(j.job_player != "player1" for j in data.job_datas)
    # save 闭环：存档文件生成
    target = tmp_path / "daemon" / "job_data.json"
    assert target.exists()
    with open(target, encoding="utf-8") as f:
        state = json.load(f)
    # 存档中 job_datas 不含 player1
    players = [j["job_player"] for j in state["job_datas"]]
    assert "player1" not in players


def test_cut_job_all_resets(tmp_path: Any) -> None:
    """删除 "all" -> reset + save。"""
    store = DaemonStore(str(tmp_path))
    data = _job_data()
    store.register("job_data", data)
    game, actor = _game(daemon_store=store)
    ctx = _ctx(actor, raw_args="all", verb="job_cut", token=_token(actor))

    result = do_cut_job(game, ctx, data)
    assert result == [""]
    # reset 后 job_datas 清空
    assert data.job_datas == []
    assert data.start_job_system == 0
    # save 闭环
    target = tmp_path / "daemon" / "job_data.json"
    assert target.exists()
    with open(target, encoding="utf-8") as f:
        state = json.load(f)
    assert state["job_datas"] == []


def test_cut_job_no_store_skips_save() -> None:
    """无 daemon_store -> 跳过 save + 不 crash。"""
    data = _job_data()
    game, actor = _game()  # 不注入 daemon_store
    ctx = _ctx(actor, raw_args="player1", verb="job_cut", token=_token(actor))
    result = do_cut_job(game, ctx, data)
    assert "你现在删除player1所有的任务" in result[0]
    # 仍然 detract（内存态修改生效）
    assert all(j.job_player != "player1" for j in data.job_datas)


def test_cut_job_save_roundtrip(tmp_path: Any) -> None:
    """do_cut_job save -> restore_all 往返一致。"""
    store = DaemonStore(str(tmp_path))
    data = _job_data()
    store.register("job_data", data)
    game, actor = _game(daemon_store=store)
    ctx = _ctx(actor, raw_args="player2", verb="job_cut", token=_token(actor))
    do_cut_job(game, ctx, data)

    # 新 store 冷重启
    store2 = DaemonStore(str(tmp_path))
    store2.register("job_data", JobData())
    store2.restore_all()
    restored = store2.get("job_data")
    assert restored is not None
    assert isinstance(restored, JobData)
    # player2 被删除
    players = [j.job_player for j in restored.job_datas]
    assert "player2" not in players
    # player1/player3 保留
    assert "player1" in players
    assert "player3" in players


# ──────────────────────── do_check_do_job ────────────────────────


def test_check_do_job_lists_three_groups() -> None:
    """do_check_do_job 列出三组任务。"""
    # player1/player3 在线（ask_job），player2 不在线
    game, actor = _game(online_players=["player1", "player3"])
    ctx = _ctx(actor, raw_args="", verb="check_do_job")
    result = do_check_do_job(game, ctx, _job_data())
    msg = result[0]
    assert "现在已经得到任务的人有" in msg
    assert "现在正在执行任务的人有" in msg
    assert "现在已经完成任务的人有" in msg
    # player1 在线且 ask_job==1 -> 出现在"已得到任务"
    assert "player1" in msg
    # player3 在线且 ask_job==1 -> 出现在"已得到任务"
    assert "player3" in msg


def test_check_do_job_filters_offline() -> None:
    """do_check_do_job 过滤离线玩家。"""
    # 无在线玩家
    game, actor = _game(online_players=[])
    ctx = _ctx(actor, raw_args="", verb="check_do_job")
    result = do_check_do_job(game, ctx, _job_data())
    msg = result[0]
    # 三组都列出标题但不包含玩家名（全离线）
    assert "现在已经得到任务的人有:\n" in msg
    assert "player1" not in msg
    assert "player2" not in msg


def test_check_do_job_oppose_pker_online() -> None:
    """do_check_do_job 在线 oppose_pker 玩家出现。"""
    # player2 在线（oppose_pker）
    game, actor = _game(online_players=["player2"])
    ctx = _ctx(actor, raw_args="", verb="check_do_job")
    result = do_check_do_job(game, ctx, _job_data())
    msg = result[0]
    # player2 有 oppose_pker_place -> 出现在"正在执行任务"
    assert "player2" in msg
