"""wield/unwield 命令测试（ADR-0063）。

覆盖 wield 命令批：weapon_prop 注入 apply/<key> + flag 槽位判定 + skill_type 桥接
CombatState.attack_skill + is_busy/perform 门控 + wield all + unwield 反向扣减。
用 xueshan_micro scene（item_registry 含 149 武器，ADR-0062 接线）。
"""

from __future__ import annotations

from xkx.cli import load_game
from xkx.runtime import equipment
from xkx.runtime.action_context import new_context
from xkx.runtime.commands import COMMAND_REGISTRY, unwield, wield
from xkx.runtime.components import CombatState, Equipment, Inventory, Skills
from xkx.runtime.conditions import apply_condition


def _add_inv(game, pid: int, *item_ids: str) -> None:
    """把物品 id 加入玩家 inventory。"""
    inv = game.world.get(pid, Inventory)
    if inv is None:
        inv = Inventory()
        game.world.add(pid, inv)
    for iid in item_ids:
        inv.items.add(iid)


def _inject_spec(game, item_id: str, **fields) -> None:
    """注入测试用武器 spec 到 item_registry（测试 TWO_HANDED/SECONDARY/未知 prop）。"""
    spec = {
        "id": item_id,
        "name": fields.get("name", item_id),
        "aliases": [],
        "weapon_prop": fields.get("weapon_prop", {"damage": 10}),
        "flag": fields.get("flag", 4),
        "skill_type": fields.get("skill_type", "sword"),
        "weight": fields.get("weight", 1000),
        "value": fields.get("value", 100),
    }
    game.item_registry[item_id] = spec


# ──────────────────────── wield 成功 + prop 注入 + skill_type 桥接 ────────────────────────


