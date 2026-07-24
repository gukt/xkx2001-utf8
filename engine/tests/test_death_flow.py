"""M2-17 / M2-18：玩家死亡流程 + NPC 击杀掉落 / 重生。"""

from __future__ import annotations

import json
import random
from pathlib import Path

from openmud.components import (
    Container,
    Currency,
    Engaged,
    Identity,
    NpcSpawnMeta,
    Position,
    SkillLevels,
    Unconscious,
    Vitals,
)
from openmud.death_flow import ON_BEFORE_DEATH, handle_vitals_depleted
from openmud.events import Deny
from openmud.parsing import execute_line
from openmud.save import restore_world, save_world
from openmud.scene_loader import load_scene
from openmud.tick import TickLoop


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_BASE = """rooms:
  yard:
    name: 院子
    exits:
      north: village
    objects:
      herb: 1
      bandit: 1
  village:
    name: 华山村
    no_death: true
    exits:
      south: yard
death_policy:
  penalty_ratio: 0.5
  revive_room: village
  drop_currency: true
  drop_items: true
items:
  herb:
    name: 解毒丹
    short: 解毒丹
skills:
  basic_fist:
    type: martial
    level_req: 0
    moves:
    - name: 直拳
      force: 50
      dodge: 0
      damage_type: blunt
      damage: 50
npcs:
  bandit:
    name: 山贼
    respawn: true
    loot:
      currency:
      - 10
      - 10
      items:
      - herb
      kill_exp: 7
    vitals:
      qi_current: 30
      qi_max: 30
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    attributes:
      str: 5
      con: 5
      dex: 0
      int: 5
    skills:
      basic_fist:
        level: 1
        exp: 0
player:
  name: 你
  start_room: yard
  currency: 100
  vitals:
    qi: 20
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
  attributes:
    str: 30
    con: 10
    dex: 0
    int: 10
  skills:
    basic_fist:
      level: 1
      exp: 40
"""


def _npc_named(world, name: str):
    for entity in world.entities_with(Identity, NpcSpawnMeta):
        if world.require_component(entity, Identity).name == name:
            return entity
    return None


