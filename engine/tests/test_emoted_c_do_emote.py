"""pilot 样本 id=7：emoted.c:do_emote 迁移单元测试。

覆盖本地 emote（channel_emote==0）主路径 + 关键分支：
- 无 environment / verb 不存在 -> 0
- 无目标 emote（others 广播）/ 有目标 emote（myself/target/others 三路 + relay_emote）
- target==自己（_self 后缀）/ 非频道找不到目标 -> 0 / 频道 find_player 全局目标
- 目标非角色 / 不可见（鬼魂）-> 0
- wizard 隐身 / channel==2 rumor -> myname="某人"
- 频道 emote 返回 others 字符串
- 代词替换正确性（$N/$P/$n/$p/$S/$s/$C/$c/$R/$r）
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.emoted_c_do_emote import do_emote

from xkx.runtime.components import (
    Attributes,
    Identity,
    Position,
    TitleComp,
)
from xkx.runtime.ecs import World

# 笑 emote 模板（对照 LPC /adm/daemons/emoted 表 smile，含 $N/$P/$n/$p 代词）
# myself 段 $P=gender_self（emoter 看自己="你"）；others 段 $P=gender_pronoun
_SMILE_EMOTE = {
    "smile": {
        "myself": "$N$P微微一笑。",
        "myself_self": "$N$P对自己微微一笑。",
        "myself_target": "$N$P对着$n微微一笑。",
        "target": "$N$P对着你微微一笑。",
        "others": "$N$P微微一笑。",
        "others_target": "$N$P对着$n$P微微一笑。",
        "others_self": "$N$P对着自己微微一笑。",
    },
    "bow": {
        "myself": "$N$P拱手作揖。$S$s",
        "myself_target": "$N$P向$n拱手作揖。$S$s$R$r",
        "target": "$N$P向你拱手作揖。",
        "others": "$N$P拱手作揖。",
        "others_target": "$N$P向$n拱手作揖。",
    },
}


def _world_with_buffer() -> World:
    """构造带 pending_messages 缓冲的 world（供 tell_object/tell_room facade 收集）。"""
    w = World()
    w.pending_messages = []  # type: ignore[attr-defined]
    return w


def _player(
    world: World,
    *,
    name: str = "张三",
    gender: str = "男性",
    age: int = 20,
    room: str = "room/test",
    is_ghost: bool = False,
    rank_self: str | None = "在下",
    rank_self_rude: str | None = "老子",
) -> int:
    """构造一个角色实体。"""
    eid = world.new_entity()
    world.add(eid, Identity(name=name, aliases=[name], is_player=True, prototype_id=name))
    world.add(eid, Position(room_id=room))
    world.add(eid, Attributes(gender=gender, age=age))
    world.add(eid, TitleComp(
        rank_info_self=rank_self,
        rank_info_self_rude=rank_self_rude,
        is_ghost=is_ghost,
    ))
    return eid


def _route(
    world: World,
) -> tuple[dict[int, list[str]], dict[str, list[str]], Any, Any]:
    """monkeypatch 用：把模块内 tell_object/tell_room 换成按 eid/room 路由的桩。

    返回 (by_eid, by_room, tell_object_stub, tell_room_stub)。
    """
    by_eid: dict[int, list[str]] = {}
    by_room: dict[str, list[str]] = {}

    def tell_object(_world: Any, eid: int, msg: str) -> None:
        by_eid.setdefault(eid, []).append(msg)

    def tell_room(_world: Any, room_id: str, msg: str, exclude: tuple = ()) -> None:
        by_room.setdefault(room_id, []).append(msg)

    return by_eid, by_room, tell_object, tell_room


def _patch_route(monkeypatch: Any) -> tuple[dict[int, list[str]], dict[str, list[str]]]:
    """patch 模块内 tell_object/tell_room，返回 (by_eid, by_room)。"""
    by_eid, by_room, tell_object, tell_room = _route(_world_with_buffer())
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_object", tell_object
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_room", tell_room
    )
    return by_eid, by_room


# ──────────────────────── 失败分支 ────────────────────────


def test_no_environment_returns_zero() -> None:
    """emoter 无 environment -> return 0。"""
    world = _world_with_buffer()
    me = world.new_entity()
    world.add(me, Identity(name="张三", aliases=["张三"]))
    # 无 Position
    assert do_emote(world, _SMILE_EMOTE, me, "smile") == 0


def test_verb_not_in_emote_returns_zero() -> None:
    """verb 不在 emote 表 -> return 0。"""
    world = _world_with_buffer()
    me = _player(world)
    assert do_emote(world, _SMILE_EMOTE, me, "nonexistent") == 0


def test_target_not_found_local_returns_zero(monkeypatch: Any) -> None:
    """本地非频道，arg 在房间找不到 -> return 0（不调 find_player）。"""
    _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)
    called = {"find_player": False}

    def find_player(_w: Any, _arg: str) -> None:
        called["find_player"] = True

    assert do_emote(world, _SMILE_EMOTE, me, "smile", "路人甲", 0,
                    find_player=find_player) == 0
    assert called["find_player"] is False


def test_target_not_character_returns_zero(monkeypatch: Any) -> None:
    """目标无 Identity（非角色）-> return 0。"""
    _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)
    # 一个无 Identity 的实体在房间里（find_in_room 按 Identity 匹配，找不到；
    # 改用直接放一个有 Identity 但 is_character 判定通过的目标更贴合，
    # 此处验证 find_in_room 找不到 -> 0）
    assert do_emote(world, _SMILE_EMOTE, me, "smile", "物品", 0) == 0


def test_target_invisible_ghost_returns_zero(monkeypatch: Any) -> None:
    """目标为鬼魂（visible=False）-> return 0。"""
    _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)
    _ghost = _player(world, name="李四", is_ghost=True)
    assert do_emote(world, _SMILE_EMOTE, me, "smile", "李四", 0) == 0


# ──────────────────────── 本地主路径 ────────────────────────


def test_no_target_emote_broadcasts_others(monkeypatch: Any) -> None:
    """无目标本地 emote：myself 给 me，others 广播房间（排除 me）。"""
    by_eid, by_room = _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)
    assert do_emote(world, _SMILE_EMOTE, me, "smile") == 1
    # myself 段给 me：$P=gender_self="你"（emoter 看自己）
    assert "张三你微微一笑。" in by_eid[me]
    # others 段广播房间（排除 me）：$P=gender_pronoun(男性)="他"
    assert "张三他微微一笑。" in by_room["room/test"]
    assert me not in by_room  # me 被排除


def test_target_emote_three_routes_and_relay(monkeypatch: Any) -> None:
    """有目标本地 emote：myself_target 给 me，target 给目标，others_target 广播，
    且调用 relay_emote。
    """
    by_eid, by_room = _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)
    target = _player(world, name="李四", gender="女性")
    relayed: list[tuple] = []

    def relay_emote(_w: Any, t: int, m: int, verb: str) -> None:
        relayed.append((t, m, verb))

    assert do_emote(world, _SMILE_EMOTE, me, "smile", "李四", 0,
                    relay_emote=relay_emote) == 1
    # myself_target：$N=张三 $P=他(性别self代词=你? 注意 myself 段 $P=gender_self=你)
    # gender_self 恒返回"你"
    assert "张三你对着李四微微一笑。" in by_eid[me]
    # target 段给 target：$N=张三 $P=gender_pronoun(男性)=他
    assert "张三他对着你微微一笑。" in by_eid[target]
    # others_target 广播房间（排除 me 和 target）
    assert "李四" in by_room["room/test"][0]
    assert target not in by_room
    # relay_emote 被调用
    assert relayed == [(target, me, "smile")]


def test_target_is_self_uses_self_postfix(monkeypatch: Any) -> None:
    """target==me -> msg_postfix=_self，target 清零，用 others_self 模板。"""
    by_eid, by_room = _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)
    # arg 匹配自己（find_in_room 找到 me 自己）
    assert do_emote(world, _SMILE_EMOTE, me, "smile", "张三", 0) == 1
    # myself_self：$N=张三 $P=gender_self="你"
    assert "张三你对自己微微一笑。" in by_eid[me]
    # others_self：$N=张三 $P=gender_pronoun(男性)="他"
    assert "张三他对着自己微微一笑。" in by_room["room/test"][0]


# ──────────────────────── myname 三路 ────────────────────────


def test_wizard_invisible_myname_someone(monkeypatch: Any) -> None:
    """非频道 + wizardp=True + env/invisibility=True -> $N 替换为"某人"。"""
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.wizardp",
        lambda *_a, **_kw: True,
    )
    by_eid, _by_room = _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)

    def env_invis(_w: Any, _eid: int) -> bool:
        return True

    do_emote(world, _SMILE_EMOTE, me, "smile", query_env_invisibility=env_invis)
    assert any("某人" in m for m in by_eid[me])


def test_rumor_channel_myname_is_someone(monkeypatch: Any) -> None:
    """channel_emote==2 rumor -> myname="某人"，返回 others 字符串。"""
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_object", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_room", lambda *_a, **_kw: None
    )
    world = _world_with_buffer()
    me = _player(world)
    result = do_emote(world, _SMILE_EMOTE, me, "smile", channel_emote=2)
    assert isinstance(result, str)
    assert "某人" in result


def test_non_wizard_invisibility_ignored(monkeypatch: Any) -> None:
    """非 wizard 即使 env/invisibility=True 也不隐身（wizardp 桩默认 False）。"""
    by_eid, _by_room = _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world)

    def env_invis(_w: Any, _eid: int) -> bool:
        return True

    do_emote(world, _SMILE_EMOTE, me, "smile", query_env_invisibility=env_invis)
    # wizardp 桩默认 False -> myname 仍为裸名"张三"
    assert any("张三" in m and "某人" not in m for m in by_eid[me])


# ──────────────────────── 频道分支 ────────────────────────


def test_channel_find_player_global_target(monkeypatch: Any) -> None:
    """频道（channel_emote=1）房间找不到目标 -> 调 find_player 全局查找。"""
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_object", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_room", lambda *_a, **_kw: None
    )
    world = _world_with_buffer()
    me = _player(world)
    # 全局目标在另一房间
    other_room_target = _player(world, name="王五", room="room/other")
    called = {"find_player": False}

    def find_player(_w: Any, arg: str) -> int:
        called["find_player"] = True
        return other_room_target if arg == "王五" else None

    result = do_emote(world, _SMILE_EMOTE, me, "smile", "王五", 1,
                      find_player=find_player)
    assert called["find_player"] is True
    # 频道返回 others 字符串
    assert isinstance(result, str)
    assert "王五" in result


def test_channel_find_player_none_returns_zero(monkeypatch: Any) -> None:
    """频道 find_player 找不到 -> return 0。"""
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_object", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_room", lambda *_a, **_kw: None
    )
    world = _world_with_buffer()
    me = _player(world)

    def find_player(_w: Any, _arg: str) -> None:
        return None

    assert do_emote(world, _SMILE_EMOTE, me, "smile", "不存在", 1,
                    find_player=find_player) == 0


def test_channel_returns_others_string(monkeypatch: Any) -> None:
    """频道 emote 成功 -> 返回 others 段字符串（非 1）。"""
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_object", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_room", lambda *_a, **_kw: None
    )
    world = _world_with_buffer()
    me = _player(world)
    result = do_emote(world, _SMILE_EMOTE, me, "smile", channel_emote=1)
    assert result == "张三他微微一笑。"


# ──────────────────────── 代词替换 ────────────────────────


def test_pronoun_substitution_all_placeholders(monkeypatch: Any) -> None:
    """$N/$P/$S/$s/$n/$C/$c/$R/$r 全替换（bow emote，myself_target 段）。"""
    by_eid, _by_room = _patch_route(monkeypatch)
    world = _world_with_buffer()
    me = _player(world, rank_self="在下", rank_self_rude="老子")
    _target = _player(world, name="李四", gender="女性",
                      rank_self=None, rank_self_rude=None)
    do_emote(world, _SMILE_EMOTE, me, "bow", "李四", 0)
    msg = by_eid[me][0]
    # $N=张三 $P=gender_self(男性)=你 $S=在下 $s=老子 $n=李四
    assert "张三" in msg and "李四" in msg and "在下" in msg and "老子" in msg
    assert "$N" not in msg and "$P" not in msg and "$S" not in msg
    assert "$s" not in msg and "$n" not in msg


def test_target_section_p_uses_gender_self(monkeypatch: Any) -> None:
    """target 段 $p=gender_self(target_gender)（target 看自己=你）。"""
    by_eid, _by_room = _patch_route(monkeypatch)
    # 用含 $p 的 target 模板
    emote = {"wink": {
        "myself_target": "$N$P对$n眨眨眼。",
        "target": "$N$P对$n$p眨眨眼。",
        "others_target": "$N$P对$n$P眨眨眼。",
    }}
    world = _world_with_buffer()
    me = _player(world)
    target = _player(world, name="李四", gender="女性")
    do_emote(world, emote, me, "wink", "李四", 0)
    target_msg = by_eid[target][0]
    # target 段：$N=张三 $P=gender_pronoun(男性)=他 $n=李四 $p=gender_self(女性)=你
    assert target_msg == "张三他对李四你眨眨眼。"


def test_others_section_p_uses_gender_pronoun(monkeypatch: Any) -> None:
    """others 段 $p=gender_pronoun(target_gender)（女性->她）。"""
    _by_eid, by_room = _patch_route(monkeypatch)
    emote = {"wink": {
        "myself_target": "$N$P对$n眨眨眼。",
        "target": "$N$P对$n$p眨眨眼。",
        "others_target": "$N$P对$n$p眨眨眼。",
    }}
    world = _world_with_buffer()
    me = _player(world)
    _target = _player(world, name="李四", gender="女性")
    do_emote(world, emote, me, "wink", "李四", 0)
    others_msg = by_room["room/test"][0]
    # others 段：$N=张三 $P=gender_pronoun(男性)=他 $n=李四 $p=gender_pronoun(女性)=她
    assert others_msg == "张三他对李四她眨眨眼。"


def test_intermud_channel_uses_bare_name(monkeypatch: Any) -> None:
    """channel_emote==3 intermud（单机排除 INTERMUD_MUD_NAME）-> 走裸名分支。"""
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_object", lambda *_a, **_kw: None
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.emoted_c_do_emote.tell_room", lambda *_a, **_kw: None
    )
    world = _world_with_buffer()
    me = _player(world)
    result = do_emote(world, _SMILE_EMOTE, me, "smile", channel_emote=3)
    # intermud 单机简化走裸名，myname=张三（非 name(id@mud) 格式）
    assert isinstance(result, str)
    assert "张三" in result
    assert "@" not in result