def test_wield_success_injects_props_and_bridges_skill_type() -> None:
    """wield 成功：weapon_prop 注入 apply_damage + skill_type 桥接 attack_skill。"""
    game, pid = load_game("xueshan_micro")
    assert "changjian" in game.item_registry
    _add_inv(game, pid, "changjian")
    spec = game.item_registry["changjian"]
    msgs = wield(game, pid, "changjian")
    assert any("你装备" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert eq.weapon == "changjian"
    skills = game.world.get(pid, Skills)
    assert skills.apply_damage == spec["weapon_prop"]["damage"]
    combat = game.world.get(pid, CombatState)
    assert combat.attack_skill == spec["skill_type"]
    assert combat.weapon_label == spec["name"]


# ──────────────────────── wield 槽位冲突 ────────────────────────


def test_wield_slot_conflict_main_hand_occupied() -> None:
    """主手已占，再 wield 另一主手武器 -> 失败 + weapon 不变。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian", "gangdao")
    wield(game, pid, "changjian")
    msgs = wield(game, pid, "gangdao")
    assert any("放下" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert eq.weapon == "changjian"


def test_wield_idempotent_already_equipped() -> None:
    """已装备再 wield 同一武器 -> "你已经装备著了。"。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    wield(game, pid, "changjian")
    msgs = wield(game, pid, "changjian")
    assert msgs == ["你已经装备著了。"]


def test_wield_not_held() -> None:
    """wield 不在 inventory 的武器 -> "你身上没有"。"""
    game, pid = load_game("xueshan_micro")
    msgs = wield(game, pid, "changjian")
    assert any("没有" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert eq.weapon is None


def test_wield_non_weapon_item_rejected() -> None:
    """wield 无 weapon_prop 的非武器物品 -> "只能装备可当作武器的东西。"。"""
    game, pid = load_game("xueshan_micro")
    _inject_spec(game, "test-no-prop", name="测试非武器", weapon_prop={}, flag=0)
    _add_inv(game, pid, "test-no-prop")
    msgs = wield(game, pid, "test-no-prop")
    assert any("只能装备" in m for m in msgs)


# ──────────────────────── wield is_busy 门控 ────────────────────────


def test_wield_busy_rejected() -> None:
    """is_busy（exercise condition）期间 wield -> "你正忙着呢。"。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    apply_condition(game.world, pid, "exercise", 10)
    msgs = wield(game, pid, "changjian")
    assert msgs == ["你正忙着呢。"]
    assert game.world.get(pid, Equipment).weapon is None


# ──────────────────────── wield all（主 + 副）────────────────────────


def test_wield_all_equips_main_and_secondary() -> None:
    """wield all：遍历 inventory 装备主手 + 副手（SECONDARY）+ "Ok。"。"""
    game, pid = load_game("xueshan_micro")
    _inject_spec(
        game, "test-secondary", name="测试副剑", weapon_prop={"damage": 8}, flag=2
    )
    _add_inv(game, pid, "changjian", "test-secondary")
    msgs = wield(game, pid, "all")
    assert "Ok。" in msgs
    eq = game.world.get(pid, Equipment)
    assert eq.weapon == "changjian"
    assert eq.secondary_weapon == "test-secondary"


def test_wield_all_no_weapons() -> None:
    """wield all 无可装备武器 -> "你没有可装备的武器。"。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    wield(game, pid, "changjian")  # 先装备
    msgs = wield(game, pid, "all")  # 全部已装备
    assert msgs == ["你没有可装备的武器。"]


# ──────────────────────── wield TWO_HANDED ────────────────────────


def test_wield_two_handed_needs_both_hands_free() -> None:
    """TWO_HANDED 武器需空双手，主手占 -> "空出双手"。"""
    game, pid = load_game("xueshan_micro")
    _inject_spec(
        game, "test-twohanded", name="测试双手剑", weapon_prop={"damage": 30}, flag=1
    )
    _add_inv(game, pid, "changjian", "test-twohanded")
    wield(game, pid, "changjian")  # 占主手
    msgs = wield(game, pid, "test-twohanded")
    assert any("空出双手" in m for m in msgs)
    assert game.world.get(pid, Equipment).weapon == "changjian"


def test_wield_two_handed_into_free_hands() -> None:
    """TWO_HANDED 武器双手空时装备成功占主手。"""
    game, pid = load_game("xueshan_micro")
    _inject_spec(
        game, "test-twohanded", name="测试双手剑", weapon_prop={"damage": 30}, flag=1
    )
    _add_inv(game, pid, "test-twohanded")
    msgs = wield(game, pid, "test-twohanded")
    assert any("你装备" in m for m in msgs)
    assert game.world.get(pid, Equipment).weapon == "test-twohanded"


# ──────────────────────── weapon_prop 未知 key 忽略 ────────────────────────


def test_wield_unknown_prop_key_ignored() -> None:
    """weapon_prop 含未知 key（武侠特有）-> 已知 key 注入，未知忽略。"""
    game, pid = load_game("xueshan_micro")
    _inject_spec(
        game,
        "test-unknown-prop",
        name="测试未知属性",
        weapon_prop={"damage": 12, "wuxia_special": 99},
    )
    _add_inv(game, pid, "test-unknown-prop")
    wield(game, pid, "test-unknown-prop")
    skills = game.world.get(pid, Skills)
    assert skills.apply_damage == 12  # damage 注入


# ──────────────────────── unwield 反向扣减 ────────────────────────


def test_unwield_success_reverses_props() -> None:
    """unwield 成功：卸下 + weapon=None + apply_damage 反向扣减归 0。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    wield(game, pid, "changjian")
    assert game.world.get(pid, Skills).apply_damage > 0
    msgs = unwield(game, pid, "changjian")
    assert any("放下" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert eq.weapon is None
    assert game.world.get(pid, Skills).apply_damage == 0


def test_unwield_not_equipped() -> None:
    """unwield 未装备武器 -> "你并没有装备这样东西作为武器。"。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    msgs = unwield(game, pid, "changjian")
    assert msgs == ["你并没有装备这样东西作为武器。"]


def test_unwield_armor_not_treated_as_weapon() -> None:
    """unwield 已穿护甲（非武器槽）-> "你并没有装备...作为武器。"（unwield 只管武器槽）。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "test-armor")
    equipment.wear(game.world, pid, "test-armor", props={}, armor_type="cloth")
    msgs = unwield(game, pid, "test-armor")
    assert msgs == ["你并没有装备这样东西作为武器。"]


# ──────────────────────── 8 段管线 adapter 路径 ────────────────────────


def test_wield_via_command_registry_adapter() -> None:
    """wield 经 COMMAND_REGISTRY adapter（8 段管线路径）可执行。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    ctx = new_context(verb="wield", raw_args="changjian", actor=pid)
    adapter = COMMAND_REGISTRY["wield"]
    msgs = adapter(game, ctx)
    assert any("你装备" in m for m in msgs)
    assert game.world.get(pid, Equipment).weapon == "changjian"


def test_unwield_via_command_registry_adapter() -> None:
    """unwield 经 COMMAND_REGISTRY adapter 可执行。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    wield(game, pid, "changjian")
    ctx = new_context(verb="unwield", raw_args="changjian", actor=pid)
    adapter = COMMAND_REGISTRY["unwield"]
    msgs = adapter(game, ctx)
    assert any("放下" in m for m in msgs)
    assert game.world.get(pid, Equipment).weapon is None
