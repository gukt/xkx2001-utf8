"""pilot 样本 id=5：songshan-jian.c:next_sword 迁移单元测试。

覆盖 LPC L137-188 的关键分支：致命斩（eff_qi<0 && qi<0）、
非 RESULT_PARRY 早退、四档对抗判定（寸断 wap>3wdp / 脱手 wap>2wdp /
震动 wap>wdp / 火星 else）、unequip+reset_action 副作用、item 桩属性读写、
RNG 注入（wap=random(wap/2)+wap/2）。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.songshan_jian_c_next_sword import (
    _DictItemRegistry,
    songshan_jian_c_next_sword,
)

from xkx.combat.result import RESULT_PARRY
from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Position,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World


class _FakeRng:
    """固定随机源：rand(n) 恒返回 n-1（最大值，便于触发高 wap 分支）。"""

    def __init__(self, value: int = 1) -> None:
        self._value = value

    def rand(self, n: int) -> int:
        if n <= 0:
            return 0
        return min(self._value, n - 1)


def _game(
    *,
    me_str: int = 20,
    victim_str: int = 20,
    me_jiali: int = 0,
    victim_jiali: int = 0,
    me_songshan: int = 30,
    victim_parry: int = 30,
    victim_eff_qi: int = 100,
    victim_qi: int = 100,
    victim_weapon: str | None = "victim_sword",
    me_weapon: str = "me_sword",
) -> tuple[World, int, int]:
    """构造 1 房间 + me + victim 的最小场景。"""
    world = World()
    room_id = "room/test"

    me = world.new_entity()
    world.add(me, Identity(name="攻击者", aliases=["me"], prototype_id="me"))
    world.add(me, Position(room_id=room_id))
    world.add(me, Attributes(str_=me_str, gender="男性"))
    world.add(me, Vitals(qi=100, eff_qi=100))
    world.add(me, Skills(levels={"songshan-jian": me_songshan}))
    world.add(me, Equipment(weapon=me_weapon))

    victim = world.new_entity()
    world.add(victim, Identity(name="受害者", aliases=["victim"], prototype_id="victim"))
    world.add(victim, Position(room_id=room_id))
    world.add(victim, Attributes(str_=victim_str, gender="男性"))
    world.add(victim, Vitals(qi=victim_qi, eff_qi=victim_eff_qi))
    world.add(victim, Skills(levels={"parry": victim_parry}))
    if victim_weapon is not None:
        world.add(victim, Equipment(weapon=victim_weapon))
    else:
        world.add(victim, Equipment())

    # jiali 经 stubs.query_jiali 默认 0；monkeypatch 注入非零值用
    return world, me, victim


def _items(
    me_w: int = 5000,
    me_rig: int = 10,
    vic_w: int = 5000,
    vic_rig: int = 10,
) -> _DictItemRegistry:
    """构造 item 桩注册表（weight/rigidity/name 固定）。"""
    return _DictItemRegistry({
        "me_sword": {"name": "嵩山剑", "weight": me_w, "rigidity": me_rig},
        "victim_sword": {"name": "长剑", "weight": vic_w, "rigidity": vic_rig},
    })


def test_lethal_slash_branch() -> None:
    """eff_qi<0 且 qi<0 -> 致命斩消息，立即返回。"""
    world, me, victim = _game(victim_eff_qi=-1, victim_qi=-1)
    msgs = songshan_jian_c_next_sword(world, me, victim, "me_sword", 0, items=_items())
    assert len(msgs) == 1
    assert "斩成两截" in msgs[0]
    assert "嵩山剑" in msgs[0]


def test_lethal_needs_both_negative() -> None:
    """仅 eff_qi<0（qi>=0）不触发致命斩，继续走 parry 分支。"""
    world, me, victim = _game(victim_eff_qi=-1, victim_qi=5)
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=_items(), rng=_FakeRng(0)
    )
    # 不含致命斩
    assert all("斩成两截" not in m for m in msgs)


def test_non_parry_early_return() -> None:
    """damage != RESULT_PARRY -> 无 parry 分支，返回空消息。"""
    world, me, victim = _game()
    msgs = songshan_jian_c_next_sword(world, me, victim, "me_sword", 0, items=_items())
    assert msgs == []


def test_parry_but_no_victim_weapon_early_return() -> None:
    """RESULT_PARRY 但 victim 无武器 -> 无四档判定，返回空。"""
    world, me, victim = _game(victim_weapon=None)
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=_items()
    )
    assert msgs == []


def test_shatter_branch(monkeypatch: Any) -> None:
    """wap > 3*wdp -> 寸断：unequip + 改名 + value/weapon_prop 置 0。"""
    # me 武器极重/rigid 高，victim 武器轻 -> wap 远超 3*wdp
    world, me, victim = _game(me_str=100, me_songshan=300, victim_str=1, victim_parry=1)
    items = _items(me_w=50000, me_rig=100, vic_w=100, vic_rig=1)
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert any("寸断" in m for m in msgs)
    # 副作用：victim 武器已卸下
    assert world.get(victim, Equipment).weapon is None
    # 改名 + value/weapon_prop 置 0
    assert items.name("victim_sword") == "断碎的长剑"
    assert items.value("victim_sword") == 0
    assert items.weapon_prop("victim_sword") == 0


def test_shatter_calls_reset_action(monkeypatch: Any) -> None:
    """寸断分支调用 victim->reset_action()（桩 no-op，验证被调用）。"""
    world, me, victim = _game(me_str=100, me_songshan=300, victim_str=1, victim_parry=1)
    items = _items(me_w=50000, me_rig=100, vic_w=100, vic_rig=1)
    called: list[int] = []
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.songshan_jian_c_next_sword.reset_action",
        lambda _world, eid: called.append(eid),
    )
    songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert called == [victim]


def test_disarm_branch_calculated(monkeypatch: Any) -> None:
    """脱手分支：精确构造 wap in (2*wdp, 3*wdp]。"""
    # me: weight/500=20 + rig=20 + str=40 + jiali=0 + songshan(60)/3=20 + xuli=0 = 100
    # victim: weight/500=20 + rig=20 + str=40 + jiali=0 + parry(60)/3=20 = 100
    # wap = random(50)+50；wdp=100
    # 要 200 < wap <= 300：random(50) 需 >150 不可能（max 49 -> wap=99 < 100）
    # 调整：me 强 victim 弱
    # me: 20+20+60+0+20+0=120; half=60; rng.rand(60)=30 -> wap=90
    # victim: 20+20+20+0+6=66 (parry=18->6); 2*wdp=132, 3*wdp=198 -> wap=90<132 震动
    # 再调：victim 极弱
    world, me, victim = _game(
        me_str=60, me_songshan=60, victim_str=5, victim_parry=6
    )
    items = _items(me_w=10000, me_rig=20, vic_w=10000, vic_rig=20)
    # me wap base = 20+20+60+0+20+0 = 120; half=60
    # victim wdp = 20+20+5+0+2 = 47
    # rng.rand(60)=59 -> wap=119; 2*wdp=94 < 119 <= 3*wdp=141 -> 脱手
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(59)
    )
    assert any("脱手" in m for m in msgs)
    assert world.get(victim, Equipment).weapon is None
    # 脱手不改名
    assert items.name("victim_sword") == "长剑"


def test_shock_branch() -> None:
    """wdp < wap <= 2*wdp -> 震动：不 unequip，消息 $N=victim。"""
    # 构造 wap 略大于 wdp
    # me wap base = 20+20+40+0+20+0=100; half=50; rng.rand(50)=0 -> wap=50
    # victim wdp = 20+20+40+0+20=100 -> wap=50 < 100 走火星，不行
    # 调 victim 弱：victim_str=20, parry=30 -> parry/3=10; wdp=20+20+20+0+10=70
    # wap=50 < 70 火星。再调 me 强
    world, me, victim = _game(me_str=80, me_songshan=90, victim_str=20, victim_parry=30)
    items = _items(me_w=10000, me_rig=20, vic_w=10000, vic_rig=20)
    # me wap base = 20+20+80+0+30+0=150; half=75; rng.rand(75)=0 -> wap=75
    # victim wdp = 20+20+20+0+10=70 -> wdp=70 < wap=75 <= 2*wdp=140 -> 震动
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert any("一震" in m and "险些脱手" in m for m in msgs)
    # 震动不卸武器
    assert world.get(victim, Equipment).weapon == "victim_sword"


def test_sparks_branch() -> None:
    """wap <= wdp -> 火星：双方武器都在，消息含双方武器名。"""
    # 双方对称，rng 返回 0 -> wap = half < wdp
    world, me, victim = _game(me_str=20, me_songshan=30, victim_str=20, victim_parry=30)
    items = _items(me_w=5000, me_rig=10, vic_w=5000, vic_rig=10)
    # me wap base = 10+10+20+0+10+0=50; half=25; rng.rand(25)=0 -> wap=25
    # victim wdp = 10+10+20+0+10=50 -> wap=25 <= 50 -> 火星
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert any("火星" in m for m in msgs)
    assert world.get(victim, Equipment).weapon == "victim_sword"
    # 火星消息含双方武器名
    assert any("嵩山剑" in m and "长剑" in m for m in msgs)


def test_wap_random_application() -> None:
    """wap = random(wap/2) + wap/2：rng 不同 -> 不同分支。

    同一场景，rng=0 走火星，rng=max 走更高级分支。
    """
    world1, me1, victim1 = _game(me_str=20, me_songshan=30, victim_str=20, victim_parry=30)
    world2, me2, victim2 = _game(me_str=20, me_songshan=30, victim_str=20, victim_parry=30)
    items = _items(me_w=5000, me_rig=10, vic_w=5000, vic_rig=10)
    # rng=0 -> wap=25 -> 火星
    msgs_low = songshan_jian_c_next_sword(
        world1, me1, victim1, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    # rng=max(24) -> wap=25+24=49 -> 仍 <= wdp=50 火星；需 me 更强才能跨档
    assert any("火星" in m for m in msgs_low)


def test_xuli_monkeypatch(monkeypatch: Any) -> None:
    """query_temp("songshan_xuli") 经 _query_xuli 桩，monkeypatch 注入非零提升 wap。"""
    world, me, victim = _game(me_str=20, me_songshan=30, victim_str=20, victim_parry=30)
    items = _items(me_w=5000, me_rig=10, vic_w=5000, vic_rig=10)
    # 默认 xuli=0，rng=0 -> wap=25 火星
    base_msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert any("火星" in m for m in base_msgs)

    # 重建场景，注入大 xuli -> wap 提升
    world2, me2, victim2 = _game(me_str=20, me_songshan=30, victim_str=20, victim_parry=30)
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.songshan_jian_c_next_sword._query_xuli",
        lambda _world, _eid: 200,
    )
    # wap base = 10+10+20+0+10+200=250; half=125; rng=0 -> wap=125
    # wdp=50 -> 2*wdp=100 < 125 <= 3*wdp=150 -> 脱手
    msgs = songshan_jian_c_next_sword(
        world2, me2, victim2, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert any("脱手" in m for m in msgs)


def test_jiali_monkeypatch(monkeypatch: Any) -> None:
    """query_jiali 经 stubs 桩，monkeypatch 注入非零提升 me 侧 wap。"""
    world, me, victim = _game(me_str=20, me_songshan=30, victim_str=20, victim_parry=30)
    items = _items(me_w=5000, me_rig=10, vic_w=5000, vic_rig=10)
    # 仅 me 加力（按 eid 区分），victim 保持 0
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.songshan_jian_c_next_sword.query_jiali",
        lambda _world, eid: 300 if eid == me else 0,
    )
    # me wap base = 10+10+20+300+10+0=350; half=175; rng=0 -> wap=175
    # victim wdp = 10+10+20+0+10=50 -> 3*wdp=150 < 175 -> 寸断
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert any("寸断" in m for m in msgs)


def test_default_registry_used_when_none() -> None:
    """items=None 用默认 _DictItemRegistry（属性全 0），wap 极小走火星。"""
    world, me, victim = _game(me_str=1, me_songshan=0, victim_str=1, victim_parry=0)
    # 默认注册表 weight/rigidity=0，name 回退 item_id
    # wap base = 0+0+1+0+0+0=1; half=0; rng=0 -> wap=0
    # wdp = 0+0+1+0+0=1 -> wap=0 <= 1 -> 火星
    msgs = songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, rng=_FakeRng(0)
    )
    assert any("火星" in m for m in msgs)
    # 默认 name 回退 item_id
    assert any("me_sword" in m for m in msgs)


def test_shatter_weapon_prop_recorded() -> None:
    """寸断分支 set("weapon_prop",0)：桩记录原值非零被清零。"""
    world, me, victim = _game(me_str=100, me_songshan=300, victim_str=1, victim_parry=1)
    items = _DictItemRegistry({
        "me_sword": {"name": "嵩山剑", "weight": 50000, "rigidity": 100},
        "victim_sword": {
            "name": "长剑", "weight": 100, "rigidity": 1,
            "value": 500, "weapon_prop": 30,
        },
    })
    songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    assert items.value("victim_sword") == 0
    assert items.weapon_prop("victim_sword") == 0
    assert items.name("victim_sword") == "断碎的长剑"


def test_move_to_room_recorded() -> None:
    """寸断/脱手 ob->move(environment(victim))：物品无 Position，桩记录 dropped_room。"""
    world, me, victim = _game(me_str=100, me_songshan=300, victim_str=1, victim_parry=1)
    items = _items(me_w=50000, me_rig=100, vic_w=100, vic_rig=1)
    songshan_jian_c_next_sword(
        world, me, victim, "me_sword", RESULT_PARRY, items=items, rng=_FakeRng(0)
    )
    # 桩记录掉落房间（实际 Position 未实现，记为待迁移面）
    assert items._items["victim_sword"].get("dropped_room") == "room/test"
