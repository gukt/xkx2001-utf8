"""pilot 样本 id=6：feature/damage.c:die 迁移单元测试。

覆盖 die 主路径 + 关键分支：no_death 房转 unconcious、wizard 免死、
NPC destruct、killer_reward、无 killer 玩家谣言（string/无来源两段）、
死亡日志三段子分支（PKILL_DATA/PLAYER_DEATH）、风清扬弟子 break_relation、
战斗关系清理（remove_all_killer/remove_killer）、is_busy interrupt_me、
dismiss_team/save/move 阴间入口。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples import damage_c_die as dcd
from tools.sampling.pilot.samples.damage_c_die import damage_c_die

from xkx.runtime.components import (
    Attributes,
    FamilyComp,
    Identity,
    Marks,
    Position,
    Progression,
    RoomComp,
    Vitals,
)
from xkx.runtime.death import GHOST_FLAG, UNCONSCIOUS_FLAG
from xkx.runtime.ecs import World


def _world_with_room(
    *,
    room_id: str = "room/test",
    no_death: bool = False,
) -> tuple[World, int]:
    """建世界 + 一个房间，返回 (world, room_eid)。"""
    world = World()
    room_eid = world.new_entity()
    world.add(
        room_eid,
        RoomComp(room_id=room_id, short="", long="", no_death=no_death),
    )
    return world, room_eid


def _player(
    world: World,
    *,
    room_id: str = "room/test",
    name: str = "玩家",
    uid: str = "player",
    combat_exp: int = 100,
    potential: int = 50,
    family: str = "华山派",
    master_id: str = "huashan/laojiaoshi",
) -> int:
    """建玩家实体。"""
    eid = world.new_entity()
    world.add(
        eid,
        Identity(name=name, aliases=[uid], is_player=True, prototype_id=uid),
    )
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
    world.add(eid, Progression(combat_exp=combat_exp, potential=potential))
    world.add(eid, Attributes(family=family, gender="男性"))
    world.add(eid, FamilyComp(family_name=family, master_id=master_id))
    return eid


def _npc(
    world: World,
    *,
    room_id: str = "room/test",
    name: str = "强盗",
    uid: str = "bandit",
) -> int:
    """建 NPC 实体。"""
    eid = world.new_entity()
    world.add(
        eid,
        Identity(name=name, aliases=[uid], is_player=False, prototype_id=uid),
    )
    world.add(eid, Position(room_id=room_id))
    world.add(eid, Vitals())
    return eid


def _vitals(world: World, eid: int) -> Vitals:
    v = world.get(eid, Vitals)
    assert v is not None
    return v


def _marks(world: World, eid: int) -> Marks:
    m = world.get(eid, Marks)
    assert m is not None
    return m


# ──────────────────────── 主路径 ────────────────────────


def test_player_die_main_path_ghost_move(monkeypatch: Any) -> None:
    """玩家被杀：ghost=1 + move 阴间入口 + 血量清 1 + 后置 stub 调用。"""
    world, _ = _world_with_room()
    player = _player(world)
    killer = _npc(world, name="杀手", uid="killer")

    calls: dict[str, list[Any]] = {
        "dismiss": [],
        "break_marriage": [],
        "start_death": [],
    }
    monkeypatch.setattr(
        dcd, "dismiss_team", lambda w, e: calls["dismiss"].append(e)
    )
    monkeypatch.setattr(
        dcd, "break_marriage", lambda w, e: calls["break_marriage"].append(e)
    )
    monkeypatch.setattr(
        dcd, "_start_death", lambda w, e, t: calls["start_death"].append((e, t))
    )

    damage_c_die(world, player, killer_id=killer, tick=42)

    # ghost + move 阴间入口 + 血量清 1
    assert GHOST_FLAG in _marks(world, player).flags
    assert world.get(player, Position).room_id == "death/gate"
    assert _vitals(world, player).qi == 1
    assert _vitals(world, player).jingli == 1
    # 后置 stub 被调用
    assert calls["dismiss"] == [player]
    assert calls["break_marriage"] == [player]
    assert calls["start_death"] == [(player, 42)]


def test_player_die_my_killer_marked(monkeypatch: Any) -> None:
    """有 killer 时 set marks/my_killer = killer uid。"""
    world, _ = _world_with_room()
    player = _player(world)
    killer = _npc(world, name="杀手", uid="sha_shou")

    damage_c_die(world, player, killer_id=killer)

    # my_killer 经 "my_killer:<uid>" 约定写入 Marks.flags（Marks.flags 是 set
    # 不能存值，用 key:value 约定可解析出 killer uid）
    marks = _marks(world, player)
    assert dcd._has_mark(marks, "my_killer")
    assert dcd._marks_value(marks, "my_killer") == "sha_shou"


# ──────────────────────── no_death 房 ────────────────────────


def test_no_death_room_player_goes_unconcious() -> None:
    """no_death 房玩家不真正死亡，转 unconcious。"""
    world, _ = _world_with_room(room_id="nd", no_death=True)
    player = _player(world, room_id="nd")

    damage_c_die(world, player, tick=0)

    assert UNCONSCIOUS_FLAG in _marks(world, player).flags
    # no_death 分支早退：不设 ghost、不 move 阴间
    m = world.get(player, Marks)
    assert m is None or GHOST_FLAG not in m.flags
    assert world.get(player, Position).room_id == "nd"


# ──────────────────────── wizard 免死 ────────────────────────


def test_wizard_immortal_early_return(monkeypatch: Any) -> None:
    """wizard + env/immortal -> 免死早退，不扣血不进鬼魂。"""
    world, _ = _world_with_room()
    player = _player(world)

    monkeypatch.setattr(dcd, "wizardp", lambda *_a, **_k: True)
    monkeypatch.setattr(dcd, "query_env_immortal", lambda *_a, **_k: True)

    damage_c_die(world, player, tick=0)

    assert _vitals(world, player).qi == 100  # 未扣血
    m = world.get(player, Marks)
    assert m is None or GHOST_FLAG not in m.flags


def test_wizard_without_immortal_dies(monkeypatch: Any) -> None:
    """wizard 但 env/immortal=False -> 正常死亡（不早退）。"""
    world, _ = _world_with_room()
    player = _player(world)

    monkeypatch.setattr(dcd, "wizardp", lambda *_a, **_k: True)
    # query_env_immortal 保持桩默认 False

    damage_c_die(world, player, tick=0)

    assert GHOST_FLAG in _marks(world, player).flags


# ──────────────────────── NPC destruct ────────────────────────


def test_npc_destruct_removes_position() -> None:
    """NPC 死亡 -> destruct（移除 Position 从房间消失）。"""
    world, _ = _world_with_room()
    npc = _npc(world)

    damage_c_die(world, npc, tick=0)

    assert world.get(npc, Position) is None


# ──────────────────────── 谣言分支 ────────────────────────


def test_no_killer_player_rumor_anonymous(monkeypatch: Any) -> None:
    """无 killer 玩家死亡 -> 莫名其妙地死了 谣言。"""
    world, _ = _world_with_room()
    player = _player(world)

    channels: list[tuple[Any, str, str]] = []
    monkeypatch.setattr(
        dcd, "do_channel", lambda ob, ch, msg: channels.append((ob, ch, msg))
    )
    monkeypatch.setattr(dcd, "find_object", lambda _p: "aqingsao")

    damage_c_die(world, player, tick=0)

    assert len(channels) == 1
    ob, ch, msg = channels[0]
    assert ch == "rumor"
    assert "莫名其妙地死了" in msg
    assert ob == "aqingsao"


def test_no_killer_player_rumor_string_killer(monkeypatch: Any) -> None:
    """killer 为字符串来源 -> 拼接谣言。"""
    world, _ = _world_with_room()
    player = _player(world)

    channels: list[tuple[str, str]] = []
    monkeypatch.setattr(
        dcd, "do_channel", lambda _ob, ch, msg: channels.append((ch, msg))
    )
    monkeypatch.setattr(dcd, "find_object", lambda _p: None)
    monkeypatch.setattr(dcd, "load_object", lambda p: f"loaded:{p}")

    damage_c_die(world, player, killer_name="高山落石", tick=0)

    assert len(channels) == 1
    ch, msg = channels[0]
    assert ch == "rumor"
    assert "高山落石" in msg


# ──────────────────────── 死亡日志 ────────────────────────


def test_log_pkill_data_when_eff_damage_from(monkeypatch: Any) -> None:
    """last_eff_damage_from 存在 -> PKILL_DATA + PLAYER_DEATH 双写。"""
    world, _ = _world_with_room()
    player = _player(world, uid="xiake")
    # 模拟 receive_damage 写入 last_eff_damage_from（带 id 约定）
    marks = Marks()
    marks.flags.add("last_eff_damage_from:enemy_id")
    world.add(player, marks)

    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(dcd, "log_file", lambda f, m: logs.append((f, m)))

    damage_c_die(world, player, tick=0)

    files = [f for f, _ in logs]
    assert "PKILL_DATA" in files
    assert "PLAYER_DEATH" in files
    pkill_msg = next(m for f, m in logs if f == "PKILL_DATA")
    assert "PlayerKill" in pkill_msg
    assert "enemy_id" in pkill_msg
    assert "xiake" in pkill_msg


def test_log_player_death_when_object_killer(monkeypatch: Any) -> None:
    """objectp(killer) -> PLAYER_DEATH（被 killer 名 杀死）。"""
    world, _ = _world_with_room()
    player = _player(world, uid="victim")
    killer = _npc(world, name="黑衣人", uid="heiyiren")

    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(dcd, "log_file", lambda f, m: logs.append((f, m)))

    damage_c_die(world, player, killer_id=killer, tick=0)

    death_logs = [m for f, m in logs if f == "PLAYER_DEATH"]
    assert any("黑衣人" in m for m in death_logs)
    assert any("victim" in m for m in death_logs)
    # object killer 分支不写 PKILL_DATA
    assert "PKILL_DATA" not in [f for f, _ in logs]


def test_log_player_death_when_string_killer(monkeypatch: Any) -> None:
    """stringp(killer) -> PLAYER_DEATH（died from killer_name）。"""
    world, _ = _world_with_room()
    player = _player(world, uid="victim2")

    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(dcd, "log_file", lambda f, m: logs.append((f, m)))
    monkeypatch.setattr(dcd, "do_channel", lambda *_a, **_k: None)

    damage_c_die(world, player, killer_name="毒沼", tick=0)

    death_logs = [m for f, m in logs if f == "PLAYER_DEATH"]
    assert any("died from 毒沼" in m for m in death_logs)


# ──────────────────────── 战斗关系清理 ────────────────────────


def test_remove_all_killer_and_room_observers(monkeypatch: Any) -> None:
    """remove_all_killer(self) + 房间内每个 observer remove_killer(self)。"""
    world, _ = _world_with_room()
    player = _player(world)
    obs1 = _npc(world, name="旁观甲", uid="obs1")
    obs2 = _npc(world, name="旁观乙", uid="obs2")

    self_cleared: list[int] = []
    obs_cleared: list[tuple[int, int]] = []
    monkeypatch.setattr(
        dcd, "remove_all_killer", lambda w, e: self_cleared.append(e)
    )
    monkeypatch.setattr(
        dcd,
        "remove_killer",
        lambda w, observer, target: obs_cleared.append((observer, target)),
    )

    damage_c_die(world, player, tick=0)

    assert self_cleared == [player]
    # 两个旁观者都解除对玩家的 killer 关系（排除玩家自己）
    assert (obs1, player) in obs_cleared
    assert (obs2, player) in obs_cleared
    assert (player, player) not in obs_cleared


# ──────────────────────── 风清扬弟子 break_relation ────────────────────────


def test_feng_qingyang_disciple_break_relation(monkeypatch: Any) -> None:
    """风清扬弟子死亡 -> CHAR_D.break_relation。"""
    world, _ = _world_with_room()
    player = _player(world, master_id="feng qingyang")

    relations: list[int] = []
    monkeypatch.setattr(
        dcd, "break_relation", lambda w, e: relations.append(e)
    )

    damage_c_die(world, player, tick=0)

    assert relations == [player]


def test_non_feng_disciple_no_break_relation(monkeypatch: Any) -> None:
    """非风清扬弟子 -> 不调 break_relation。"""
    world, _ = _world_with_room()
    player = _player(world, master_id="huashan/laojiaoshi")

    relations: list[int] = []
    monkeypatch.setattr(
        dcd, "break_relation", lambda w, e: relations.append(e)
    )

    damage_c_die(world, player, tick=0)

    assert relations == []


# ──────────────────────── is_busy interrupt_me ────────────────────────


def test_busy_player_interrupted(monkeypatch: Any) -> None:
    """is_busy 玩家死亡 -> interrupt_me 被调。"""
    from xkx.runtime.components import EffectComp

    world, _ = _world_with_room()
    player = _player(world)
    busy = world.new_entity()
    world.add(
        busy,
        EffectComp(effect_id="exercise", kind="busy", target_id=player, duration=1),
    )

    interrupted: list[int] = []
    monkeypatch.setattr(
        dcd, "interrupt_me", lambda w, e: interrupted.append(e)
    )

    damage_c_die(world, player, tick=0)

    assert interrupted == [player]


def test_non_busy_player_not_interrupted(monkeypatch: Any) -> None:
    """非 busy 玩家死亡 -> 不调 interrupt_me。"""
    world, _ = _world_with_room()
    player = _player(world)

    interrupted: list[int] = []
    monkeypatch.setattr(
        dcd, "interrupt_me", lambda w, e: interrupted.append(e)
    )

    damage_c_die(world, player, tick=0)

    assert interrupted == []


# ──────────────────────── make_corpse + move ────────────────────────


def test_npc_die_makes_corpse_in_room() -> None:
    """NPC 死亡 -> 生成尸体 + 尸体留在死亡房间。"""
    world, _ = _world_with_room()
    npc = _npc(world, name="山贼", uid="shanzei")

    damage_c_die(world, npc, tick=0)

    # NPC 自身 destruct（Position 移除）
    assert world.get(npc, Position) is None
    # 房间内有一具尸体（Identity.name 含"尸体"）
    corpse_names = [
        world.get(e, Identity).name
        for e in world.entities_in_room("room/test")
        if world.get(e, Identity) is not None
    ]
    assert any("尸体" in n for n in corpse_names)


def test_player_die_saves(monkeypatch: Any) -> None:
    """玩家死亡 -> save 被调（_save 经 storage_system.mark_dirty，ADR-0057 决策 5）。

    death 属 entity 非 daemon，走 mark_dirty（周期 persist），不引入 per-eid 同步
    persist。原 FakeStorage 测 ``persist_now(eid)`` 是假绿（签名断裂未真存），
    改测 mark_dirty 对齐 runtime.death._save。
    """
    world, _ = _world_with_room()
    player = _player(world)

    dirtied: list[int] = []

    class _FakeStorage:
        def mark_dirty(self, eid: int) -> None:
            dirtied.append(eid)

    world.storage_system = _FakeStorage()  # type: ignore[attr-defined]

    damage_c_die(world, player, tick=0)

    assert player in dirtied
