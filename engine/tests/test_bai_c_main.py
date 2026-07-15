"""pilot 样本 id=13：bai.c:main 迁移单元测试。

覆盖补全的 6 项后置分支：cancel 取消、possessed 静默、玩家拜玩家 wizardp
门控、磕头 add 第 3 死亡原因参数、pending/recruit 双向握手收徒（叛师 vs 普通）、
chinese_number、NPC attempt_apprentice 钩子、改主意换人。
"""

from __future__ import annotations

from typing import Any

import pytest
from tools.sampling.pilot.samples import bai_c_main as mod
from tools.sampling.pilot.samples.bai_c_main import bai_c_main

from xkx.runtime.commands import Game
from xkx.runtime.components import (
    Attributes,
    EffectComp,
    FamilyComp,
    Identity,
    NpcBehavior,
    Position,
    Progression,
    Vitals,
)
from xkx.runtime.ecs import World


def _game(
    *,
    player_family: str = "",
    player_generation: int = 0,
    master_id: str = "",
    master_name: str = "",
    master_family: str = "雪山派",
    master_generation: int = 1,
    master_is_player: bool = False,
    player_jing: int = 500,
    app_config: dict | None = None,
) -> tuple[Game, int, int]:
    """构造 1 房间 + 玩家 + 目标的最小场景。"""
    world = World()

    player = world.new_entity()
    world.add(
        player, Identity(name="玩家", aliases=["player"], is_player=True, prototype_id="player")
    )
    world.add(player, Position(room_id="room/test"))
    world.add(player, Attributes(family=player_family, gender="男性", int_=20))
    world.add(player, Vitals(jing=player_jing, max_jing=player_jing))
    world.add(player, Progression(combat_exp=50000))
    if player_family or master_id:
        world.add(
            player,
            FamilyComp(
                family_name=player_family,
                generation=player_generation,
                master_id=master_id,
                master_name=master_name,
            ),
        )

    target = world.new_entity()
    world.add(
        target,
        Identity(
            name="师傅",
            aliases=["shifu"],
            is_player=master_is_player,
            prototype_id="xueshan/gongcang",
        ),
    )
    world.add(target, Position(room_id="room/test"))
    world.add(target, Attributes(family=master_family, gender="男性", int_=20))
    world.add(target, Vitals(jing=500, max_jing=500))
    world.add(target, Progression(combat_exp=50000))
    world.add(
        target,
        FamilyComp(
            family_name=master_family,
            generation=master_generation,
        ),
    )
    if app_config is not None:
        world.add(target, NpcBehavior(apprentice_config=app_config))

    return Game(world, {}, rules=[]), player, target


def _family(world: World, eid: int) -> FamilyComp:
    f = world.get(eid, FamilyComp)
    assert f is not None
    return f


def _vitals(world: World, eid: int) -> Vitals:
    v = world.get(eid, Vitals)
    assert v is not None
    return v


def _reset_pending() -> None:
    mod._PENDING_APPRENTICE.clear()
    mod._PENDING_RECRUIT.clear()
    mod._JING_DEATH_REASONS.clear()


@pytest.fixture(autouse=True)
def _clear_pending_state() -> None:
    """每个测试前清空模块级 pending 握手状态（跨测试残留隔离）。"""
    _reset_pending()


def test_busy_fails() -> None:
    """busy 状态阻止拜师。"""
    game, player, _ = _game()
    busy = game.world.new_entity()
    game.world.add(
        busy, EffectComp(effect_id="exercise", kind="busy", target_id=player, duration=1)
    )
    assert bai_c_main(game, player, "师傅") == ["你现在正忙着呢。"]


def test_no_arg_shows_usage() -> None:
    """无参 -> 指令格式提示。"""
    game, player, _ = _game()
    assert bai_c_main(game, player, "") == ["指令格式：apprentice | bai [cancel]|<对象>"]


def test_possessed_silent_return(monkeypatch: Any) -> None:
    """possessed 玩家静默返回空列表（对照 LPC return 0）。"""
    game, player, _ = _game()
    monkeypatch.setattr(mod, "_query_possessed", lambda *_a, **_kw: True)
    assert bai_c_main(game, player, "师傅") == []


def test_cancel_no_pending_fails() -> None:
    """cancel 但无 pending -> 没有拜师意思。"""
    game, player, _ = _game()
    assert bai_c_main(game, player, "cancel") == ["你现在并没有拜任何人为师的意思。"]


def test_cancel_with_pending(monkeypatch: Any) -> None:
    """cancel 有 pending -> 改主意消息 + 清 pending + 通知 old_app。"""
    game, player, target = _game()
    mod._PENDING_APPRENTICE[player] = target
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "cancel")
    assert msgs == ["你改变主意不想拜师傅为师了。"]
    assert player not in mod._PENDING_APPRENTICE


