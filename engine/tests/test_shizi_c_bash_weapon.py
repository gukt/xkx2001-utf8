"""pilot 样本 id=8：shizi.c:bash_weapon 迁移单元测试。

覆盖四档判定（断裂/脱手/震动/火星）、neili 门控、无武器门控、jiali<200 vs
>=200 双消息、damage<90 断裂门控、unequip 副作用、reset_action 调用、
query_str/query_jiali 桩注入、RNG 控制命中各档。
"""

from __future__ import annotations

from typing import Any

import pytest
from tools.sampling.pilot.samples import shizi_c_bash_weapon as mod
from tools.sampling.pilot.samples.shizi_c_bash_weapon import (
    WeaponItem,
    bash_weapon,
)

from xkx.runtime.commands import Game
from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Position,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World

# 测试固定参数：wdp=100（victim parry=200 非 raw=100 /2=50 + str=20 +
# rigidity=30 + weight=0）；actor wap 上界=250（neili=200+str=20+技能=30）。
# monkeypatch random.randint 返回 R 命中各档：断裂 R=201 / 脱手 R=101 /
# 震动 R=51 / 火星 R=30。
_WEAPON = WeaponItem(
    item_id="sword/test",
    name="长剑",
    weight=0,
    rigidity=30,
    damage=50,
)


def _game(
    *,
    neili: int = 200,
    actor_str: int = 20,
    victim_str: int = 20,
    tanzhi: int = 30,
    parry: int = 200,
    weapon: WeaponItem | None = _WEAPON,
) -> tuple[Game, int, int]:
    """构造 1 房间 + actor + victim（持武器）的最小场景。"""
    world = World()

    actor = world.new_entity()
    world.add(actor, Identity(name="桃花弟子", is_player=True, prototype_id="actor"))
    world.add(actor, Position(room_id="room/test"))
    world.add(actor, Attributes(str_=actor_str))
    world.add(actor, Vitals(neili=neili))
    world.add(actor, Skills(levels={"tanzhi-shentong": tanzhi}))

    victim = world.new_entity()
    world.add(victim, Identity(name="对手", prototype_id="victim"))
    world.add(victim, Position(room_id="room/test"))
    world.add(victim, Attributes(str_=victim_str))
    world.add(victim, Skills(levels={"parry": parry}))

    if weapon is not None:
        world.add(victim, Equipment(weapon=weapon.item_id, weapon_props={"damage": weapon.damage}))
        # 注入武器台账
        mod._WEAPON_REGISTRY[weapon.item_id] = weapon

    return Game(world, {}, rules=[]), actor, victim


def _equip(world: World, eid: int) -> Equipment:
    e = world.get(eid, Equipment)
    assert e is not None
    return e


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    """每个测试前后清空武器台账，避免跨测试污染。"""
    saved = dict(mod._WEAPON_REGISTRY)
    mod._WEAPON_REGISTRY.clear()
    yield
    mod._WEAPON_REGISTRY.clear()
    mod._WEAPON_REGISTRY.update(saved)


def test_neili_le_100_no_action() -> None:
    """neili<=100 不进入判定，无消息无副作用。"""
    game, actor, victim = _game(neili=100)
    monkey = pytest.MonkeyPatch()
    monkey.setattr("random.randint", lambda a, b: 999)
    msgs = bash_weapon(game, actor, victim)
    monkey.undo()
    assert msgs == []
    # 武器仍在
    assert _equip(game.world, victim).weapon == "sword/test"


def test_no_weapon_no_action() -> None:
    """victim 无武器不进入判定。"""
    game, actor, victim = _game(weapon=None)
    msgs = bash_weapon(game, actor, victim)
    assert msgs == []


def test_break_branch_low_jiali(monkeypatch: Any) -> None:
    """断裂分支（wap>2*wdp 且 damage<90），jiali<200 普通断裂消息 + unequip。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 201)  # wap=201>2*100
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_jiali",
        lambda _w, _e: 50,
    )
    msgs = bash_weapon(game, actor, victim)
    assert len(msgs) == 1
    assert "断为两截" in msgs[0]
    assert "火星四溅" not in msgs[0]
    # $N=victim 名
    assert "对手" in msgs[0]
    # unequip 副作用：武器卸下
    assert _equip(game.world, victim).weapon is None


def test_break_branch_high_jiali_sparks(monkeypatch: Any) -> None:
    """断裂分支，jiali>=200 火星四溅消息。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 201)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_jiali",
        lambda _w, _e: 200,
    )
    msgs = bash_weapon(game, actor, victim)
    assert "火星四溅" in msgs[0]
    assert "断为两截" in msgs[0]