class TestPlayerDeathFlow:
    def test_first_deplete_unconscious_second_kills_and_revives(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        # 把地上解毒丹放进背包，供死亡掉落断言
        yard = world.room_ids["yard"]
        herb = next(
            i
            for i in world.require_component(yard, Container).items
            if world.require_component(i, Identity).name == "解毒丹"
        )
        from openmud.transfer import transfer

        transfer(world, herb, yard, player_id, player_id=player_id)
        assert herb in world.require_component(player_id, Container).items

        vitals = world.require_component(player_id, Vitals)
        vitals.qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.has_component(player_id, Unconscious)
        assert world.require_component(player_id, Position).room == world.room_ids["yard"]

        # 昏迷中再次归零 → 死亡完整流程
        vitals.qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert not world.has_component(player_id, Unconscious)
        assert world.require_component(player_id, Position).room == world.room_ids["village"]
        assert world.require_component(player_id, Vitals).qi_current == 100
        assert world.require_component(player_id, Currency).amount == 50  # 100 * 0.5
        exp = world.require_component(player_id, SkillLevels).levels["basic_fist"].exp
        assert exp == 20  # 40 * 0.5
        # 物品留在死亡房间地面
        assert herb in world.require_component(yard, Container).items
        assert herb not in world.require_component(player_id, Container).items

    def test_npc_kill_without_loot_still_grants_default_exp(self, tmp_path: Path) -> None:
        scene = _BASE.replace(
            """    loot:
      currency:
      - 10
      - 10
      items:
      - herb
      kill_exp: 7
""",
            "",
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        bandit = _npc_named(world, "山贼")
        assert bandit is not None
        before = world.require_component(player_id, SkillLevels).levels["basic_fist"].exp
        world.require_component(bandit, Vitals).qi_current = 0
        handle_vitals_depleted(world, bandit, killer_id=player_id, rng=random.Random(0))
        assert (
            world.require_component(player_id, SkillLevels).levels["basic_fist"].exp
            == before + 10
        )
    def test_no_death_zone_stays_unconscious(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        execute_line(world, player_id, "go north")
        world.require_component(player_id, Vitals).qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.has_component(player_id, Unconscious)
        world.require_component(player_id, Vitals).qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.has_component(player_id, Unconscious)
        assert world.require_component(player_id, Currency).amount == 100

    def test_before_death_deny_skips_flow(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        world.require_component(player_id, Vitals).qi_current = 0
        handle_vitals_depleted(world, player_id)  # → unconscious
        world.events.register(ON_BEFORE_DEATH, lambda ctx: Deny(message="免死符生效。"))
        world.require_component(player_id, Vitals).qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.has_component(player_id, Unconscious)
        assert world.require_component(player_id, Currency).amount == 100
        assert world.require_component(player_id, Position).room == world.room_ids["yard"]

    def test_unconscious_blocks_attack(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        world.add_component(player_id, Unconscious())
        lines = execute_line(world, player_id, "attack 山贼")
        assert any("昏迷" in line for line in lines)


class TestNpcDeathAndLoot:
    def test_kill_npc_grants_loot_and_exp(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        bandit = _npc_named(world, "山贼")
        assert bandit is not None
        world.require_component(bandit, Vitals).qi_current = 0
        before_money = world.require_component(player_id, Currency).amount
        before_exp = world.require_component(player_id, SkillLevels).levels["basic_fist"].exp
        handle_vitals_depleted(world, bandit, killer_id=player_id, rng=random.Random(0))
        assert _npc_named(world, "山贼") is None
        assert world.require_component(player_id, Currency).amount == before_money + 10
        assert (
            world.require_component(player_id, SkillLevels).levels["basic_fist"].exp
            == before_exp + 7
        )
        yard = world.room_ids["yard"]
        floor_names = [
            world.require_component(i, Identity).name
            for i in world.require_component(yard, Container).items
        ]
        assert "解毒丹" in floor_names

    def test_respawn_after_scan(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        from openmud.ai import spawn_scan

        bandit = _npc_named(world, "山贼")
        assert bandit is not None
        world.require_component(bandit, Vitals).qi_current = 0
        handle_vitals_depleted(world, bandit, killer_id=player_id, rng=random.Random(0))
        assert _npc_named(world, "山贼") is None
        spawn_scan(world)
        assert _npc_named(world, "山贼") is not None


class TestUnconsciousTickRecovery:
    """M3-hardening-01：昏迷 tick 自动苏醒（tick 层 seam）。"""

    def test_ticks_decrement_then_wake_with_vitals(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        world.require_component(player_id, Vitals).qi_current = 0
        handle_vitals_depleted(world, player_id)
        unc = world.require_component(player_id, Unconscious)
        assert unc.ticks_remaining == 5  # DeathPolicy 默认

        loop = TickLoop(lambda: None, world=world, interval=100)
        for remaining in (4, 3, 2, 1):
            loop.advance()
            assert world.has_component(player_id, Unconscious)
            assert (
                world.require_component(player_id, Unconscious).ticks_remaining == remaining
            )

        loop.advance()  # 归零 → 苏醒
        assert not world.has_component(player_id, Unconscious)
        assert world.require_component(player_id, Vitals).qi_current == 20  # max(1, 100*0.2)
        assert not world.has_component(player_id, Engaged)
        assert any("悠悠转醒" in msg for msg in world.pending_messages)

    def test_scene_can_override_recovery_policy(self, tmp_path: Path) -> None:
        scene = _BASE.replace(
            """death_policy:
  penalty_ratio: 0.5
  revive_room: village
  drop_currency: true
  drop_items: true
""",
            """death_policy:
  penalty_ratio: 0.5
  revive_room: village
  drop_currency: true
  drop_items: true
  unconscious_recovery_ticks: 2
  recovery_vitals_ratio: 0.5
""",
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        world.require_component(player_id, Vitals).qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.require_component(player_id, Unconscious).ticks_remaining == 2

        loop = TickLoop(lambda: None, world=world, interval=100)
        loop.advance()
        assert world.has_component(player_id, Unconscious)
        loop.advance()
        assert not world.has_component(player_id, Unconscious)
        assert world.require_component(player_id, Vitals).qi_current == 50  # 100 * 0.5

    def test_legacy_save_missing_ticks_falls_back_to_default(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _BASE))
        world.add_component(player_id, Unconscious(ticks_remaining=3))
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)

        entity_path = (save_dir / "current").resolve() / f"entity_{player_id}.json"
        record = json.loads(entity_path.read_text(encoding="utf-8"))
        record["components"]["Unconscious"] = {}  # 模拟老存档缺字段
        entity_path.write_text(json.dumps(record), encoding="utf-8")

        restored = restore_world(save_dir)
        assert restored is not None
        rworld, rid = restored
        assert rworld.require_component(rid, Unconscious).ticks_remaining == 5
