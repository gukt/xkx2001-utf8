"""runtime/message.py facade 单测：tell_object/tell_room/message_vision 三段视角。

对照 LPC simul_efun/message.c:6-33 的三段视角规则：me 段 $P/$N=gender_self="你"、
you 段 $P=gender_pronoun(me)、others 段 $P/$N=me 名。M3-1 tell_object 写全局
pending_messages（按实体分桶后置 M3）。
"""

from __future__ import annotations

from xkx.runtime.components import Attributes, Identity, Position
from xkx.runtime.ecs import World
from xkx.runtime.message import message_vision, tell_object, tell_room


def _world() -> World:
    world = World()
    world.pending_messages = []  # type: ignore[attr-defined]
    return world


def _add(world: World, name: str, gender: str, room: str = "room/test") -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name=name))
    world.add(eid, Position(room_id=room))
    world.add(eid, Attributes(gender=gender))
    return eid


def test_tell_object_writes_pending() -> None:
    """tell_object 写 world.pending_messages。"""
    world = _world()
    me = _add(world, "张三", "男性")
    tell_object(world, me, "你好")
    assert world.pending_messages == ["你好"]


def test_tell_room_broadcast_excludes() -> None:
    """tell_room 广播给房间内实体，exclude 跳过。"""
    world = _world()
    me = _add(world, "张三", "男性")
    _add(world, "王五", "男性")
    tell_room(world, "room/test", "广播", exclude=(me,))
    # me 被 exclude，仅 other 收到
    assert world.pending_messages == ["广播"]


def test_message_vision_three_views() -> None:
    """me(男,张三) 击 you(女,李四)：三段视角分化。"""
    world = _world()
    me = _add(world, "张三", "男性")
    you = _add(world, "李四", "女性")
    _add(world, "王五", "男性")
    message_vision(world, "$P一招击向$n。", me, you)
    msgs = world.pending_messages
    # me 段：$P=你、$n=李四
    assert "你一招击向李四。" in msgs
    # you 段：$P=他(gender_pronoun 男)、$n=你
    assert "他一招击向你。" in msgs
    # others 段：$P=张三、$n=李四
    assert "张三一招击向李四。" in msgs


def test_message_vision_you_female_pronoun() -> None:
    """you 为女性：me 段 $p=她(gender_pronoun 女)。"""
    world = _world()
    me = _add(world, "张三", "男性")
    you = _add(world, "李四", "女性")
    _add(world, "王五", "男性")  # 房间第三人收 others 段
    message_vision(world, "$P看着$p。", me, you)
    msgs = world.pending_messages
    # me 段：$P=你、$p=她(gender_pronoun 女)
    assert "你看着她。" in msgs
    # you 段：$P=他、$p=你(gender_self)
    assert "他看着你。" in msgs
    # others 段：$P=张三、$p=李四
    assert "张三看着李四。" in msgs


def test_message_vision_no_you() -> None:
    """you=None：只 me 段 + others 段，无 you 段。"""
    world = _world()
    me = _add(world, "张三", "男性")
    _add(world, "王五", "男性")
    message_vision(world, "$P施展武功。", me, you=None)
    msgs = world.pending_messages
    # me 段：$P=你
    assert "你施展武功。" in msgs
    # others 段：$P=张三
    assert "张三施展武功。" in msgs
    # me 收 str1 + other 收 str3（me 被 exclude 不收 str3）= 2 条
    assert len(msgs) == 2


def test_message_vision_dollar_n_me_view_is_self() -> None:
    """$N 在 me 段也是 gender_self='你'（simul_efun/message.c:14）。"""
    world = _world()
    me = _add(world, "张三", "男性")
    _add(world, "王五", "男性")  # 房间第三人收 others 段
    message_vision(world, "$N思考。", me)
    assert "你思考。" in world.pending_messages
    # others 段 $N=张三
    assert "张三思考。" in world.pending_messages


def test_message_vision_others_exclude_me_and_you() -> None:
    """others 段排除 me+you：房间第三人收 str3，me/you 不收 str3。"""
    world = _world()
    me = _add(world, "张三", "男性")
    you = _add(world, "李四", "女性")
    _add(world, "王五", "男性")
    message_vision(world, "$P出手。", me, you)
    # other 只收 others 段（$P=张三 -> "张三出手。"）
    assert "张三出手。" in world.pending_messages
    # me 段 "你出手。" + you 段 "他出手。" + others 段 "张三出手。"
    assert "你出手。" in world.pending_messages
    assert "他出手。" in world.pending_messages
    # 共 3 条（me/you/other 各一）
    assert len(world.pending_messages) == 3
