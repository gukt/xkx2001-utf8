"""pilot 样本 id=2：center.c:do_check_menpai_job 迁移单元测试。

覆盖主路径（单门派/多门派）+ 失败分支（无参数/非法参数/can_used 门控/
job_data 加载失败）+ 各贡献度展示分支（空/单/多 good&bad）+ start_more
分页调用 + 11 门派同构去重。
"""

from __future__ import annotations

from typing import Any

import tools.sampling.pilot.samples.center_c_do_check_menpai_job as mod
from tools.sampling.pilot.samples.center_c_do_check_menpai_job import (
    do_check_menpai_job,
)

from xkx.runtime.commands import Game
from xkx.runtime.components import Identity, Position
from xkx.runtime.ecs import World


class FakeJobData:
    """样本特有 job_data 桩（不进 stubs.py）。

    对照 LPC /clone/obj/job/job_data 三方法：restore no-op，
    query_family_jobdata 返回统计串，choose_of_player 返回预设玩家名 list。
    """

    def __init__(
        self,
        stats: dict[str, str] | None = None,
        players: dict[tuple[str, str], list[str]] | None = None,
    ) -> None:
        self.stats = stats or {}
        self.players = players or {}
        self.restored = False

    def restore(self) -> None:
        self.restored = True

    def query_family_jobdata(self, family: str) -> str:
        return self.stats.get(family, f"[{family}统计]\n")

    def choose_of_player(self, family: str, kind: str) -> list[str]:
        return self.players.get((family, kind), [])


def _game(
    monkeypatch: Any,
    *,
    actor_id_val: str = "server",
    is_wizard: bool = True,
) -> tuple[Game, int]:
    """构造巫师玩家最小场景（do_check_menpai_job 不需房间/NPC）。

    wizardp 预建桩默认 False，按 is_wizard 用 monkeypatch 替换（自动恢复）。
    """
    world = World()
    player = world.new_entity()
    world.add(player, Identity(
        name="巫师", aliases=["wizard"], is_player=True,
        prototype_id=actor_id_val,
    ))
    world.add(player, Position(room_id="room/test"))
    game = Game(world, {}, rules=[])
    monkeypatch.setattr(mod, "wizardp", lambda *_a, **_k: is_wizard)
    return game, player


def _install_job_data(monkeypatch: Any, job_data: FakeJobData) -> None:
    """注入样本特有 job_data 桩（monkeypatch 模块级 provider）。"""
    monkeypatch.setattr(mod, "_job_data_provider", lambda: job_data)


def test_no_arg_fails(monkeypatch: Any) -> None:
    """无参数 -> 格式提示。"""
    game, player = _game(monkeypatch)
    msgs = do_check_menpai_job(game, player, None)
    assert msgs == ["格式check_menpai_job -menpai_name。\n"]


def test_can_used_id_not_in_whitelist_fails(monkeypatch: Any) -> None:
    """actor id 非白名单(server/poke/xuanyuan) -> 拒绝。"""
    game, player = _game(monkeypatch, actor_id_val="hacker", is_wizard=True)
    msgs = do_check_menpai_job(game, player, "-wudang")
    assert msgs == ["任务控制系统目前只能由高级巫师来控制。\n"]


def test_can_used_not_wizard_fails(monkeypatch: Any) -> None:
    """id 在白名单但 wizardp False -> 拒绝。"""
    game, player = _game(monkeypatch, actor_id_val="server", is_wizard=False)
    msgs = do_check_menpai_job(game, player, "-wudang")
    assert msgs == ["你还没有获得神仙的法力，无法控制这里。\n"]


def test_unknown_flag_fails(monkeypatch: Any) -> None:
    """非门派参数 -> "你要查什么门派?"（default 分支）。"""
    game, player = _game(monkeypatch)
    msgs = do_check_menpai_job(game, player, "-foobar")
    assert msgs == ["你要查什么门派?\n"]


def test_mixed_known_and_unknown_flag_fails(monkeypatch: Any) -> None:
    """合法 + 非法参数混合 -> default 分支拒绝。"""
    game, player = _game(monkeypatch)
    msgs = do_check_menpai_job(game, player, "-wudang -bogus")
    assert msgs == ["你要查什么门派?\n"]


def test_job_data_load_failure_returns_empty(monkeypatch: Any) -> None:
    """job_data 加载失败（provider None）-> 返回空（对应 LPC return 0）。"""
    game, player = _game(monkeypatch)
    monkeypatch.setattr(mod, "_job_data_provider", None)
    msgs = do_check_menpai_job(game, player, "-wudang")
    assert msgs == []


def test_single_menpai_single_good_single_bad(monkeypatch: Any) -> None:
    """单门派：good/bad 各 1 玩家 -> 单列表消息。"""
    game, player = _game(monkeypatch)
    jd = FakeJobData(
        stats={"武当派": "武当派统计行\n"},
        players={
            ("武当派", "good"): ["张三丰"],
            ("武当派", "bad"): ["小道士"],
        },
    )
    _install_job_data(monkeypatch, jd)
    captured: list[str] = []
    monkeypatch.setattr(mod, "start_more", lambda m: captured.append(m))
    msgs = do_check_menpai_job(game, player, "-wudang")
    assert len(msgs) == 1
    assert "游戏主动性任务察看器1.0版" in msgs[0]
    assert "武当派统计行" in msgs[0]
    assert "这个门派贡献度最高的玩家是：\n张三丰\n" in msgs[0]
    assert "\n这个门派贡献度最低的玩家是：\n小道士\n" in msgs[0]
    assert jd.restored is True
    assert len(captured) == 1
    assert captured[0] == msgs[0]


