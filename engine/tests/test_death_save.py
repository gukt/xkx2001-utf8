"""death 存档真单测（ADR-0057 决策 5）。

第一批把 ``runtime.death._save`` 从断裂的 ``persist_now(eid)`` 改为 ``mark_dirty(eid)``
（走 ADR-0022 §1 内存权威 + 周期 persist）。本文件补真单测：die / death_penalty 后
``storage.mark_dirty(eid)`` 被调用，确认断裂修复不降级。

ADR-0057 决策 5：death 属 entity 非 daemon，走 mark_dirty，不引入 per-eid 同步
persist（滑坡论证见 ADR）。
"""

from __future__ import annotations

from typing import Any

from xkx.runtime import death
from xkx.runtime.components import (
    Attributes,
    Identity,
    Marks,
    Position,
    Progression,
    RoomComp,
    Vitals,
)
from xkx.runtime.ecs import World


class _FakeStorage:
    """记录 mark_dirty 调用的 spy（对齐 death._save/_mark_dirty 读取 world.storage_system）。"""

    def __init__(self) -> None:
        self.dirtied: list[int] = []

    def mark_dirty(self, eid: int) -> None:
        self.dirtied.append(eid)


def _world_with_room(*, no_death: bool = False) -> tuple[World, int]:
    world = World()
    room_eid = world.new_entity()
    world.add(
        room_eid,
        RoomComp(room_id="room/test", short="", long="", no_death=no_death),
    )
    return world, room_eid


def _player(world: World, *, room_id: str = "room/test") -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name="玩家", is_player=True, prototype_id="player"))
    world.add(eid, Position(room_id=room_id))
    world.add(
        eid,
        Vitals(
            qi=100,
            max_qi=100,
            eff_qi=100,
            jing=100,
            max_jing=100,
            eff_jing=100,
            jingli=100,
            max_jingli=100,
        ),
    )
    world.add(eid, Progression(combat_exp=100, potential=50))
    world.add(eid, Attributes(gender="男性"))
    world.add(eid, Marks())
    return eid


def _npc(world: World, *, room_id: str = "room/test") -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name="强盗", prototype_id="bandit"))
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Vitals())
    return eid


def _attach_storage(world: World) -> _FakeStorage:
    storage = _FakeStorage()
    world.storage_system = storage  # type: ignore[attr-defined]
    return storage


def _stub_governance(monkeypatch: Any) -> None:
    """桩掉阴间剧情（die 玩家分支末调 governance.enter_underworld，本测试只关心 mark_dirty）。

    death.die 函数内 ``from xkx.runtime import governance`` 后 ``governance.enter_underworld``
    是属性访问，monkeypatch 模块属性生效。
    """
    from xkx.runtime import governance

    monkeypatch.setattr(governance, "enter_underworld", lambda *a, **k: None)


# ──────────────────────── death_penalty ────────────────────────


def test_death_penalty_marks_dirty() -> None:
    """death_penalty 后 mark_dirty(eid) 被调（combat_exp>20 扣减分支）。"""
    world, _ = _world_with_room()
    player = _player(world)
    storage = _attach_storage(world)

    death.death_penalty(world, player)

    assert player in storage.dirtied


def test_death_penalty_high_combat_exp_marks_dirty() -> None:
    """death_penalty 分支 A（combat_exp>5000）mark_dirty 被调。"""
    world, _ = _world_with_room()
    player = _player(world)
    world.get(player, Progression).combat_exp = 10000  # type: ignore[union-attr]
    storage = _attach_storage(world)

    death.death_penalty(world, player)

    assert player in storage.dirtied


# ──────────────────────── die 玩家分支 ────────────────────────


def test_die_player_marks_dirty(monkeypatch: Any) -> None:
    """玩家 die 后 mark_dirty 被调（_save + _mark_dirty 路径）。"""
    _stub_governance(monkeypatch)
    world, _ = _world_with_room()
    player = _player(world)
    storage = _attach_storage(world)

    death.die(world, player, tick=0)

    assert player in storage.dirtied


def test_die_player_with_killer_marks_both_dirty(monkeypatch: Any) -> None:
    """玩家被击杀：玩家 + killer 都 mark_dirty（killer_reward 标脏 killer）。"""
    _stub_governance(monkeypatch)
    world, _ = _world_with_room()
    player = _player(world)
    killer = _npc(world)
    storage = _attach_storage(world)

    death.die(world, player, killer_id=killer, tick=0)

    assert player in storage.dirtied
    assert killer in storage.dirtied


# ──────────────────────── die NPC 分支 ────────────────────────


def test_die_npc_marks_dirty() -> None:
    """NPC die 后 mark_dirty 被调（NPC destruct 移除 Position 前标脏）。"""
    world, _ = _world_with_room()
    npc = _npc(world)
    storage = _attach_storage(world)

    death.die(world, npc, tick=0)

    assert npc in storage.dirtied


# ──────────────────────── 无 storage_system 不报错 ────────────────────────


def test_die_without_storage_does_not_raise(monkeypatch: Any) -> None:
    """无 storage_system 时 die 不报错（_save/_mark_dirty getattr None 回退）。"""
    _stub_governance(monkeypatch)
    world, _ = _world_with_room()
    player = _player(world)
    # 不挂 storage_system

    death.die(world, player, tick=0)  # 不应 raise

    assert not hasattr(world, "storage_system") or world.storage_system is None  # type: ignore[attr-defined]