def test_target_not_found_fails() -> None:
    """present 找不到目标 -> 想拜谁为师。"""
    game, player, _ = _game()
    assert bai_c_main(game, player, "不存在的人") == ["你想拜谁为师？"]


def test_self_bai_fails() -> None:
    """拜自己 -> 好主意不过没用。"""
    game, player, _ = _game()
    # 给玩家一个 family 使其能被 present 命中（_find_target_in_room 查 Identity）
    assert bai_c_main(game, player, "玩家") == ["拜自己为师？好主意....不过没有用。"]


def test_player_target_non_wizard_fails(monkeypatch: Any) -> None:
    """玩家目标且非巫师 -> 不能拜其他玩家为师。"""
    game, player, _ = _game(master_is_player=True)
    monkeypatch.setattr(mod, "wizardp", lambda *_a, **_kw: False)
    assert bai_c_main(game, player, "师傅") == ["你不能够拜其他玩家为师。"]


def test_player_target_wizard_proceeds(monkeypatch: Any) -> None:
    """玩家目标且为巫师 -> 跳过 L43 门控，继续后续流程（无 family -> 拒）。"""
    game, player, _ = _game(master_is_player=True, master_family="")
    # wizardp=True 跳过玩家门控；目标无 FamilyComp.family_name -> L52 拒
    monkeypatch.setattr(mod, "wizardp", lambda *_a, **_kw: True)
    msgs = bai_c_main(game, player, "师傅")
    assert msgs == ["师傅既不属於任何门派，也没有开山立派，不能拜师。"]


def test_already_apprentice_bows() -> None:
    """已是徒弟 -> 磕头请安 + 扣 50 jing。"""
    game, player, target = _game(
        player_family="雪山派",
        master_id="xueshan/gongcang",
        master_name="师傅",
    )
    before = _vitals(game.world, player).jing
    msgs = bai_c_main(game, player, "师傅")
    assert msgs == ["你恭恭敬敬地向师傅磕头请安，叫道：「师父！」"]
    assert _vitals(game.world, player).jing == before - 50


def test_bow_to_death_records_reason() -> None:
    """磕头扣 50 jing 致死 -> 记录「磕死」死因（第 3 参数传递）。"""
    game, player, target = _game(
        player_family="雪山派",
        master_id="xueshan/gongcang",
        master_name="师傅",
        player_jing=30,
    )
    msgs = bai_c_main(game, player, "师傅")
    assert msgs == ["你恭恭敬敬地向师傅磕头请安，叫道：「师父！」"]
    assert _vitals(game.world, player).jing == 0
    assert mod._JING_DEATH_REASONS.get(player) == "一头磕在地上磕死了。"


def test_target_no_family_fails() -> None:
    """目标无门派 -> 不能拜师。"""
    game, player, _ = _game(master_family="")
    assert bai_c_main(game, player, "师傅") == ["师傅既不属於任何门派，也没有开山立派，不能拜师。"]


def test_generation_check_same_family_fails() -> None:
    """同门派 + 师傅辈分 >= 玩家 + 非 special_master -> 辈分不对。"""
    game, player, _ = _game(
        player_family="雪山派",
        player_generation=2,
        master_family="雪山派",
        master_generation=3,  # 师傅辈分 >= 玩家
    )
    assert bai_c_main(game, player, "师傅") == ["师傅的辈分不对，你不能拜平辈或晚辈为师。"]


def test_special_master_bypasses_generation(monkeypatch: Any) -> None:
    """special_master=True -> 绕过辈分检查，进入 pending 流程。"""
    game, player, target = _game(
        player_family="雪山派",
        player_generation=2,
        master_family="雪山派",
        master_generation=3,
        app_config={
            "family_name": "雪山派",
            "generation": 3,
            "conditions": {},
        },
    )
    monkeypatch.setattr(mod, "_query_special_master", lambda *_a, **_kw: True)
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    # 进入 else 分支：设 pending/apprentice + NPC attempt 通过
    assert "你想要拜师傅为师。" in msgs
    assert mod._PENDING_APPRENTICE.get(player) == target


def test_pending_recruit_normal_recruits(monkeypatch: Any) -> None:
    """pending/recruit == me 且同门派 -> 普通拜师收徒。"""
    game, player, target = _game(
        player_family="雪山派",
        player_generation=2,
        master_family="雪山派",
        master_generation=1,
        app_config={
            "family_name": "雪山派",
            "generation": 1,
            "conditions": {},
        },
    )
    mod._PENDING_RECRUIT[target] = player
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    # 首条：决定拜师 + 磕四个响头
    assert "你决定拜师傅为师。" in msgs[0]
    assert "磕了四个响头" in msgs[0]
    # 末条：恭喜成为第 N 代弟子（chinese_number 桩=阿拉伯数字，generation=2）
    assert any("恭喜您成为雪山派的第2代弟子" in m for m in msgs)
    fam = _family(game.world, player)
    assert fam.family_name == "雪山派"
    assert fam.master_name == "师傅"
    # 叛师分支未触发（同门派）
    assert fam.betrayer == 0
    # pending/recruit 已清
    assert target not in mod._PENDING_RECRUIT


