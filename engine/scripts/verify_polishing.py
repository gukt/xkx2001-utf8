#!/usr/bin/env python3
"""Polishing（打磨抛光）13 项 S5 矩阵：给人看的一页转录。

正式门禁仍以各票单测（``test_navigation`` / ``test_hotel`` / ``test_local_nature``
等）为准；本脚本侧重全局观察，覆盖票 ``01``–``13`` 每项至少一条端到端步骤。

用法（仓库根）::

    just verify-polishing

或::

    cd engine && uv run python scripts/verify_polishing.py

不读存档、不写存档；官方轨场景每次 fresh load；迷你场景写 tempfile。
"""

from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

import yaml

from verify_harness import (
    Expect,
    ScenarioResult,
    StepResult,
    assert_step,
    check,
    main_from,
    move_to,
    run_lines,
)

from mud_engine.ai import spawn_scan
from mud_engine.components import (
    Exits,
    NpcSpawnMeta,
    Position,
    RoomDetails,
    RoomHookBinding,
    Vitals,
)
from mud_engine.entity_gate import EntityGateContext
from mud_engine.nature import Weather, attach_nature
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_mvp_scene, load_xingxiu_mechanics
from mud_engine.world import EntityId, World

_REPO_ROOT = Path(__file__).resolve().parents[2]


class _ScriptedChoiceRng(random.Random):
    """确定性 ``choice``：按序返回预设值（与 ``test_spawner`` 同形）。"""

    def __init__(self, picks: list[object], *, seed: int = 0) -> None:
        super().__init__(seed)
        self._picks = list(picks)

    def choice(self, seq):  # type: ignore[no-untyped-def]
        seq_list = list(seq)
        if self._picks:
            pick = self._picks.pop(0)
            if pick not in seq_list:
                raise AssertionError(f"scripted pick {pick!r} not in {seq_list!r}")
            return pick
        return super().choice(seq_list)


def _force_phase(world: World, name: str) -> None:
    assert world.nature is not None
    world.nature.seek_phase(name)


def _write_tmp_scene(content: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="verify_polishing_"))
    path = tmp / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _write_tmp_tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="verify_polishing_"))
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _go_with_mailbox(world: World, player_id: EntityId, line: str) -> list[str]:
    msgs = execute_line(world, player_id, line)
    return [*msgs, *world.drain_messages(player_id)]


def _npc_in_room(world: World, room: EntityId, template_key: str) -> EntityId | None:
    for entity in world.entities_in_room(room):
        meta = world.get_component(entity, NpcSpawnMeta)
        if meta is not None and meta.template_key == template_key:
            return entity
    return None


def _doc_contains(path: Path, *needles: str) -> tuple[bool, str, list[str]]:
    if not path.is_file():
        return False, f"文件不存在：{path}", []
    text = path.read_text(encoding="utf-8")
    missing = [n for n in needles if n not in text]
    if missing:
        return False, f"缺少片段：{missing!r}", [path.as_posix()]
    return True, "", [path.as_posix()]


# ── 01–07：主要走 MVP ──────────────────────────────────────────────


def _scenario_01_exit_nav() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_guangchang")
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("东(east)",))),
            ("go 东", Expect(contains=("东大街",))),
        ],
    )
    steps.append(
        assert_step(
            "(assert) 抵达东大街",
            world.require_component(player_id, Position).room
            == world.room_ids["yangzhou_dongdajie"],
        )
    )
    return ScenarioResult(name="01 出口导航别名", steps=steps)


def _scenario_02_yaml_shorthand() -> ScenarioResult:
    """票 02：官方范本清理后靠目标房 name 走 ``go 武庙``，出口无冗余方位 alias。"""
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_guangchang")
    plaza = world.room_ids["yangzhou_guangchang"]
    exit_ne = world.require_component(plaza, Exits).by_direction["northeast"]
    steps = [
        assert_step(
            "(assert) northeast→武庙出口无冗余 aliases",
            "武庙" not in exit_ne.aliases and "东北" not in exit_ne.aliases,
            messages=[f"aliases={exit_ne.aliases!r}"],
        )
    ]
    steps.extend(
        run_lines(world, player_id, [("go 武庙", Expect(contains=("武庙",)))])
    )
    steps.append(
        assert_step(
            "(assert) 抵达武庙",
            world.require_component(player_id, Position).room
            == world.room_ids["yangzhou_wumiao"],
        )
    )
    return ScenarioResult(name="02 YAML 简写规范化", steps=steps)