def test_multi_good_multi_bad_tab_separated(monkeypatch: Any) -> None:
    """good/bad 各多个玩家 -> 数个 + tab 分隔。"""
    game, player = _game(monkeypatch)
    _install_job_data(monkeypatch, FakeJobData(
        players={
            ("丐帮", "good"): ["洪七", "鲁有脚"],
            ("丐帮", "bad"): ["乞丐甲", "乞丐乙"],
        },
    ))
    msgs = do_check_menpai_job(game, player, "-gaibang")
    assert "这个门派有数个贡献度最高的玩家，他们分别是：\n洪七\t鲁有脚\t" in msgs[0]
    assert (
        "\n这个门派有数个贡献度最低的玩家，他们分别是：\n乞丐甲\t乞丐乙\t"
        in msgs[0]
    )


def test_empty_good_bad_no_player_message(monkeypatch: Any) -> None:
    """good/bad 均空 -> "没有完成任务的完家"（HIR/NOR 回落空串）。"""
    game, player = _game(monkeypatch)
    _install_job_data(monkeypatch, FakeJobData(players={}))
    msgs = do_check_menpai_job(game, player, "-shaolin")
    assert "这个门派没有完成任务的完家。\n" in msgs[0]
    # good 段无前导换行，bad 段同样无前导换行（两段都走空分支）
    assert msgs[0].count("这个门派没有完成任务的完家。") == 2


def test_good_empty_bad_single_mixed(monkeypatch: Any) -> None:
    """good 空、bad 单个 -> good 走空分支，bad 走单列表分支。"""
    game, player = _game(monkeypatch)
    _install_job_data(monkeypatch, FakeJobData(
        players={("星宿派", "bad"): ["丁春秋"]},
    ))
    msgs = do_check_menpai_job(game, player, "-xingxiu")
    # good 空分支（无前导换行）
    assert "这个门派没有完成任务的完家。\n" in msgs[0]
    # bad 单列表分支（带前导换行）
    assert "\n这个门派贡献度最低的玩家是：\n丁春秋\n" in msgs[0]


def test_multiple_menpai_accumulate_and_multi_start_more(monkeypatch: Any) -> None:
    """多门派选中 -> msg 累积，每门派调一次 start_more（共 N 次）。"""
    game, player = _game(monkeypatch)
    jd = FakeJobData(
        stats={"武当派": "WD\n", "少林派": "SL\n"},
        players={
            ("武当派", "good"): ["张三丰"],
            ("武当派", "bad"): [],
            ("少林派", "good"): [],
            ("少林派", "bad"): ["虚竹"],
        },
    )
    _install_job_data(monkeypatch, jd)
    captured: list[str] = []
    monkeypatch.setattr(mod, "start_more", lambda m: captured.append(m))
    msgs = do_check_menpai_job(game, player, "-wudang -shaolin")
    assert len(msgs) == 1
    # 两个门派内容都在最终累积 msg 中
    assert "WD\n" in msgs[0]
    assert "SL\n" in msgs[0]
    # start_more 被调 2 次（每门派一次）；第一次只含武当段，第二次含全部累积
    assert len(captured) == 2
    assert "WD\n" in captured[0]
    assert "SL\n" not in captured[0]
    assert captured[1] == msgs[0]


def test_all_eleven_menpai_processed(monkeypatch: Any) -> None:
    """11 个门派全选 -> 11 段统计全部出现，start_more 调 11 次。"""
    game, player = _game(monkeypatch)
    _install_job_data(monkeypatch, FakeJobData(
        stats={f: f"{f}统计\n" for _, f in mod._MENPAI_OPTIONS}
    ))
    captured: list[str] = []
    monkeypatch.setattr(mod, "start_more", lambda m: captured.append(m))
    all_flags = " ".join(flag for flag, _ in mod._MENPAI_OPTIONS)
    msgs = do_check_menpai_job(game, player, all_flags)
    for _, family in mod._MENPAI_OPTIONS:
        assert f"{family}统计" in msgs[0]
    assert len(captured) == 11


def test_arg_split_handles_spaces(monkeypatch: Any) -> None:
    """多空格参数 explode 后空串 token 走 default 分支。"""
    game, player = _game(monkeypatch)
    # "  " split 产生空串 token，空串非门派 flag -> default 拒绝
    msgs = do_check_menpai_job(game, player, "-wudang  -shaolin")
    assert msgs == ["你要查什么门派?\n"]


def test_dali_menpai_name_correct(monkeypatch: Any) -> None:
    """-dali 映射"大理段家"（非"大理派"），校验门派名参数化正确。"""
    game, player = _game(monkeypatch)
    _install_job_data(monkeypatch, FakeJobData(stats={"大理段家": "DL_FLAG\n"}))
    msgs = do_check_menpai_job(game, player, "-dali")
    assert "DL_FLAG\n" in msgs[0]


def test_start_more_default_stub_returns_list(monkeypatch: Any) -> None:
    """未替换 start_more 时用预建桩（返回 [msg]），不报错。"""
    game, player = _game(monkeypatch)
    _install_job_data(monkeypatch, FakeJobData(stats={"峨嵋派": "EM\n"}))
    # 不 monkeypatch start_more，走预建桩
    msgs = do_check_menpai_job(game, player, "-emei")
    assert "EM\n" in msgs[0]
