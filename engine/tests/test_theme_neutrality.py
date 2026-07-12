"""CombatKernel 主题无关性硬门禁（04 kill criteria 2 / 范围检查点 2）。

验证核心战斗引擎不硬编码武侠语义：
1. 非武侠题材（火器/戒尺）snapshot 跑 resolve_attack，武器->技能/标签映射走题材
   数据声明（attack_skill/weapon_label），不 fallback 到武侠默认；
2. resolve_attack 模块源码不含 sword/blade 字符串字面量（防回归硬门禁）；
3. neili（内力）不在 CombatantSnapshot 核心签名（ADR-0003）。

关联 [05] dissent 1（CombatKernel 抽象时机张力）：从武侠提取的接口用非武侠验证。
"""

from __future__ import annotations

import inspect

from xkx.combat import resolve_attack as resolve_attack_mod
from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.combat.result import KIND_SKILL_IMPROVE, RESULT_HIT


def _firearm_attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=1,
        name="海盗",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"firearm": 80},
        weapon="firearm",
        attack_skill="firearm",
        weapon_label="火枪",
        action_message="$N端起$w，对准$n$l",
        max_qi=600,
        qi=600,
        max_jingli=300,
        jingli=300,
    )


def _ruler_attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=3,
        name="监生",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"ruler": 80},
        weapon="ruler",
        attack_skill="ruler",
        weapon_label="戒尺",
        action_message="$N挥起$w，抽向$n$l",
        max_qi=600,
        qi=600,
        max_jingli=300,
        jingli=300,
    )


def _victim() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=2,
        name="靶子",
        dex_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        max_qi=10,
        qi=10,
    )


def test_firearm_theme_runs_and_uses_declared_mapping() -> None:
    """火器题材：resolve_attack 走声明的 attack_skill=firearm / weapon_label=火枪。"""
    ctx = CombatContext(attacker=_firearm_attacker(), victim=_victim(), seed=0)
    r = resolve_attack(ctx)
    assert r.result_code == RESULT_HIT
    # weapon_label 走题材声明（$w 替换），非内核 fallback
    assert any("火枪" in m for m in r.messages)
    # attack_skill 走题材声明 -> skill_improve detail=firearm
    improves = [e for e in r.effects if e.kind == KIND_SKILL_IMPROVE]
    assert improves and improves[0].detail == "firearm"


def test_ruler_theme_runs_and_uses_declared_mapping() -> None:
    """戒尺题材：同样验证非武侠武器映射走题材声明。"""
    ctx = CombatContext(attacker=_ruler_attacker(), victim=_victim(), seed=0)
    r = resolve_attack(ctx)
    assert r.result_code == RESULT_HIT
    assert any("戒尺" in m for m in r.messages)
    improves = [e for e in r.effects if e.kind == KIND_SKILL_IMPROVE]
    assert improves and improves[0].detail == "ruler"


def test_non_wuxia_deterministic_replay() -> None:
    """非武侠 snapshot 同 seed 同输出（combat 确定性不绑题材）。"""
    ctx = CombatContext(attacker=_firearm_attacker(), victim=_victim(), seed=123)
    assert resolve_attack(ctx) == resolve_attack(ctx)


def test_resolve_attack_source_has_no_wuxia_weapon_literals() -> None:
    """防回归硬门禁：resolve_attack 模块源码不得含 sword/blade 字符串字面量。"""
    src = inspect.getsource(resolve_attack_mod)
    assert '"sword"' not in src and "'sword'" not in src
    assert '"blade"' not in src and "'blade'" not in src


def test_neili_not_in_core_snapshot() -> None:
    """ADR-0003：内力（neili）不进 CombatantSnapshot 核心签名。"""
    fields = CombatantSnapshot.model_fields
    assert "neili" not in fields
    assert "max_neili" not in fields