def _scenario_03_room_details() -> ScenarioResult:
    """官方广场已迁 K2：英键 + long 手写 ``名(id)`` + aliases / N1。"""
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_guangchang")
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("石狮(shi_shi)", "旗杆(qi_gan)"))),
            ("look 石狮", Expect(contains=("石狮",))),
            ("look shi_shi", Expect(contains=("石狮",))),
            ("look ss", Expect(contains=("石狮",))),
            ("look 旗杆", Expect(contains=("<c:yellow>旗角</c>",))),
            ("look qi_gan", Expect(contains=("<c:yellow>旗角</c>",))),
        ],
    )
    plaza = world.room_ids["yangzhou_guangchang"]
    details = world.require_component(plaza, RoomDetails)
    steps.append(
        assert_step(
            "(assert) MVP details 键为 shi_shi / qi_gan",
            set(details.entries) == {"shi_shi", "qi_gan"}
            and "石狮" in details.entries["shi_shi"].aliases
            and "旗杆" in details.entries["qi_gan"].aliases,
            messages=[repr(sorted(details.entries))],
        )
    )
    return ScenarioResult(name="03 房间风景 details 升级", steps=steps)


def _scenario_04_block_deny_message() -> ScenarioResult:
    data = {
        "rooms": {
            "street": {
                "name": "街上",
                "long": "街上。",
                "exits": {"north": "yard"},
            },
            "yard": {
                "name": "前院",
                "long": "前院。",
                "exits": {"south": "street", "west": "garden"},
                "block_exits": {
                    "west": {
                        "npc": "guard_npc",
                        "deny_message": "门卫冷冷道：闲人止步。",
                    }
                },
                "objects": {"guard_npc": 1},
            },
            "garden": {
                "name": "小园",
                "long": "小园。",
                "exits": {"east": "yard"},
            },
        },
        "npcs": {"guard_npc": {"name": "门卫"}},
        "player": {"name": "你", "start_room": "street"},
    }
    path = _write_tmp_scene(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    )
    world, player_id = load_scene(path)
    steps = run_lines(
        world,
        player_id,
        [
            ("go north", Expect(contains=("前院",))),
            ("go west", Expect(contains=("门卫冷冷道：闲人止步。",))),
        ],
    )
    steps.append(
        assert_step(
            "(assert) 仍在前院",
            world.require_component(player_id, Position).room == world.room_ids["yard"],
        )
    )
    return ScenarioResult(name="04 block_exits 拒走文案", steps=steps)


def _scenario_05_walking_stamina() -> ScenarioResult:
    """目标房 ``wild_edge.cost=8`` → 步行扣 16；恰好放行、不足拒走。"""
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "road_yz_east")
    road = world.room_ids["road_yz_east"]
    vitals = world.require_component(player_id, Vitals)
    vitals.jingli_current = 15
    refused = execute_line(world, player_id, "go east")
    ok, detail = check(refused, Expect(contains=("精力不足",)))
    steps = [
        StepResult(line="go east (精力不足)", messages=refused, ok=ok, detail=detail),
        assert_step(
            "(assert) 不足未移动",
            world.require_component(player_id, Position).room == road,
        ),
    ]
    vitals.jingli_current = 16
    ok_go = execute_line(world, player_id, "go east")
    ok2, detail2 = check(ok_go, Expect(contains=("陡坡",)))
    steps.append(StepResult(line="go east (恰好 16)", messages=ok_go, ok=ok2, detail=detail2))
    after = world.require_component(player_id, Vitals).jingli_current
    steps.append(
        assert_step(
            "(assert) 抵达陡坡且精力扣至 0",
            world.require_component(player_id, Position).room
            == world.room_ids["wild_edge"]
            and after == 0,
            messages=[f"jingli -> {after}"],
        )
    )
    return ScenarioResult(name="05 步行地形精力", steps=steps)


def _scenario_06_hotel() -> ScenarioResult:
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_kedian")
    steps = run_lines(
        world,
        player_id,
        [
            ("sleep", Expect(contains=("房钱",))),
            ("pay 小二", Expect(contains=("房钱",))),
            ("sleep", Expect(contains=("睡了一觉",))),
            ("go west", Expect(contains=("北大街",))),
        ],
    )
    move_to(world, player_id, "yangzhou_kedian")
    again = execute_line(world, player_id, "sleep")
    ok, detail = check(again, Expect(contains=("房钱",)))
    steps.append(
        StepResult(line="sleep (离店后须再付)", messages=again, ok=ok, detail=detail)
    )
    return ScenarioResult(name="06 客店三件套", steps=steps)


