"""层0 schema + IR 编译测试。"""

from __future__ import annotations

from xkx.dsl.ir import IR_SCHEMA_VERSION, compile_room, compile_scene
from xkx.dsl.layer0 import NpcDef, RoomDef, load_rooms


def test_room_def_minimal() -> None:
    r = RoomDef(id="city/chaguan", short="春来茶馆", long="茶香沁入心脾。")
    assert r.exits == {}
    assert r.objects == {}


def test_room_def_exits_objects() -> None:
    r = RoomDef(
        id="city/chaguan",
        short="春来茶馆",
        long="...",
        exits={"south": "city/xidajie1"},
        objects={"city/npc/wang_lifa": 1},
    )
    assert r.exits["south"] == "city/xidajie1"
    assert r.objects["city/npc/wang_lifa"] == 1


def test_npc_def_combat() -> None:
    n = NpcDef(
        id="city/npc/bing",
        name="官兵",
        attitude="heroism",
        str_=24,
        dex_=16,
        combat_exp=10000,
        skills={"unarmed": 40, "blade": 40},
        weapon="blade",
        chat_chance_combat=10,
        chat_msg_combat=["官兵喝道：大胆刁民！"],
    )
    assert n.attitude == "heroism"
    assert n.weapon == "blade"
    assert n.skills["blade"] == 40


def test_compile_scene_ir() -> None:
    rooms = [RoomDef(id="r1", short="A", long="aa", exits={"e": "r2"})]
    npcs = [NpcDef(id="n1", name="兵", combat_exp=100)]
    ir = compile_scene(rooms, npcs)
    assert ir["schema_version"] == IR_SCHEMA_VERSION
    assert ir["rooms"][0]["id"] == "r1"
    assert ir["rooms"][0]["exits"] == {"e": "r2"}
    assert ir["npcs"][0]["kind"] == "npc"
    assert ir["npcs"][0]["name"] == "兵"


def test_compile_room_roundtrip() -> None:
    r = RoomDef(id="r", short="s", long="l", exits={"n": "r2"}, objects={"n1": 2})
    ir = compile_room(r)
    assert ir["kind"] == "room"
    assert ir["exits"] == {"n": "r2"}
    assert ir["objects"] == {"n1": 2}


def test_yaml_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "rooms.yaml"
    p.write_text(
        "- id: city/chaguan\n"
        "  short: 春来茶馆\n"
        "  long: 茶香。\n"
        "  exits:\n"
        "    south: city/xidajie1\n",
        encoding="utf-8",
    )
    rooms = load_rooms(p)
    assert len(rooms) == 1
    assert rooms[0].id == "city/chaguan"
    assert rooms[0].exits == {"south": "city/xidajie1"}
