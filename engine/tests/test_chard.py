"""CHAR_D setup_char 编排层行为等价测试（B 类补全，对照 adm/daemons/chard.c）。

覆盖 chard.c L22-114：种族 dispatch（human 调 setup_race / 非人类 noop / 未知
raise）、dbase 兜底（jing/qi/jingli）、eff 钳位、玩家 neili/jingli 超限钳位、
NPC force 自动设置、shen 不覆盖已有值、max_encumbrance 兜底。
"""

from __future__ import annotations

import pytest

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import RoomDef
from xkx.runtime.chard import setup_char
from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.skill import map_skill, set_skill
from xkx.runtime.world import build_world, spawn_player


def _player_world(*, is_player: bool = True, con: int = 30, str_: int = 25) -> tuple:
    """构建 1 房间 + 1 玩家场景。

    属性设非默认值（20）避免 setup_race 属性随机改值，保证编排层测试确定性。
    is_player=False 模拟 NPC（测 NPC force 自动设置分支）。
    """
    room = RoomDef(id="room/test", short="测试", long="测试房间。")
    ir = compile_scene([room], [])
    world, _, _ = build_world(ir)
    pid = spawn_player(world, "玩家", "room/test")
    attrs = world.get(pid, Attributes)
    if attrs:
        attrs.con_ = con
        attrs.str_ = str_
        attrs.dex_ = 25
        attrs.int_ = 25
        attrs.age = 22  # 非默认 20，避免 setup_race 改 age
    ident = world.get(pid, Identity)
    if ident:
        ident.is_player = is_player
    return world, pid


# ──────────────────────── 种族 dispatch（chard.c:27-59） ────────────────────────


def test_setup_char_default_race_is_human():
    """race 未传兜底"人类"并调 setup_race（chard.c:27-34）。"""
    world, pid = _player_world()
    race = setup_char(world, pid)
    assert race == "人类"
    assert world.get(pid, Vitals).max_jing > 0  # setup_race 设了 max_jing


def test_setup_char_unknown_race_raises():
    """未知种族名 raise（chard.c:57-58 default error）。"""
    world, pid = _player_world()
    with pytest.raises(ValueError, match="undefined race"):
        setup_char(world, pid, race="外星人")


def test_setup_char_nonhuman_race_noop_no_setup_race():
    """已知非人类种族 noop（不调 setup_race，max_jing 不被改），返回种族名。"""
    world, pid = _player_world()
    before = world.get(pid, Vitals).max_jing
    race = setup_char(world, pid, race="妖魔")
    assert race == "妖魔"
    assert world.get(pid, Vitals).max_jing == before  # setup_race 未跑


# ──────────────────────── dbase 兜底（chard.c:64-66） ────────────────────────


def test_setup_char_fills_jing_qi_jingli_when_zero():
    """jing/qi/jingli 未初始化（<=0）兜底 = max（chard.c:64-66）。"""
    world, pid = _player_world()
    v = world.get(pid, Vitals)
    v.jing = 0
    v.qi = 0
    v.jingli = 0
    setup_char(world, pid)
    v = world.get(pid, Vitals)
    assert v.jing == v.max_jing
    assert v.qi == v.max_qi
    assert v.jingli == v.max_jingli


# ──────────────────────── eff 钳位（chard.c:68-69） ────────────────────────


def test_setup_char_clamps_eff_to_max():
    """eff_jing/eff_qi 超 max 钳到 max（chard.c:68-69）。"""
    world, pid = _player_world()
    v = world.get(pid, Vitals)
    v.eff_jing = 99999
    v.eff_qi = 99999
    setup_char(world, pid)
    v = world.get(pid, Vitals)
    assert v.eff_jing == v.max_jing
    assert v.eff_qi == v.max_qi


# ──────────────────────── 玩家 neili/jingli 超限钳位（chard.c:75-92） ────────────────────────


def test_setup_char_player_neili_capped():
    """玩家 force 有效>基础时 max_neili 钳到 force*con*2/3（chard.c:75-81）。"""
    world, pid = _player_world(con=30)  # is_player=True
    set_skill(world, pid, "force", 100)
    set_skill(world, pid, "neigong", 200)
    map_skill(world, pid, "force", "neigong")  # force_eff = 50 + 200 = 250 > 100
    v = world.get(pid, Vitals)
    v.max_neili = 9999
    v.neili = 9999
    setup_char(world, pid)
    cap = 100 * 30 * 2 // 3  # 2000
    v = world.get(pid, Vitals)
    assert v.max_neili == cap
    assert v.neili == cap


# ──────────────────────── NPC force 自动设置（chard.c:94-95） ────────────────────────


def test_setup_char_npc_force_auto_set():
    """NPC 有 max_neili 但 force<1 时 set_skill("force", max_neili/6)（chard.c:94-95）。"""
    world, pid = _player_world(is_player=False)  # NPC
    world.get(pid, Vitals).max_neili = 600
    setup_char(world, pid)
    assert world.get(pid, Skills).levels.get("force") == 100  # 600 // 6


# ──────────────────────── shen（chard.c:97-104） ────────────────────────


def test_setup_char_shen_not_overwrite_existing():
    """TitleComp.shen 已有非 0 值时不覆盖（chard.c:99 undefinedp 语义）。"""
    world, pid = _player_world()
    world.add(pid, TitleComp(shen=500))
    setup_char(world, pid)
    assert world.get(pid, TitleComp).shen == 500


# ──────────────────────── max_encumbrance（chard.c:109-111） ────────────────────────


def test_setup_char_fills_max_encumbrance():
    """max_encumbrance 为 0 时补 str*5000（chard.c:109-111 简化）。"""
    world, pid = _player_world(str_=25)
    world.get(pid, Equipment).max_encumbrance = 0
    setup_char(world, pid)
    assert world.get(pid, Equipment).max_encumbrance == 25 * 5000