def _scenario_07_condition_dsl() -> ScenarioResult:
    doc = _REPO_ROOT / "docs" / "condition-dsl.md"
    ok_doc, detail_doc, msgs = _doc_contains(
        doc, "entry_guard", "day_shop", "is_day", "luohan_quan", "现在不支持"
    )
    steps = [
        assert_step("(assert) docs/condition-dsl.md 锚点", ok_doc, messages=msgs, detail=detail_doc)
    ]
    world, player_id = load_mvp_scene()
    move_to(world, player_id, "yangzhou_xidajie")
    _force_phase(world, "night")
    night = execute_line(world, player_id, "go north")
    ok, detail = check(night, Expect(contains=("晚上",)))
    steps.append(StepResult(line="(night) go north → day_shop", messages=night, ok=ok, detail=detail))
    return ScenarioResult(name="07 条件 DSL 文档", steps=steps)


# ── 08–13：tmp / xingxiu / ADR ─────────────────────────────────────


def _scenario_08_liquid() -> ScenarioResult:
    scene = """rooms:
  riverside:
    name: 河边
    long: 河水清澈。
    resource:
      water: true
    exits: {}
    objects:
      waterskin: 1
      ration: 1
items:
  waterskin:
    name: 水袋
    liquid_container: true
  ration:
    name: 干粮
    consumable:
      uses: 2
player:
  name: 你
  start_room: riverside
  vitals:
    qi: 40
    qi_max: 100
    neili: 10
    neili_max: 50
    jingli: 10
    jingli_max: 80
"""
    world, player_id = load_scene(_write_tmp_scene(scene))
    steps = run_lines(
        world,
        player_id,
        [
            ("get 水袋", Expect(contains=("拿起",))),
            ("fill 水袋", Expect(contains=("灌满",))),
            ("drink 水袋", Expect(contains=("喝了",))),
            ("get 干粮", Expect(contains=("拿起",))),
            ("eat 干粮", Expect(contains=("吃了",))),
        ],
    )
    return ScenarioResult(name="08 液体 fill/drink/eat", steps=steps)


def _scenario_09_random_objects() -> ScenarioResult:
    """补刷期 objects ``random_of``；与出口加载期 ``random_of`` 正交（不共用求值路径）。"""
    scene = """rooms:
  forest:
    name: 落日林
    exits:
      south:
        to: camp
    objects:
      wildlife:
        random_of:
        - crow
        - rabbit
        - snake
        count: 1
  camp:
    name: 营地
    exits:
      north:
        to: forest
      east:
        random_of:
        - lake_a
        - lake_b
  lake_a:
    name: 湖畔甲
    exits:
      west:
        to: camp
  lake_b:
    name: 湖畔乙
    exits:
      west:
        to: camp
npcs:
  crow:
    name: 乌鸦
    respawn: true
  rabbit:
    name: 野兔
    respawn: true
  snake:
    name: 毒蛇
    respawn: true
player:
  name: 你
  start_room: camp
"""
    world, _ = load_scene(
        _write_tmp_scene(scene),
        rng=_ScriptedChoiceRng(["lake_a", "crow"]),
    )
    camp = world.room_ids["camp"]
    east_target = world.require_component(camp, Exits).by_direction["east"].target
    bp = world.random_object_slots[("forest", "wildlife")]
    first = bp.slots[0]
    assert first is not None
    steps = [
        assert_step(
            "(assert) 出口 random_of 落地为 lake_a",
            east_target == world.room_ids["lake_a"],
        ),
        assert_step(
            "(assert) objects 池首刷 crow",
            world.require_component(first, NpcSpawnMeta).template_key == "crow",
        ),
    ]
    world.destroy_entity(first)
    spawn_scan(world, rng=_ScriptedChoiceRng(["rabbit"]))
    bp = world.random_object_slots[("forest", "wildlife")]
    redrawn = bp.slots[0]
    assert redrawn is not None
    steps.append(
        assert_step(
            "(assert) 补刷重抽 rabbit（独立于出口）",
            world.require_component(redrawn, NpcSpawnMeta).template_key == "rabbit",
        )
    )
    steps.append(
        assert_step(
            "(assert) 出口仍指向 lake_a",
            world.require_component(camp, Exits).by_direction["east"].target
            == world.room_ids["lake_a"],
        )
    )
    return ScenarioResult(name="09 随机 objects 池", steps=steps)


