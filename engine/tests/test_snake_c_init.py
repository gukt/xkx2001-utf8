"""pilot 样本 id=10：snake.c:init 迁移单元测试。

覆盖主路径 + 失败分支 + RNG 分支：
- 无玩家 / 玩家不在房间 -> 不触发
- 白驼山弟子 -> 不触发（family 门控）
- kar+per < 30 概率达标 -> 触发攻击（initiate_combat 建敌对关系）
- kar+per 概率不达标 -> 不触发
- 非 interactive（NPC 而非玩家）-> 不触发
- query_kar/query_per monkeypatch 注入验证概率边界
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.snake_c_init import snake_c_init

from xkx.runtime.commands import Game
from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    NpcBehavior,
    Position,
)
from xkx.runtime.ecs import World


def _game(
    *,
    player_family: str = "丐帮",
    player_in_room: bool = True,
    snake_room: str = "room/snake",
) -> tuple[Game, int, int | None]:
    """构造 1 房间 + 蛇 NPC + 玩家的最小场景。

    返回 (game, snake_eid, player_eid)。player_in_room=False 时玩家不进蛇房。
    """
    world = World()

    snake = world.new_entity()
    world.add(snake, Identity(
        name="毒蛇", aliases=["snake", "she"], is_player=False, prototype_id="beast/snake"
    ))
    world.add(snake, Position(room_id=snake_room))
    # snake attitude=peaceful（L13），不走 _decide_room_enter_fight aggressive 分支
    world.add(snake, NpcBehavior(attitude="peaceful"))

    player = None
    if player_in_room:
        player = world.new_entity()
        world.add(player, Identity(
            name="玩家", aliases=["player"], is_player=True, prototype_id="player"
        ))
        world.add(player, Position(room_id=snake_room))
        world.add(player, Attributes(family=player_family, gender="男性", int_=20))
        world.add(player, CombatState())

    return Game(world, {}, rules=[]), snake, player


def _combat(world: World, eid: int) -> CombatState:
    cs = world.get(eid, CombatState)
    assert cs is not None
    return cs


def test_no_player_no_trigger() -> None:
    """房间内无玩家 -> 不触发攻击，返回空。"""
    game, snake, player = _game(player_in_room=False)
    assert player is None
    assert snake_c_init(game, snake) == []
    cs = game.world.get(snake, CombatState)
    assert cs is None or not cs.is_fighting


def test_baituoshan_family_no_trigger() -> None:
    """白驼山弟子不被蛇攻击（L39 family != "白驼山" 门控）。"""
    game, snake, player = _game(player_family="白驼山")
    assert player is not None
    # kar+per 即使概率达标，白驼山先短路
    assert snake_c_init(game, snake) == []
    cs = game.world.get(player, CombatState)
    assert cs is None or not cs.is_fighting


def test_prob_met_triggers_combat(monkeypatch: Any) -> None:
    """kar+per 概率达标（random < 30）-> 触发攻击，建立双向敌对关系。"""
    game, snake, player = _game(player_family="丐帮")
    assert player is not None
    # 注入 kar=10 per=15 -> kar+per=25，random(0,24) 必 < 30，概率达标
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 10,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 15,
    )
    # random.randint(0, 24) 返回任意值都 < 30
    monkeypatch.setattr("random.randint", lambda a, b: 24)
    msgs = snake_c_init(game, snake)
    assert msgs == ["你被攻击了！"]
    # 双向敌对：snake 与 player 互在 enemy_ids + is_fighting + killer_ids
    assert _combat(game.world, snake).is_fighting
    assert player in _combat(game.world, snake).enemy_ids
    assert snake in _combat(game.world, player).enemy_ids
    # kill_ob (to_death=True) 双向写 killer_ids（对齐 LPC killer 数组）
    assert player in _combat(game.world, snake).killer_ids


def test_prob_not_met_no_trigger(monkeypatch: Any) -> None:
    """kar+per 概率不达标（random >= 30）-> 不触发攻击。"""
    game, snake, player = _game(player_family="丐帮")
    assert player is not None
    # kar+per=40，random(0,39) 返回 35 >= 30 -> 不达标
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 20,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 20,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 35)
    assert snake_c_init(game, snake) == []
    cs = game.world.get(snake, CombatState)
    assert cs is None or not cs.is_fighting


def test_random_zero_boundary_triggers(monkeypatch: Any) -> None:
    """random(kar+per)=0（最小值）必 < 30 -> 触发。"""
    game, snake, player = _game()
    assert player is not None
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 5,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 5,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 0)
    assert snake_c_init(game, snake) == ["你被攻击了！"]


def test_random_29_boundary_triggers(monkeypatch: Any) -> None:
    """random(kar+per)=29（< 30 边界）-> 触发。"""
    game, snake, player = _game()
    assert player is not None
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 15,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 20,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 29)
    assert snake_c_init(game, snake) == ["你被攻击了！"]


def test_random_30_boundary_no_trigger(monkeypatch: Any) -> None:
    """random(kar+per)=30（>= 30 边界）-> 不触发。"""
    game, snake, player = _game()
    assert player is not None
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 15,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 20,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 30)
    assert snake_c_init(game, snake) == []


def test_npc_not_player_no_trigger() -> None:
    """房间内只有另一个 NPC（非玩家）-> interactive 近似筛掉，不触发。"""
    world = World()
    snake = world.new_entity()
    world.add(snake, Identity(
        name="毒蛇", aliases=["snake"], is_player=False, prototype_id="beast/snake"
    ))
    world.add(snake, Position(room_id="room/x"))
    world.add(snake, NpcBehavior(attitude="peaceful"))
    other_npc = world.new_entity()
    world.add(other_npc, Identity(
        name="野猪", aliases=["boar"], is_player=False, prototype_id="beast/boar"
    ))
    world.add(other_npc, Position(room_id="room/x"))
    game = Game(world, {}, rules=[])
    assert snake_c_init(game, snake) == []


def test_snake_no_position_no_trigger() -> None:
    """蛇无 Position（已死/未放房间）-> 直接返回空。"""
    world = World()
    snake = world.new_entity()
    world.add(snake, Identity(
        name="毒蛇", aliases=["snake"], is_player=False, prototype_id="beast/snake"
    ))
    world.add(snake, NpcBehavior(attitude="peaceful"))
    game = Game(world, {}, rules=[])
    assert snake_c_init(game, snake) == []


def test_default_kar_per_zero_no_trigger(monkeypatch: Any) -> None:
    """默认 query_kar/per 桩返回 0 -> kar+per=0，random(0,-1) 走 max(0,...)=0。

    random.randint(0,0)=0 < 30 -> 触发。验证默认桩（kar=per=0）行为：LPC 中
    kar+per 不会为 0（账号层生成），但桩回落 0 时 random 上限 0 仍 < 30 触发。
    """
    game, snake, player = _game()
    assert player is not None
    # 不 monkeypatch query_kar/per，用默认桩（返回 0）
    monkeypatch.setattr("random.randint", lambda a, b: 0)
    assert snake_c_init(game, snake) == ["你被攻击了！"]


def test_first_player_in_room_targeted(monkeypatch: Any) -> None:
    """房间内多玩家时，取第一个玩家为目标（对齐 this_player()）。"""
    world = World()
    snake = world.new_entity()
    world.add(snake, Identity(
        name="毒蛇", aliases=["snake"], is_player=False, prototype_id="beast/snake"
    ))
    world.add(snake, Position(room_id="room/multi"))
    world.add(snake, NpcBehavior(attitude="peaceful"))
    p1 = world.new_entity()
    world.add(p1, Identity(name="甲", aliases=["p1"], is_player=True, prototype_id="player"))
    world.add(p1, Position(room_id="room/multi"))
    world.add(p1, Attributes(family="丐帮"))
    world.add(p1, CombatState())
    p2 = world.new_entity()
    world.add(p2, Identity(name="乙", aliases=["p2"], is_player=True, prototype_id="player"))
    world.add(p2, Position(room_id="room/multi"))
    world.add(p2, Attributes(family="丐帮"))
    world.add(p2, CombatState())
    game = Game(world, {}, rules=[])
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 20,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 20,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 0)
    snake_c_init(game, snake)
    # 蛇与第一个玩家 p1 建敌对，p2 不受影响
    assert p1 in _combat(game.world, snake).enemy_ids
    cs2 = game.world.get(p2, CombatState)
    assert cs2 is None or not cs2.is_fighting


def test_idempotent_no_double_kill(monkeypatch: Any) -> None:
    """重复调 init 不重复 append enemy_ids（initiate_combat 去重）。"""
    game, snake, player = _game()
    assert player is not None
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_kar",
        lambda _w, _e: 10,
    )
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.snake_c_init.query_per",
        lambda _w, _e: 15,
    )
    monkeypatch.setattr("random.randint", lambda a, b: 0)
    snake_c_init(game, snake)
    snake_c_init(game, snake)
    # enemy_ids 去重，player 只出现一次
    assert _combat(game.world, snake).enemy_ids.count(player) == 1