def test_pending_recruit_betray(monkeypatch: Any) -> None:
    """pending/recruit == me 且不同门派 -> 叛师收徒 + betrayer+1。"""
    game, player, target = _game(
        player_family="武当派",
        player_generation=2,
        master_family="雪山派",
        master_generation=1,
        app_config={
            "family_name": "雪山派",
            "generation": 1,
            "conditions": {},
        },
    )
    mod._PENDING_RECRUIT[target] = player
    score_calls: list[int] = []
    monkeypatch.setattr(mod, "_set_score", lambda _w, eid, val: score_calls.append(eid))
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    # 首条：叛师消息
    assert "你决定背叛师门，改投入师傅门下" in msgs[0]
    fam = _family(game.world, player)
    assert fam.family_name == "雪山派"  # 改投新门派
    assert fam.betrayer == 1  # 叛师计数 +1
    # score=0 / death_count=0 被调用（后置 key 桩）
    assert score_calls == [player]


def test_set_pending_npc_attempt_passes(monkeypatch: Any) -> None:
    """无 pending/recruit + NPC 目标 attempt 通过 -> 设 pending + 想拜消息。"""
    game, player, target = _game(
        master_family="雪山派",
        master_generation=1,
        app_config={
            "family_name": "雪山派",
            "generation": 1,
            "conditions": {},
        },
    )
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    assert msgs == ["你想要拜师傅为师。"]
    assert mod._PENDING_APPRENTICE.get(player) == target


def test_npc_attempt_rejected(monkeypatch: Any) -> None:
    """NPC attempt_apprentice 拒绝（条件不满足）-> 返回拒绝消息 + 清 pending。"""
    game, player, target = _game(
        master_family="雪山派",
        master_generation=1,
        app_config={
            "family_name": "雪山派",
            "generation": 1,
            "conditions": {"min_combat_exp": 100000},  # 玩家 exp 50000 不够
        },
    )
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    assert msgs == ["师傅说道：你的经验还浅，再历练历练吧。"]
    # 拒绝后 pending 已清
    assert player not in mod._PENDING_APPRENTICE


def test_already_pending_same_target(monkeypatch: Any) -> None:
    """已 pending 同一目标 -> 对方还没答应。"""
    game, player, target = _game(
        master_family="雪山派",
        master_generation=1,
    )
    mod._PENDING_APPRENTICE[player] = target
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    assert msgs == ["你想拜师傅为师，但是对方还没有答应。"]


def test_change_target_clears_old(monkeypatch: Any) -> None:
    """改拜新目标 -> 取消旧 pending + 想拜消息。"""
    game, player, target = _game(
        master_family="雪山派",
        master_generation=1,
        app_config={
            "family_name": "雪山派",
            "generation": 1,
            "conditions": {},
        },
    )
    # 旧 pending 指向另一个实体
    old = game.world.new_entity()
    game.world.add(old, Identity(name="旧师傅", aliases=["old"], is_player=False))
    game.world.add(old, Position(room_id="room/test"))
    game.world.add(old, FamilyComp(family_name="雪山派", generation=1))
    mod._PENDING_APPRENTICE[player] = old
    told: list[str] = []
    monkeypatch.setattr(mod, "tell_object", lambda _w, eid, msg: told.append(msg))
    msgs = bai_c_main(game, player, "师傅")
    # 改主意消息 + 想拜新目标消息
    assert "你改变主意不想拜旧师傅为师了。" in msgs
    assert "你想要拜师傅为师。" in msgs
    # 旧 pending 已清，新 pending 指向新目标
    assert mod._PENDING_APPRENTICE.get(player) == target
    # tell_object 通知了旧师傅
    assert any("改变主意不想拜你为师了" in m for m in told)


def test_chinese_number_monkeypatch(monkeypatch: Any) -> None:
    """chinese_number 可被 monkeypatch 注入中文（验证桩可替换）。"""
    game, player, target = _game(
        player_family="雪山派",
        player_generation=2,
        master_family="雪山派",
        master_generation=1,
        app_config={
            "family_name": "雪山派",
            "generation": 1,
            "conditions": {},
        },
    )
    mod._PENDING_RECRUIT[target] = player
    monkeypatch.setattr(mod, "chinese_number", lambda n: "二")
    monkeypatch.setattr(mod, "tell_object", lambda *_a, **_kw: None)
    msgs = bai_c_main(game, player, "师傅")
    assert any("恭喜您成为雪山派的第二代弟子" in m for m in msgs)
