"""wear/remove 命令测试（ADR-0064）。

覆盖 wear 命令批：armor_prop 注入 apply/<key> + armor_type 槽位判定 +
wear_msg 按 armor_type 分支（穿/戴/绑）+ is_busy/perform 门控 + wear all +
remove 反向扣减 + remove all + remove 只管护甲槽（非武器）。用 xueshan_micro
scene（item_registry 含 145 护甲 + 149 武器，ADR-0064 数据接线）。
"""

from __future__ import annotations

from xkx.cli import load_game
from xkx.runtime.action_context import new_context
from xkx.runtime.commands import COMMAND_REGISTRY, remove, wear, wield
from xkx.runtime.components import Equipment, Inventory, Skills
from xkx.runtime.conditions import apply_condition


def _add_inv(game, pid: int, *item_ids: str) -> None:
    """把物品 id 加入玩家 inventory。"""
    inv = game.world.get(pid, Inventory)
    if inv is None:
        inv = Inventory()
        game.world.add(pid, inv)
    for iid in item_ids:
        inv.items.add(iid)


def _inject_armor_spec(game, item_id: str, **fields) -> None:
    """注入测试用护甲 spec 到 item_registry（测槽位冲突/消息分支/未知 prop）。"""
    spec = {
        "id": item_id,
        "name": fields.get("name", item_id),
        "aliases": [],
        "armor_prop": fields.get("armor_prop", {"armor": 10}),
        "armor_type": fields.get("armor_type", "cloth"),
        "weight": fields.get("weight", 1000),
        "value": fields.get("value", 100),
        "unit": fields.get("unit", "件"),
    }
    game.item_registry[item_id] = spec


# ──────────────────────── wear 成功 + prop 注入 + armor_type 槽位 ────────────────────────


