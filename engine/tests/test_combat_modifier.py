"""CombatModifier 声明式载体测试（ADR-0027 §2.2）。

验证：
1. 载体字段完整性 + 默认值 + frozen 不可变
2. 主题无关性断言（源码无"阵法"/"合击"/"anubis"/"sword"/"blade"字面量）
3. 可序列化往返（dataclasses.asdict）
4. CombatModifier 注入 CombatContext 快照路径：attack_modifier -> attacker.apply_attack
   使 ap 修正生效，defense_modifier -> victim.apply_dodge 使 dp 修正生效。
5. special_attack 调用点（ADR-0027 §2.3）：CombatSystem.tick 读 formation_modifier
   注入快照副本 -> resolve_attack 生效（ap 修正命中率 / dp 修正闪避率 / message 注入
   ledger / formation_modifier=None 行为不变回归）。
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from xkx.combat import modifier as modifier_mod
from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.modifier import CombatModifier
from xkx.combat.replay import CombatSnapshot
from xkx.combat.resolve_attack import ATTACK, DEFENSE, skill_power
from xkx.combat.result import RESULT_HIT
from xkx.combat.system import CombatSystem

# ---- 1. 载体字段 + 默认值 + frozen 不可变 ----


def test_modifier_required_and_default_fields() -> None:
    """modifier_type 必填，其余字段有默认值。"""
    m = CombatModifier(modifier_type="combined_attack")
    assert m.modifier_type == "combined_attack"
    assert m.participants == ()
    assert m.attack_modifier == 0
    assert m.defense_modifier == 0
    assert m.message == ""
    assert m.post_action is None


def test_modifier_all_fields_set() -> None:
    """全字段构造 + tuple 类型保持（不可变序列）。"""
    m = CombatModifier(
        modifier_type="formation",
        participants=(1, 2, 3),
        attack_modifier=50,
        defense_modifier=30,
        message="$N 与同伴联手夹击$n$l",
        post_action="on_formation_hit",
    )
    assert m.modifier_type == "formation"
    assert m.participants == (1, 2, 3)
    assert m.attack_modifier == 50
    assert m.defense_modifier == 30
    assert m.message == "$N 与同伴联手夹击$n$l"
    assert m.post_action == "on_formation_hit"


def test_modifier_field_completeness() -> None:
    """字段集与 ADR-0027 §2.2 声明一致（6 字段）。"""
    expected = {
        "modifier_type",
        "participants",
        "attack_modifier",
        "defense_modifier",
        "message",
        "post_action",
    }
    assert {f.name for f in dataclasses.fields(CombatModifier)} == expected


def test_modifier_is_frozen() -> None:
    """frozen=True：字段赋值抛 FrozenInstanceError。"""
    m = CombatModifier(modifier_type="combined_attack", attack_modifier=10)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.attack_modifier = 99  # type: ignore[misc]


def test_modifier_has_slots() -> None:
    """slots=True：无 __dict__，无法动态添加属性。

    frozen+slots dataclass 赋值不存在的属性时抛 TypeError（slots 拦截），
    已存在属性赋值抛 FrozenInstanceError（frozen 拦截，见 test_modifier_is_frozen）。
    """
    m = CombatModifier(modifier_type="combined_attack")
    assert not hasattr(m, "__dict__")
    with pytest.raises((AttributeError, TypeError)):
        m.extra_field = 1  # type: ignore[attr-defined]


def test_modifier_equality_and_hash() -> None:
    """frozen dataclass 可哈希 + 值相等。"""
    a = CombatModifier(modifier_type="formation", participants=(1, 2), attack_modifier=5)
    b = CombatModifier(modifier_type="formation", participants=(1, 2), attack_modifier=5)
    assert a == b
    assert hash(a) == hash(b)


# ---- 2. 主题无关性断言 ----


def test_modifier_source_has_no_wuxia_literals() -> None:
    """防回归硬门禁：modifier.py 源码不含武侠语义字面量。

    ADR-0027 §2.2 + ADR-0003：CombatModifier 是主题无关声明式载体，内核不得
    硬编码武侠语义。检查源码字符串字面量。
    """
    src = inspect.getsource(modifier_mod)
    # 中文武侠语义字面量
    assert "阵法" not in src
    assert "合击" not in src
    # 英文武侠特有标记/武器字面量
    for lit in ("anubis", "sword", "blade"):
        assert f'"{lit}"' not in src, f"源码含双引号字面量: {lit}"
        assert f"'{lit}'" not in src, f"源码含单引号字面量: {lit}"


def test_modifier_type_values_are_generic() -> None:
    """modifier_type 取值是通用协同类型枚举，非武侠特有语义。

    ADR-0027 §2.2：modifier_type 是"formation"/"formation_break"/"combined_attack"
    等通用类型字符串，内核不解释。这里验证类型字符串本身可被构造（不抛错），
    具体语义由题材数据侧解释。
    """
    for t in ("formation", "formation_break", "combined_attack"):
        m = CombatModifier(modifier_type=t)
        assert m.modifier_type == t


# ---- 3. 可序列化往返 ----


def test_modifier_asdict_roundtrip() -> None:
    """dataclasses.asdict 往返：序列化 -> 重建 -> 值相等。"""
    original = CombatModifier(
        modifier_type="combined_attack",
        participants=(10, 20, 30),
        attack_modifier=50,
        defense_modifier=-10,
        message="$N 夹击$n",
        post_action="on_combined_hit",
    )
    d = dataclasses.asdict(original)
    # dataclasses.asdict 对 tuple 字段保持 tuple（不转 list）
    assert d["participants"] == (10, 20, 30)
    # 重建：asdict 产出 dict，直接解包重建（tuple 类型保持）
    rebuilt = CombatModifier(**d)
    assert rebuilt == original


def test_modifier_asdict_minimal() -> None:
    """最小构造的 asdict 含全部字段键。"""
    m = CombatModifier(modifier_type="formation")
    d = dataclasses.asdict(m)
    assert set(d.keys()) == {
        "modifier_type",
        "participants",
        "attack_modifier",
        "defense_modifier",
        "message",
        "post_action",
    }
    assert d["participants"] == ()
    assert d["post_action"] is None


# ---- 4. CombatModifier 注入 CombatContext 快照路径 ----


def _base_attacker() -> CombatantSnapshot:
    """基线 attacker：apply_attack=0，便于验证注入后 ap 增量。"""
    return CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"unarmed": 80},
        max_qi=600,
        qi=600,
        eff_qi=600,
        max_jingli=300,
        jingli=300,
    )


def _base_victim() -> CombatantSnapshot:
    """基线 victim：apply_dodge=0，便于验证注入后 dp 增量。"""
    return CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=10,
        dex_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        max_qi=100,
        qi=100,
        eff_qi=100,
        max_jingli=50,
        jingli=50,
    )


def test_modifier_attack_modifier_injects_into_snapshot_ap() -> None:
    """attack_modifier 注入 attacker.apply_attack 后 ap 修正生效（ap += attack_modifier）。

    注入路径（ADR-0027 §2.2 内核职责）：CombatSystem 把 CombatModifier.attack_modifier
    叠加到 attacker 的 apply_attack。skill_power 的 ATTACK 路径 level =
    skills[skill] + apply_attack，故 ap 增量 == attack_modifier 的立方贡献差。
    """
    attacker = _base_attacker()
    skill_id = "unarmed"
    ap_before = skill_power(attacker, skill_id, ATTACK)

    modifier = CombatModifier(
        modifier_type="combined_attack",
        participants=(1, 3),
        attack_modifier=50,
        defense_modifier=0,
    )
    # 注入：attacker.apply_attack += modifier.attack_modifier（model_copy 保持快照不可变）
    injected = attacker.model_copy(
        update={"apply_attack": attacker.apply_attack + modifier.attack_modifier}
    )
    ap_after = skill_power(injected, skill_id, ATTACK)

    # skill_power ATTACK 公式：power = (level^3)//3 + str_*2，level = skill + apply_attack
    # apply_attack 从 0 -> 50，level 从 80 -> 130
    # 分步整除（与 skill_power 实现一致），避免 (a-b)//3 与 a//3-b//3 的整除差
    expected_delta = (130**3) // 3 - (80**3) // 3
    assert ap_after - ap_before == expected_delta
    assert ap_after > ap_before


def test_modifier_defense_modifier_injects_into_snapshot_dp() -> None:
    """defense_modifier 注入 victim.apply_dodge 后 dp 修正生效（dp += defense_modifier）。

    注入路径：CombatSystem 把 CombatModifier.defense_modifier 叠加到 victim 的
    apply_dodge。skill_power 的 DEFENSE dodge 路径 level = skills["dodge"] +
    apply_dodge，故 dp 增量 == defense_modifier 的立方贡献差。
    """
    victim = _base_victim()
    dp_before = skill_power(victim, "dodge", DEFENSE)

    modifier = CombatModifier(
        modifier_type="combined_attack",
        participants=(1, 2),
        attack_modifier=0,
        defense_modifier=30,
    )
    injected = victim.model_copy(
        update={"apply_dodge": victim.apply_dodge + modifier.defense_modifier}
    )
    dp_after = skill_power(injected, "dodge", DEFENSE)

    # victim dodge=0 + apply_dodge 0 -> 30，level 0 -> 30
    # level<1 时走经验补偿分支，level>=1 走 (level^3)/3 + dex*2
    # 原 level=0 -> combat_exp(0)//20 * (jingli_bonus//10) = 0
    # 注入后 level=30 -> (30^3)/3 + dex*2 = 9000 + 2
    assert dp_before == 0
    assert dp_after == (30**3) // 3 + victim.dex_ * 2
    assert dp_after > dp_before


def test_modifier_full_injection_into_combat_context() -> None:
    """CombatModifier 完整注入 CombatContext 双方快照：ap/dp 同时修正。

    模拟 ADR-0027 §2.2 内核注入路径：
    - attacker.apply_attack += attack_modifier
    - victim.apply_dodge += defense_modifier
    构造注入后的 CombatContext，验证 ap/dp 均反映修正值。
    """
    attacker = _base_attacker()
    victim = _base_victim()

    modifier = CombatModifier(
        modifier_type="combined_attack",
        participants=(1, 2, 3),
        attack_modifier=50,
        defense_modifier=30,
        message="$N 与同伴联手夹击$n$l",
        post_action="on_combined_hit",
    )

    # 注入快照（model_copy 保持原快照不可变，产出注入后新快照）
    injected_attacker = attacker.model_copy(
        update={"apply_attack": attacker.apply_attack + modifier.attack_modifier}
    )
    injected_victim = victim.model_copy(
        update={"apply_dodge": victim.apply_dodge + modifier.defense_modifier}
    )
    ctx = CombatContext(attacker=injected_attacker, victim=injected_victim, seed=42)

    ap = skill_power(ctx.attacker, "unarmed", ATTACK)
    dp = skill_power(ctx.victim, "dodge", DEFENSE)

    # 验证修正生效：ap/dp 均大于未注入基线
    ap_base = skill_power(attacker, "unarmed", ATTACK)
    dp_base = skill_power(victim, "dodge", DEFENSE)
    assert ap > ap_base
    assert dp > dp_base

    # message 载体含 $N/$n 占位符（PronounContext 渲染，ADR-0028）
    assert "$N" in modifier.message and "$n" in modifier.message
    # post_action 回调名透传（内核不解释）
    assert modifier.post_action == "on_combined_hit"


# ---- 5. special_attack 调用点（ADR-0027 §2.3）：CombatSystem.tick 驱动 ----


def _tick_attacker() -> CombatantSnapshot:
    """tick 驱动用 attacker（entity_id=1，甲）：unarmed 适中，无 dodge 技能。

    无 dodge 技能 -> 2->1 那轮（乙攻甲）甲不闪避，避免干扰 1->2 那轮观察。
    apply_attack=0 便于验证 attack_modifier 注入增量。
    """
    return CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=20,
        dex_=20,
        combat_exp=5000,
        skills={"unarmed": 50},
        max_qi=600,
        qi=600,
        eff_qi=600,
        max_jingli=300,
        jingli=300,
    )


def _tick_victim_with_dodge() -> CombatantSnapshot:
    """tick 驱动用 victim（entity_id=2，乙）：dodge 技能高，dp 大易闪避。

    dodge=50 -> dp 较大，baseline 1->2 那轮有可观闪避概率；注入 attack_modifier
    后 ap 增大，闪避概率下降（命中率提升）。注入 defense_modifier 后 dp 更大，
    闪避概率上升。
    """
    return CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=5,
        dex_=20,
        con_=10,
        combat_exp=1000,
        skills={"dodge": 50, "unarmed": 10},
        max_qi=200,
        qi=200,
        eff_qi=200,
        max_jingli=100,
        jingli=100,
    )


def _two_combatant_snapshot(
    attacker_mod: CombatModifier | None = None,
    victim_mod: CombatModifier | None = None,
) -> CombatSnapshot:
    """构建两 combatant 快照，可选注入 formation_modifier。

    注入路径模拟 ADR-0027 §2.3 实现期细化：runtime 层 CombatBridge 从 Marks 查
    阵法标记 -> 注入 CombatantSnapshot.formation_modifier。本测试直接在快照
    构建边界注入（后置整合前的手动注入），验证 CombatSystem.tick 读取并 apply。
    """
    a = _tick_attacker()
    v = _tick_victim_with_dodge()
    if attacker_mod is not None:
        a = a.model_copy(update={"formation_modifier": attacker_mod})
    if victim_mod is not None:
        v = v.model_copy(update={"formation_modifier": victim_mod})
    return CombatSnapshot(combatants={1: a, 2: v}, seed=42)


def _hit_count_over_seeds(
    snapshot: CombatSnapshot,
    n: int = 200,
) -> int:
    """跑 n 个 seed 统计 1->2 那轮（results[0]）的命中次数。

    results[0] 是 attacker=1 -> victim=2 那轮（tick 内 seq=0，seed+0）。
    命中 = result_code == RESULT_HIT（非 dodge/parry）。
    """
    sys = CombatSystem()
    hits = 0
    for seed in range(n):
        results = sys.tick(snapshot, seed=seed)
        # results[0] 对应 seq=0（attacker_id=1 -> victim_id=2）
        if results[0].result_code == RESULT_HIT:
            hits += 1
    return hits


def test_special_attack_callout_attacker_modifier_raises_hit_rate() -> None:
    """attacker 有 formation_modifier -> ap 修正生效，命中率提升（多 seed 采样）。

    ADR-0027 §2.3 special_attack 调用点：CombatSystem.tick 读 attacker.formation_modifier，
    apply 到快照副本（apply_attack += attack_modifier），ap 增大 -> dodge 概率下降
    （dodge_p = dp/(ap+dp)），命中率提升。

    用 200 seed 采样统计命中率，注入后命中率应显著高于 baseline。
    """
    baseline_snapshot = _two_combatant_snapshot()
    mod_snapshot = _two_combatant_snapshot(
        attacker_mod=CombatModifier(
            modifier_type="combined_attack",
            participants=(1, 3),
            attack_modifier=80,
        )
    )
    baseline_hits = _hit_count_over_seeds(baseline_snapshot)
    mod_hits = _hit_count_over_seeds(mod_snapshot)
    # 注入 attack_modifier 后命中率显著提升（ap 增大 -> dodge 概率下降）
    assert mod_hits > baseline_hits


def test_special_attack_callout_victim_modifier_raises_dodge_rate() -> None:
    """victim 有 formation_modifier -> dp 修正生效，闪避率提升（多 seed 采样）。

    ADR-0027 §2.3：CombatSystem.tick 读 victim.formation_modifier，apply 到快照副本
    （apply_dodge += defense_modifier），dp 增大 -> dodge 概率上升
    （dodge_p = dp/(ap+dp)），命中率下降。

    用 200 seed 采样统计命中率，注入后命中率应显著低于 baseline。
    """
    baseline_snapshot = _two_combatant_snapshot()
    mod_snapshot = _two_combatant_snapshot(
        victim_mod=CombatModifier(
            modifier_type="formation",
            participants=(2, 3),
            defense_modifier=80,
        )
    )
    baseline_hits = _hit_count_over_seeds(baseline_snapshot)
    mod_hits = _hit_count_over_seeds(mod_snapshot)
    # 注入 defense_modifier 后 victim dp 增大 -> dodge 概率上升 -> 命中率下降
    assert mod_hits < baseline_hits


def test_special_attack_callout_both_modifiers_apply() -> None:
    """双方都有 formation_modifier -> ap/dp 都修正（多 seed 采样）。

    attacker.attack_modifier 提升 ap（命中率升），victim.defense_modifier 提升 dp
    （命中率降）。双方对冲：最终命中率介于"仅 attacker 修正"与"仅 victim 修正"之间。
    验证注入路径对双方都生效（非互斥）。
    """
    only_attacker = _two_combatant_snapshot(
        attacker_mod=CombatModifier(
            modifier_type="combined_attack",
            participants=(1, 3),
            attack_modifier=80,
        )
    )
    only_victim = _two_combatant_snapshot(
        victim_mod=CombatModifier(
            modifier_type="formation",
            participants=(2, 3),
            defense_modifier=80,
        )
    )
    both = _two_combatant_snapshot(
        attacker_mod=CombatModifier(
            modifier_type="combined_attack",
            participants=(1, 3),
            attack_modifier=80,
        ),
        victim_mod=CombatModifier(
            modifier_type="formation",
            participants=(2, 3),
            defense_modifier=80,
        ),
    )
    hits_only_attacker = _hit_count_over_seeds(only_attacker)
    hits_only_victim = _hit_count_over_seeds(only_victim)
    hits_both = _hit_count_over_seeds(both)
    # 仅 attacker 修正命中率最高，仅 victim 修正命中率最低，双方对冲居中
    assert hits_only_attacker > hits_only_victim
    assert hits_only_victim < hits_both < hits_only_attacker


def test_special_attack_callout_none_modifier_baseline_unchanged() -> None:
    """formation_modifier=None -> 行为不变（回归测试，对比无 modifier 的 baseline）。

    ADR-0027 §2.3：formation_modifier 默认 None，无阵法时 CombatSystem.tick 行为
    不变。验证：未注入 formation_modifier 的快照与显式 None 的快照 tick 输出一致。
    """
    # 快照 A：完全不设 formation_modifier（默认 None）
    snapshot_a = _two_combatant_snapshot()
    # 快照 B：显式注入 None（模拟 runtime 层查 Marks 未命中阵法标记）
    snapshot_b = _two_combatant_snapshot(
        attacker_mod=None,
        victim_mod=None,
    )
    sys = CombatSystem()
    for seed in (0, 1, 42, 99, 12345):
        ra = sys.tick(snapshot_a, seed=seed)
        rb = sys.tick(snapshot_b, seed=seed)
        assert ra == rb


def test_special_attack_callout_message_injected_into_ledger() -> None:
    """attacker.formation_modifier.message 非空 -> action_message 替换 -> ledger 含渲染后文本。

    ADR-0027 §2.3：CombatSystem.tick 读 attacker.formation_modifier，非空 message
    替换 attacker.action_message，resolve_attack 第 1 步渲染该 message 入 ledger。
    flatten_messages 应含 modifier.message 渲染后的文本（$N/$n/$l 占位符已替换）。
    """
    modifier = CombatModifier(
        modifier_type="combined_attack",
        participants=(1, 2, 3),
        attack_modifier=10,
        message="$N 与同伴联手夹击$n$l",
        post_action="on_combined_hit",
    )
    snapshot = _two_combatant_snapshot(attacker_mod=modifier)
    sys = CombatSystem()
    results = sys.tick(snapshot, seed=42)
    # results[0] 对应 attacker=1(甲) -> victim=2(乙)
    msgs = CombatSystem.flatten_messages(results[0])
    # 注入的 message 渲染后应出现在 ledger（$N->甲, $n->乙, $l->某 limb）
    rendered = [m for m in msgs if "联手夹击" in m]
    assert len(rendered) >= 1
    # $N 已渲染为 attacker 名"甲"，$n 渲染为 victim 名"乙"
    assert "甲" in rendered[0]
    assert "乙" in rendered[0]
    # $l 已渲染为某 limb（非占位符残留）
    assert "$N" not in rendered[0]
    assert "$n" not in rendered[0]
    assert "$l" not in rendered[0]


def test_special_attack_callout_post_action_injected_into_ledger() -> None:
    """attacker.formation_modifier.post_action 非空 -> action_post_action_result 替换。

    替换后 resolve_attack 后处理（规格 order=47）把该文本入 ledger。
    flatten_messages 应含 post_action 文本（仅在命中回合，dodge/parry 提前 return
    不执行后处理）。

    ADR-0027 §2.3：CombatSystem.tick 读 attacker.formation_modifier，非空 post_action
    替换 attacker.action_post_action_result，resolve_attack 后处理（规格 order=47）
    把该文本入 ledger。flatten_messages 应含 post_action 文本。
    """
    modifier = CombatModifier(
        modifier_type="combined_attack",
        participants=(1, 2),
        attack_modifier=10,
        message="$N 夹击$n$l",
        post_action="（合击余韵：$n 受到额外冲击）",
    )
    snapshot = _two_combatant_snapshot(attacker_mod=modifier)
    sys = CombatSystem()
    # 遍历 seed 找到命中的回合（dodge/parry 提前 return 不执行 post_action 后处理）
    found = False
    for seed in range(50):
        results = sys.tick(snapshot, seed=seed)
        if results[0].result_code != RESULT_HIT:
            continue
        msgs = CombatSystem.flatten_messages(results[0])
        if any("合击余韵" in m for m in msgs):
            found = True
            break
    assert found, "命中回合的 ledger 应含 post_action 文本"


def test_special_attack_callout_victim_message_not_replaced() -> None:
    """victim.formation_modifier 不替换 attacker 的 action_message。

    ADR-0027 §2.3 实现期细化：victim 路径只 apply defense_modifier 到 apply_dodge，
    不替换 message/post_action。resolve_attack 只渲染 attacker.action_message，victim
    的 message 字段不被读取。验证：1->2 那轮 attacker(甲) 无 formation_modifier 时，
    ledger 含甲的默认招式文本（"试探"），不含 victim(乙) formation_modifier.message
    （"联手夹击"）。
    """
    # victim(乙) 有 formation_modifier（含 message），attacker(甲) 无
    modifier = CombatModifier(
        modifier_type="formation",
        participants=(2, 3),
        defense_modifier=50,
        message="$N 与同伴联手夹击$n$l",
        post_action="on_formation_hit",
    )
    snapshot = _two_combatant_snapshot(victim_mod=modifier)
    sys = CombatSystem()
    results = sys.tick(snapshot, seed=42)
    # results[0] 对应 attacker=1(甲) -> victim=2(乙)
    # 甲无 formation_modifier，action_message 是默认"试探"；乙的 message 不被渲染
    msgs_r0 = CombatSystem.flatten_messages(results[0])
    assert any("试探" in m for m in msgs_r0)
    assert not any("联手夹击" in m for m in msgs_r0)

