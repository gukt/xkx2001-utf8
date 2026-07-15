"""消息分发 facade（LPC simul_efun/message.c ``tell_object``/``tell_room``/``message_vision``）。

M3-1 最小实现：

- ``tell_object`` 写 ``world.pending_messages`` 全局缓冲（单玩家 demo 全量打印）；
  ``eid`` 参数留接口，按实体 session 分桶 + ``ConnectionSystem.push_event`` 后置 M3。
- ``message_vision`` 三段视角照 [simul_efun/message.c:6-33](../../../adm/simul_efun/message.c)
  实现，**不复用 ``PronounService.render``**--后者是单段 speaker 视角，本函数三段视角
  切换（me 段 viewer=me、others 段 viewer=第三方），直接照 replace_string 规则。
- 收敛 ``death.py``/``governance.py`` 私有 ``_tell`` 副本。

``message(msgclass,...)`` 完整路由层（``receive_message``/``relay_message``/``block_msg``/
``in_input``）后置 M3。gender_self 恒 "你"（[pronoun.py](pronoun.py) 对齐 gender.c）。
"""

from __future__ import annotations

from xkx.runtime.components import Attributes, Identity
from xkx.runtime.ecs import World
from xkx.runtime.pronoun import gender_pronoun, gender_self
from xkx.runtime.query import environment


def tell_object(world: World, eid: int, msg: str) -> None:
    """向实体定向输出消息（LPC ``tell_object``，simul_efun/message.c:35）。

    M3-1：写 ``world.pending_messages`` 全局缓冲。``eid`` 参数留接口，按实体 session
    分桶 + WS 推送后置 M3（当前单玩家 demo 全量打印，多实体分发后置）。
    """
    pending = getattr(world, "pending_messages", None)
    if pending is not None:
        pending.append(msg)


def tell_room(
    world: World, room_id: str, msg: str, exclude: tuple[int, ...] = ()
) -> None:
    """房间广播（LPC ``tell_room``，simul_efun/message.c:40）。

    遍历 ``room_id`` 内实体，``exclude`` 排除，逐个 ``tell_object``。
    """
    for eid in world.entities_in_room(room_id):
        if eid not in exclude:
            tell_object(world, eid, msg)


def message_vision(
    world: World, msg: str, me: int, you: int | None = None
) -> None:
    """代词渲染 + 三段广播（LPC ``message_vision``，simul_efun/message.c:6-33）。

    产三段视角文本分别路由（对照 simul_efun replace_string 顺序）：

    - str1 给 me：``$P``/``$N`` = ``gender_self(me)`` = "你"；若有 you，再
      ``$p`` = ``gender_pronoun(you)``、``$n`` = you 名
    - str2 给 you：``$P`` = ``gender_pronoun(me)``、``$p``/``$n`` = ``gender_self(you)``
      = "你"、``$N`` = me 名
    - str3 给 room 其余（排除 me+you）：``$P``/``$N`` = me 名；若有 you，
      ``$p``/``$n`` = you 名

    不复用 ``PronounService.render``（单段 speaker 视角 vs 本函数三段视角切换）。
    """
    me_name = _name(world, me)
    me_gender = _gender(world, me)
    # str1 给 me：$P/$N -> gender_self(me) = "你"
    str1 = msg.replace("$P", gender_self(me_gender)).replace(
        "$N", gender_self(me_gender)
    )
    # str3 给 room 其余：$P/$N -> me 名
    str3 = msg.replace("$P", me_name).replace("$N", me_name)
    exclude: tuple[int, ...] = (me,)
    if you is not None:
        you_name = _name(world, you)
        you_gender = _gender(world, you)
        # str2 给 you：$P -> gender_pronoun(me)、$p/$n -> gender_self(you)="你"、$N -> me 名
        str2 = (
            msg.replace("$P", gender_pronoun(me_gender))
            .replace("$p", gender_self(you_gender))
            .replace("$N", me_name)
            .replace("$n", gender_self(you_gender))
        )
        tell_object(world, you, str2)
        # str1 再补 you 视角：$p -> gender_pronoun(you)、$n -> you 名
        str1 = str1.replace("$p", gender_pronoun(you_gender)).replace(
            "$n", you_name
        )
        # str3 再补 you：$p/$n -> you 名
        str3 = str3.replace("$p", you_name).replace("$n", you_name)
        exclude = (me, you)
    tell_object(world, me, str1)
    room_id = environment(world, me)
    if room_id is not None:
        tell_room(world, room_id, str3, exclude=exclude)


def _gender(world: World, eid: int) -> str:
    """取实体性别（LPC ``query("gender")``，message_vision 用）。"""
    attrs = world.get(eid, Attributes)
    return attrs.gender if attrs else "男性"


def _name(world: World, eid: int) -> str:
    """取实体显示名（LPC ``name()``，message_vision 用；纯名非 name(id) 格式）。"""
    ident = world.get(eid, Identity)
    return ident.name if ident else ""