def test_break_blocked_by_high_damage(monkeypatch: Any) -> None:
    """damage>=90 阻断断裂，wap>2*wdp 落入脱手分支。"""
    game, actor, victim = _game(
        weapon=WeaponItem(item_id="sword/heavy", name="重剑", weight=0, rigidity=30, damage=95)
    )
    monkeypatch.setattr("random.randint", lambda a, b: 201)  # >2*wdp
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_jiali",
        lambda _w, _e: 50,
    )
    msgs = bash_weapon(game, actor, victim)
    # 不断裂（damage>=90），落脱手
    assert "脱手飞出" in msgs[0]
    assert "断为两截" not in msgs[0]
    assert _equip(game.world, victim).weapon is None


def test_drop_branch_low_jiali(monkeypatch: Any) -> None:
    """脱手分支（wdp<wap<=2*wdp），jiali<200 普通脱手消息 + unequip。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 101)  # 100<101<=200
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_jiali",
        lambda _w, _e: 50,
    )
    msgs = bash_weapon(game, actor, victim)
    assert "脱手飞出" in msgs[0]
    assert "摔在地下" not in msgs[0]
    assert _equip(game.world, victim).weapon is None


def test_drop_branch_high_jiali(monkeypatch: Any) -> None:
    """脱手分支，jiali>=200 炸粉碎消息。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 101)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_jiali",
        lambda _w, _e: 200,
    )
    msgs = bash_weapon(game, actor, victim)
    assert "炸得粉碎" in msgs[0]
    assert "摔在地下" in msgs[0]


def test_vibrate_branch(monkeypatch: Any) -> None:
    """震动分支（wdp/2<wap<=wdp），武器一震，不卸武器。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 51)  # 50<51<=100
    msgs = bash_weapon(game, actor, victim)
    assert "一震" in msgs[0]
    assert "险些脱手" in msgs[0]
    # 震动不卸武器
    assert _equip(game.world, victim).weapon == "sword/test"


def test_spark_branch(monkeypatch: Any) -> None:
    """火星分支（wap<=wdp/2），$N=actor $n=victim。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 30)  # <=50
    msgs = bash_weapon(game, actor, victim)
    assert "火星" in msgs[0]
    assert "桃花弟子" in msgs[0]  # $N=actor
    assert "对手" in msgs[0]  # $n=victim
    assert _equip(game.world, victim).weapon == "sword/test"


def test_wap_zero_no_action(monkeypatch: Any) -> None:
    """wap 上界<=0 时 random(wap)=0，落入火星分支（wap=0<=wdp/2）。"""
    game, actor, victim = _game(neili=101, actor_str=0, tanzhi=0)
    # wap 上界=101+0+0=101；wdp=100；random.randint(0,100) 返回 0 -> 火星
    monkeypatch.setattr("random.randint", lambda a, b: 0)
    msgs = bash_weapon(game, actor, victim)
    assert "火星" in msgs[0]


def test_reset_action_called_on_break(monkeypatch: Any) -> None:
    """断裂分支调用 reset_action（桩 no-op，用 spy 验证调用）。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 201)
    calls: list[int] = []
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.reset_action",
        lambda _w, eid: calls.append(eid),
    )
    bash_weapon(game, actor, victim)
    assert calls == [victim]


def test_reset_action_called_on_drop(monkeypatch: Any) -> None:
    """脱手分支调用 reset_action。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 101)
    calls: list[int] = []
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.reset_action",
        lambda _w, eid: calls.append(eid),
    )
    bash_weapon(game, actor, victim)
    assert calls == [victim]


def test_reset_action_not_called_on_vibrate_spark(monkeypatch: Any) -> None:
    """震动/火星分支不调用 reset_action（不卸武器）。"""
    game, actor, victim = _game()
    monkeypatch.setattr("random.randint", lambda a, b: 51)  # 震动
    calls: list[int] = []
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.reset_action",
        lambda _w, eid: calls.append(eid),
    )
    bash_weapon(game, actor, victim)
    assert calls == []


def test_query_str_injection(monkeypatch: Any) -> None:
    """query_str 桩注入影响 wap/wdp（验证派生膂力接入）。"""
    game, actor, victim = _game()
    # actor query_str=500 -> wap 上界=200+500+30=730；victim query_str=500 ->
    # wdp=0+30+500+50=580。random 返回 1161 (>2*580=1160) 命中断裂。
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_str",
        lambda _w, eid: 500,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 1161)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.shizi_c_bash_weapon.query_jiali",
        lambda _w, _e: 50,
    )
    msgs = bash_weapon(game, actor, victim)
    assert "断为两截" in msgs[0]