def test_combat_kernel_extensions_have_no_formation_literals() -> None:
    """防回归硬门禁：2.4 扩展不得含阵法/合击/anubis/武侠武器字面量（ADR-0027 §2.4）。

    协同攻击修正是题材内容（题材包武学脚本），内核只做分发；call_out 翻译的
    EffectComp 字段主题无关。集中扫描 combat/modifier.py + combat/system.py +
    runtime/auto_fight.py，确保 2.4 扩展不把武侠阵法语义锁进内核。
    """
    from xkx.combat import modifier as modifier_mod
    from xkx.combat import system as system_mod
    from xkx.runtime import auto_fight as auto_fight_mod

    # ADR-0027 §2.4 黑名单：阵法/合击/anubis（阵法标记）+ sword/blade（武侠武器）
    forbidden = ("阵法", "合击", "anubis", "sword", "blade")
    for mod in (modifier_mod, system_mod, auto_fight_mod):
        src = inspect.getsource(mod)
        for lit in forbidden:
            assert lit not in src, f"{mod.__name__} 源码含禁止字面量 {lit!r}"


# ──────────────────────── ADR-0030 决策 4：2.7 门派切割收官硬门禁 ────────────────────────


def test_runtime_source_has_no_wuxia_room_paths() -> None:
    """ADR-0030 决策 4：governance/death/cli/race/family 源码无武侠房间路径字面量。

    武侠房间路径（shaolin/dali/xueshan 等）是题材内容，由 ThemeConfig 注入，
    不硬编码在引擎语义代码中。dbase_map.py 的 "dali/" dbase key 前缀是 LPC
    兼容保真让步（决策 3 豁免），theme.py 的 ThemeConfig.wuxia() 是题材包配置数据。
    """
    from xkx import cli as cli_mod
    from xkx.runtime import death as death_mod
    from xkx.runtime import family as family_mod
    from xkx.runtime import governance as governance_mod
    from xkx.runtime import race as race_mod

    banned_paths = ("shaolin/", "dali/", "xueshan/", "huashan/", "wudang/", "emei/")
    for mod in (governance_mod, death_mod, race_mod, family_mod, cli_mod):
        src = inspect.getsource(mod)
        for path in banned_paths:
            assert path not in src, f"{mod.__name__} 源码含武侠房间路径 {path!r}"


def test_runtime_source_has_no_family_name_literals() -> None:
    """ADR-0030 决策 4：governance/death/cli/race/family 源码无门派名字面量。"""
    from xkx import cli as cli_mod
    from xkx.runtime import death as death_mod
    from xkx.runtime import family as family_mod
    from xkx.runtime import governance as governance_mod
    from xkx.runtime import race as race_mod

    banned_names = (
        "武当", "少林", "峨嵋", "华山", "丐帮", "桃花", "古墓",
        "灵鹫", "星宿", "白驼", "明教", "雪山派", "血刀", "大理段", "全真",
    )
    for mod in (governance_mod, death_mod, race_mod, family_mod, cli_mod):
        src = inspect.getsource(mod)
        for name in banned_names:
            assert name not in src, f"{mod.__name__} 源码含门派名 {name!r}"


def test_theme_config_wuxia_contains_wuxia_paths() -> None:
    """ThemeConfig.wuxia() 含武侠路径（题材包配置数据，ADR-0030 决策 2）。

    武侠路径只存在于 theme.py 的 ThemeConfig.wuxia() 方法体中，是题材包注入数据，
    类比 ADR-0028 CLASS_TITLE_TABLE 题材包数据。引擎语义代码不硬编码这些路径。
    """
    from xkx.runtime.theme import ThemeConfig

    cfg = ThemeConfig.wuxia()
    assert cfg.start_room == "xueshan/shanmen"
    assert cfg.death_room == "death/gate"
    assert "city_jail" in cfg.jail_rooms
    assert cfg.jail_rooms["bonze_jail"] == "shaolin/guangchang1"
    assert cfg.jail_rooms["dali_jail"] == "dali/taihejie5"


def test_theme_config_default_has_no_wuxia_paths() -> None:
    """ThemeConfig.default() 无武侠路径（非武侠测试默认配置）。"""
    from xkx.runtime.theme import ThemeConfig

    cfg = ThemeConfig.default()
    banned = ("shaolin", "dali", "xueshan", "huashan", "wudang", "emei", "death/gate")
    for path in banned:
        assert path not in cfg.start_room
        assert path not in cfg.death_room
        assert path not in cfg.revive_room