def _scenario_10_bandit_params() -> ScenarioResult:
    world, player_id = load_xingxiu_mechanics()
    ambush = world.room_ids["ambush_trail"]
    binding = world.require_component(ambush, RoomHookBinding)
    steps = [
        assert_step(
            "(assert) hooks.params.min_item_value=100",
            binding.params.get("min_item_value") == 100,
            messages=[repr(binding.params)],
        )
    ]
    get_msgs = execute_line(world, player_id, "get 铁剑")
    enter = _go_with_mailbox(world, player_id, "go path")
    ok, detail = check(enter, Expect(any_of=("劫匪", "拦")))
    steps.append(StepResult(line="get 铁剑", messages=get_msgs, ok=True, detail="ok"))
    steps.append(StepResult(line="go path", messages=enter, ok=ok, detail=detail))
    steps.append(
        assert_step(
            "(assert) 劫匪已生成",
            _npc_in_room(world, ambush, "road_bandit") is not None,
        )
    )
    blocked = execute_line(world, player_id, "go north")
    ok_b, detail_b = check(blocked, Expect(contains=("挡",)))
    steps.append(StepResult(line="go north (被挡)", messages=blocked, ok=ok_b, detail=detail_b))
    return ScenarioResult(name="10 刷怪条件 hooks params", steps=steps)


def _scenario_11_includes() -> ScenarioResult:
    root = _write_tmp_tree(
        {
            "scene.yaml": """includes:
  - templates/shared.yaml
rooms:
  yard:
    name: 院子
    long: 院子
    objects:
      shared_stone: 1
      shared_guard: 1
player:
  name: 你
  start_room: yard
""",
            "templates/shared.yaml": """items:
  shared_stone:
    name: 共享石
    short: 一块共享石
npcs:
  shared_guard:
    name: 共享守卫
    short: 守卫
""",
        }
    )
    world, player_id = load_scene(root / "scene.yaml")
    steps = run_lines(
        world,
        player_id,
        [("look", Expect(contains=("共享石",)))],
    )
    steps.append(
        assert_step(
            "(assert) include 模板已合并",
            "shared_stone" in world.item_templates
            and "shared_guard" in world.spawners,
        )
    )
    steps.append(
        assert_step(
            "(assert) includes 不透传 extension_data",
            "includes" not in world.extension_data,
        )
    )
    return ScenarioResult(name="11 多文件 includes", steps=steps)


def _scenario_12_local_weather_adr() -> ScenarioResult:
    adr = _REPO_ROOT / "docs" / "adr" / "0013-local-nature-room-sticker.md"
    ok, detail, msgs = _doc_contains(
        adr, "Status: accepted", "LocalNature", "World.nature", "ADR-0009"
    )
    steps = [
        assert_step("(assert) ADR-0013 accepted", ok, messages=msgs, detail=detail)
    ]
    return ScenarioResult(name="12 局部天气 ADR", steps=steps)


def _scenario_13_local_nature() -> ScenarioResult:
    scene = """rooms:
  plain:
    name: 平原
    short: 平原
    long: 开阔的平原。
    outdoors: true
    exits:
      north: peak
  peak:
    name: 山顶
    short: 山顶
    long: 终年云雾缭绕。
    outdoors: true
    local_nature:
      weather: rain
      phase: night
    exits:
      south: plain
player:
  name: 你
  start_room: plain
"""
    world, player_id = load_scene(_write_tmp_scene(scene))
    attach_nature(world, weather=Weather.CLEAR).seek_phase("day")
    steps = run_lines(
        world,
        player_id,
        [
            ("look", Expect(contains=("日正当空",), absent=("夜雨潇潇",))),
            ("go north", Expect(contains=("山顶",))),
            ("look", Expect(contains=("夜雨潇潇",), absent=("日正当空",))),
        ],
    )
    gate = EntityGateContext(world, player_id)
    steps.append(
        assert_step(
            "(assert) 贴纸房谓词 is_raining/is_night",
            gate.is_raining is True and gate.is_night is True and gate.phase == "night",
            messages=[
                f"phase={gate.phase} raining={gate.is_raining} night={gate.is_night}"
            ],
        )
    )
    return ScenarioResult(name="13 局部天气 LocalNature", steps=steps)


def all_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_01_exit_nav(),
        _scenario_02_yaml_shorthand(),
        _scenario_03_room_details(),
        _scenario_04_block_deny_message(),
        _scenario_05_walking_stamina(),
        _scenario_06_hotel(),
        _scenario_07_condition_dsl(),
        _scenario_08_liquid(),
        _scenario_09_random_objects(),
        _scenario_10_bandit_params(),
        _scenario_11_includes(),
        _scenario_12_local_weather_adr(),
        _scenario_13_local_nature(),
    ]


def main() -> int:
    return main_from(all_scenarios)


if __name__ == "__main__":
    sys.exit(main())