def test_wear_success_injects_armor_prop_and_slot() -> None:
    """wear 成功：armor_prop/armor 注入 apply_armor + armors[armor_type]=item_id。"""
    game, pid = load_game("xueshan_micro")
    assert "cloth" in game.item_registry
    _add_inv(game, pid, "cloth")
    spec = game.item_registry["cloth"]
    msgs = wear(game, pid, "cloth")
    assert any("你穿上" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert eq.armors["cloth"] == "cloth"  # armor_type=cloth 槽位
    skills = game.world.get(pid, Skills)
    assert skills.apply_armor == spec["armor_prop"]["armor"]


def test_wear_injects_dodge_prop_from_setup_side_effect() -> None:
    """护甲 armor_prop/dodge 注入 apply_dodge（tiejia dodge=-6，setup 副作用预计算）。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "tiejia")
    wear(game, pid, "tiejia")
    skills = game.world.get(pid, Skills)
    spec = game.item_registry["tiejia"]
    assert skills.apply_armor == spec["armor_prop"]["armor"]  # 50
    assert skills.apply_dodge == spec["armor_prop"]["dodge"]  # -6（setup 副作用）


# ──────────────────────── wear_msg 按 armor_type 分支 ────────────────────────


def test_wear_msg_cloth_armor_boots_uses_chuan() -> None:
    """cloth/armor/boots/surcoat -> '穿上一{unit}{name}。'。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-cloth", name="测试布衣", armor_type="cloth", unit="件")
    _add_inv(game, pid, "test-cloth")
    assert wear(game, pid, "test-cloth") == ["你穿上一件测试布衣。"]


def test_wear_msg_head_neck_uses_dai() -> None:
    """head/neck/wrists/finger/hands -> '戴上一{unit}{name}。'。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-hat", name="测试帽", armor_type="head", unit="顶")
    _add_inv(game, pid, "test-hat")
    assert wear(game, pid, "test-hat") == ["你戴上一顶测试帽。"]


def test_wear_msg_waist_uses_bang() -> None:
    """waist -> '将一{unit}{name}绑在腰间。'。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-belt", name="测试腰带", armor_type="waist", unit="条")
    _add_inv(game, pid, "test-belt")
    assert wear(game, pid, "test-belt") == ["你将一条测试腰带绑在腰间。"]


# ──────────────────────── wear 槽位冲突 / 幂等 / 前置 ────────────────────────


def test_wear_slot_conflict_same_armor_type() -> None:
    """同 armor_type 已穿再 wear 另一 -> 失败 + 槽位不变。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-cloth1", name="布衣甲", armor_type="cloth")
    _inject_armor_spec(game, "test-cloth2", name="布衣乙", armor_type="cloth")
    _add_inv(game, pid, "test-cloth1", "test-cloth2")
    wear(game, pid, "test-cloth1")
    msgs = wear(game, pid, "test-cloth2")
    assert any("同类型" in m for m in msgs)
    assert game.world.get(pid, Equipment).armors["cloth"] == "test-cloth1"


def test_wear_idempotent_already_equipped() -> None:
    """已装备再 wear 同一护甲 -> '你已经装备著了。'。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    wear(game, pid, "cloth")
    assert wear(game, pid, "cloth") == ["你已经装备著了。"]


def test_wear_not_held() -> None:
    """wear 不在 inventory 的护甲 -> '你身上没有'。"""
    game, pid = load_game("xueshan_micro")
    msgs = wear(game, pid, "cloth")
    assert any("没有" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert not eq.armors


def test_wear_non_armor_rejected() -> None:
    """wear 无 armor_prop/armor 的非护甲物品 -> '只能穿戴可当作护具的东西。'。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-no-armor", name="测试非护甲", armor_prop={})
    _add_inv(game, pid, "test-no-armor")
    msgs = wear(game, pid, "test-no-armor")
    assert any("只能穿戴" in m for m in msgs)


# ──────────────────────── wear is_busy 门控 ────────────────────────


def test_wear_busy_rejected() -> None:
    """is_busy（exercise condition）期间 wear -> '你正忙着呢。'。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    apply_condition(game.world, pid, "exercise", 10)
    assert wear(game, pid, "cloth") == ["你正忙着呢。"]
    assert not game.world.get(pid, Equipment).armors


# ──────────────────────── wear all ────────────────────────


def test_wear_all_equips_multiple_slots() -> None:
    """wear all：遍历 inventory 穿不同 armor_type 槽 + 'Ok。'。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-cloth", name="布衣", armor_type="cloth")
    _inject_armor_spec(game, "test-hat", name="帽", armor_type="head")
    _add_inv(game, pid, "test-cloth", "test-hat")
    msgs = wear(game, pid, "all")
    assert "Ok。" in msgs
    eq = game.world.get(pid, Equipment)
    assert eq.armors["cloth"] == "test-cloth"
    assert eq.armors["head"] == "test-hat"


def test_wear_all_no_armors() -> None:
    """wear all 无可穿戴护甲 -> '你没有可穿戴的护具。'。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    wear(game, pid, "cloth")  # 先穿
    assert wear(game, pid, "all") == ["你没有可穿戴的护具。"]


# ──────────────────────── armor_prop 未知 key 忽略 ────────────────────────


def test_wear_unknown_prop_key_ignored() -> None:
    """armor_prop 含未知 key（武侠特有）-> 已知 key（armor）注入，未知忽略。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(
        game, "test-unknown", name="测试未知", armor_prop={"armor": 8, "wuxia_special": 99}
    )
    _add_inv(game, pid, "test-unknown")
    wear(game, pid, "test-unknown")
    assert game.world.get(pid, Skills).apply_armor == 8  # armor 注入，wuxia_special 忽略


# ──────────────────────── remove 反向扣减 ────────────────────────


def test_remove_success_reverses_props() -> None:
    """remove 成功：卸下 + armors 清空 + apply_armor 反向扣减归 0。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    wear(game, pid, "cloth")
    assert game.world.get(pid, Skills).apply_armor > 0
    msgs = remove(game, pid, "cloth")
    assert any("脱了下来" in m for m in msgs)
    eq = game.world.get(pid, Equipment)
    assert "cloth" not in eq.armors
    assert game.world.get(pid, Skills).apply_armor == 0


def test_remove_not_equipped() -> None:
    """remove 未装备护甲 -> '你并没有装备这样东西。'。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    assert remove(game, pid, "cloth") == ["你并没有装备这样东西。"]


def test_remove_weapon_not_treated_as_armor() -> None:
    """remove 已装备武器（非护甲槽）-> '你并没有装备这样东西。'（remove 只管护甲槽）。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "changjian")
    wield(game, pid, "changjian")
    assert remove(game, pid, "changjian") == ["你并没有装备这样东西。"]


def test_remove_all() -> None:
    """remove all：遍历已装备护甲逐个卸 + 'Ok。'。"""
    game, pid = load_game("xueshan_micro")
    _inject_armor_spec(game, "test-cloth", name="布衣", armor_type="cloth")
    _inject_armor_spec(game, "test-hat", name="帽", armor_type="head")
    _add_inv(game, pid, "test-cloth", "test-hat")
    wear(game, pid, "test-cloth")
    wear(game, pid, "test-hat")
    msgs = remove(game, pid, "all")
    assert "Ok。" in msgs
    assert not game.world.get(pid, Equipment).armors


# ──────────────────────── 8 段管线 adapter 路径 ────────────────────────


def test_wear_via_command_registry_adapter() -> None:
    """wear 经 COMMAND_REGISTRY adapter（8 段管线路径）可执行。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    ctx = new_context(verb="wear", raw_args="cloth", actor=pid)
    msgs = COMMAND_REGISTRY["wear"](game, ctx)
    assert any("你穿上" in m for m in msgs)
    assert game.world.get(pid, Equipment).armors["cloth"] == "cloth"


def test_remove_via_command_registry_adapter() -> None:
    """remove 经 COMMAND_REGISTRY adapter 可执行。"""
    game, pid = load_game("xueshan_micro")
    _add_inv(game, pid, "cloth")
    wear(game, pid, "cloth")
    ctx = new_context(verb="remove", raw_args="cloth", actor=pid)
    msgs = COMMAND_REGISTRY["remove"](game, ctx)
    assert any("脱了下来" in m for m in msgs)
    assert "cloth" not in game.world.get(pid, Equipment).armors
