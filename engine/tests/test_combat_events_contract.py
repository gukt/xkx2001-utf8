"""M3-hardening-07：战斗事件点最小契约测。

Seam：``EventBus`` 上 ``on_before_combat_round`` / ``on_combat_round`` /
``on_combat_end`` + ``TickLoop.advance`` / ``execute_line``（attack/flee）。
模式参照 ``test_domain_events.py`` / ``test_command_hooks.py``（否决 / 分发 /
上下文字段）。
"""

from __future__ import annotations

import random
from pathlib import Path

from openmud.combat_system import (
    ON_BEFORE_COMBAT_ROUND,
    ON_COMBAT_END,
    ON_COMBAT_ROUND,
    CombatEndContext,
    CombatRoundContext,
    attach_combat_system,
    resolve_one_strike,
)
from openmud.components import Engaged, Identity, Vitals
from openmud.events import Deny
from openmud.parsing import execute_line
from openmud.scene_loader import load_scene
from openmud.tick import TickLoop


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      bandit: 1
skills:
  basic_fist:
    type: martial
    level_req: 0
    moves:
    - name: 直拳
      force: 20
      dodge: 0
      damage_type: blunt
      damage: 10
npcs:
  bandit:
    name: 山贼
    vitals:
      qi_current: 40
      qi_max: 40
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    attributes:
      str: 10
      con: 10
      dex: 0
      int: 5
    skills:
      basic_fist:
        level: 1
        exp: 0
player:
  name: 你
  start_room: yard
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
  attributes:
    str: 20
    con: 10
    dex: 0
    int: 10
  skills:
    basic_fist:
      level: 1
      exp: 0
"""


def _bandit_id(world, player_id):
    for entity in world.entities_with(Identity):
        if entity == player_id:
            continue
        if world.require_component(entity, Identity).name == "山贼":
            return entity
    raise AssertionError("山贼未找到")


def _engage(tmp_path: Path, *, flee_success_chance: float = 0.5):
    world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
    attach_combat_system(world, rng=random.Random(42), flee_success_chance=flee_success_chance)
    execute_line(world, player_id, "attack 山贼")
    bandit = _bandit_id(world, player_id)
    return world, player_id, bandit


class TestCombatEventsContract:
    class WhenBeforeCombatRoundIsVetoed:
        def test_round_is_skipped_and_qi_unchanged(self, tmp_path: Path) -> None:
            world, player_id, bandit = _engage(tmp_path)
            before_p = world.require_component(player_id, Vitals).qi_current
            before_b = world.require_component(bandit, Vitals).qi_current
            rounds: list[CombatRoundContext] = []

            world.events.register(
                ON_BEFORE_COMBAT_ROUND,
                lambda ctx: Deny(message="本回合暂停。"),
            )
            world.events.register(ON_COMBAT_ROUND, lambda ctx: rounds.append(ctx))

            TickLoop(lambda: None, world=world).advance()

            assert world.require_component(player_id, Vitals).qi_current == before_p
            assert world.require_component(bandit, Vitals).qi_current == before_b
            assert rounds == []
            assert any("本回合暂停" in m for m in world.pending_messages)
            assert world.has_component(player_id, Engaged)

        def test_next_tick_settles_after_veto_lifted(self, tmp_path: Path) -> None:
            world, player_id, bandit = _engage(tmp_path)
            before_b = world.require_component(bandit, Vitals).qi_current
            veto_on = True
            rounds: list[CombatRoundContext] = []

            def maybe_deny(ctx: CombatRoundContext):
                nonlocal veto_on
                if veto_on:
                    return Deny(message="本回合暂停。")
                return None

            world.events.register(ON_BEFORE_COMBAT_ROUND, maybe_deny)
            world.events.register(ON_COMBAT_ROUND, lambda ctx: rounds.append(ctx))

            TickLoop(lambda: None, world=world).advance()
            assert world.require_component(bandit, Vitals).qi_current == before_b
            assert rounds == []

            veto_on = False
            TickLoop(lambda: None, world=world).advance()
            assert world.require_component(bandit, Vitals).qi_current < before_b
            assert len(rounds) >= 1

    class WhenCombatRoundSettles:
        def test_on_combat_round_fires_with_matching_context(self, tmp_path: Path) -> None:
            world, player_id, bandit = _engage(tmp_path)
            seen: list[CombatRoundContext] = []

            world.events.register(ON_COMBAT_ROUND, lambda ctx: seen.append(ctx))
            TickLoop(lambda: None, world=world).advance()

            # 每对双方各出手一次 → 两次 on_combat_round。
            assert len(seen) == 2
            pairs = {(c.attacker_id, c.defender_id) for c in seen}
            assert pairs == {(player_id, bandit), (bandit, player_id)}
            for ctx in seen:
                assert ctx.world is world
                assert ctx.result is not None

        def test_round_result_damage_matches_qi_delta(self, tmp_path: Path) -> None:
            world, player_id, bandit = _engage(tmp_path)
            seen: list[CombatRoundContext] = []
            world.events.register(ON_COMBAT_ROUND, lambda ctx: seen.append(ctx))

            before = world.require_component(bandit, Vitals).qi_current
            result = resolve_one_strike(
                world, player_id, bandit, rng=world.combat.rng
            )
            after = world.require_component(bandit, Vitals).qi_current

            assert result is not None
            assert len(seen) == 1
            assert seen[0].attacker_id == player_id
            assert seen[0].defender_id == bandit
            assert seen[0].result is result
            assert before - after == result.damage

    class WhenEngagementEnds:
        def test_flee_dispatches_on_combat_end_once(self, tmp_path: Path) -> None:
            world, player_id, bandit = _engage(tmp_path, flee_success_chance=1.0)
            ends: list[CombatEndContext] = []

            world.events.register(ON_COMBAT_END, lambda ctx: ends.append(ctx))
            lines = execute_line(world, player_id, "flee")

            assert any("脱离" in line or "逃" in line for line in lines)
            assert len(ends) == 1
            assert {ends[0].entity_a, ends[0].entity_b} == {player_id, bandit}
            assert ends[0].reason == "flee"
            assert ends[0].world is world
            assert not world.has_component(player_id, Engaged)
            assert not world.has_component(bandit, Engaged)

        def test_npc_death_via_tick_dispatches_on_combat_end_once(
            self, tmp_path: Path
        ) -> None:
            world, player_id, bandit = _engage(tmp_path)
            ends: list[CombatEndContext] = []
            world.events.register(ON_COMBAT_END, lambda ctx: ends.append(ctx))

            # 低气血 + tick 自动交战：经 resolve_one_strike → apply → 死亡流程清交战。
            world.require_component(bandit, Vitals).qi_current = 1
            TickLoop(lambda: None, world=world).advance()

            assert len(ends) == 1
            assert {ends[0].entity_a, ends[0].entity_b} == {player_id, bandit}
            assert ends[0].reason == "death"
            assert not world.has_component(player_id, Engaged)
            assert not world.has_component(bandit, Engaged)
