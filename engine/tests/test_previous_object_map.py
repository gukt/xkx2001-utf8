"""PREVIOUS_OBJECT_MAP 测试（阶段 1 Wave 2 T4，ADR-0021）。

覆盖：
- A/B/C 三类映射（category 字段正确）
- 启动期校验（validate_previous_object_map + MappingError）
- source 显式传参（new_context source 默认 = actor）
- viewer 不变量（PronounContext 三元组 viewer 显式传参）
- 映射表覆盖 9 层规格典型调用点

[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md)
"""

from __future__ import annotations

import inspect

from xkx.runtime.action_context import new_context
from xkx.runtime.previous_object_map import (
    PREVIOUS_OBJECT_MAP,
    MappingError,
    PreviousObjectCategory,
    assert_previous_object_map,
    category_counts,
    entries_by_category,
    validate_previous_object_map,
)
from xkx.runtime.pronoun import PronounService, visible
from xkx.runtime.system_context import SystemContext

# ---- A/B/C 三类映射 ----


def test_map_has_all_three_categories() -> None:
    """映射表含 A/B/C 三类（ADR-0021 决策 2）。"""
    counts = category_counts()
    assert PreviousObjectCategory.A_COMMAND in counts
    assert PreviousObjectCategory.B_PRONOUN in counts
    assert PreviousObjectCategory.C_SYSTEM in counts
    assert counts[PreviousObjectCategory.A_COMMAND] > 0
    assert counts[PreviousObjectCategory.B_PRONOUN] > 0
    assert counts[PreviousObjectCategory.C_SYSTEM] > 0


def test_a_class_targets_action_context_source() -> None:
    """A 类映射目标 -> ActionContext.source / capability_token（Command 路径权限检查）。"""
    a_entries = entries_by_category(PreviousObjectCategory.A_COMMAND)
    assert len(a_entries) >= 3  # force_me/disable_player/set_status/valid_cmd
    # force_me 映射到 source.capability_token
    force_me = [e for e in a_entries if e.lpc_func == "force_me"]
    assert len(force_me) == 1
    assert "ActionContext.source" in force_me[0].greenfield_target
    assert "capability_token" in force_me[0].greenfield_target


def test_b_class_targets_action_context_viewer() -> None:
    """B 类映射目标 -> ActionContext.viewer（PronounContext / 可见性求值）。"""
    b_entries = entries_by_category(PreviousObjectCategory.B_PRONOUN)
    assert len(b_entries) >= 2  # visible + rankd query_close/query_self_close
    for entry in b_entries:
        assert "ActionContext.viewer" in entry.greenfield_target


def test_c_class_targets_system_context() -> None:
    """C 类映射目标 -> SystemContext（或检查已删除）。"""
    c_entries = entries_by_category(PreviousObjectCategory.C_SYSTEM)
    assert len(c_entries) >= 2  # heart_beat + do_attack
    for entry in c_entries:
        assert "SystemContext" in entry.greenfield_target or "已删除" in entry.greenfield_target


def test_force_me_maps_to_a_class() -> None:
    """force_me 的 previous_object() 门控映射到 A 类 source.capability_token。"""
    force_me_entries = [
        e for e in PREVIOUS_OBJECT_MAP if e.lpc_func == "force_me"
    ]
    assert len(force_me_entries) == 1
    entry = force_me_entries[0]
    assert entry.category == PreviousObjectCategory.A_COMMAND
    assert "ROOT_UID" in entry.lpc_expr
    assert "source" in entry.greenfield_target


def test_visible_maps_to_b_class() -> None:
    """visible(me, ob) 的 this_player() 映射到 B 类 viewer。"""
    visible_entries = [
        e for e in PREVIOUS_OBJECT_MAP if e.lpc_func == "visible"
    ]
    assert len(visible_entries) == 1
    entry = visible_entries[0]
    assert entry.category == PreviousObjectCategory.B_PRONOUN
    assert "viewer" in entry.greenfield_target


def test_heart_beat_maps_to_c_class() -> None:
    """heart_beat 的 previous_object() 检查映射到 C 类（SystemContext 或已删除）。"""
    hb_entries = [
        e for e in PREVIOUS_OBJECT_MAP if e.lpc_func == "heart_beat"
    ]
    assert len(hb_entries) >= 1
    for entry in hb_entries:
        assert entry.category == PreviousObjectCategory.C_SYSTEM


# ---- 启动期校验 ----


def test_validate_previous_object_map_clean() -> None:
    """正常路径：映射表全部合法（启动期校验通过）。"""
    issues = validate_previous_object_map()
    assert issues == [], f"映射表校验问题: {issues}"


def test_assert_previous_object_map_passes() -> None:
    """assert_previous_object_map 无问题时正常返回（不 raise）。"""
    assert_previous_object_map()  # 不 raise


def test_map_load_time_validation() -> None:
    """模块导入时自动校验（ensure_validated 已执行，ADR-0019 启动期失败思路）。"""
    # 模块已加载（顶部 import 触发 ensure_validated），无 MappingError
    # 重新调用 ensure_validated 幂等
    from xkx.runtime.previous_object_map import ensure_validated

    ensure_validated()  # 不 raise


def test_mapping_error_is_runtime_error() -> None:
    """MappingError 是 RuntimeError 子类（启动期失败可被捕获）。"""
    assert issubclass(MappingError, RuntimeError)


# ---- source 显式传参 ----


def test_new_context_source_defaults_to_actor() -> None:
    """new_context 不传 source 时默认 source = actor（玩家命令路径）。"""
    ctx = new_context(verb="look", raw_args="", actor=42)
    assert ctx.source == 42  # 默认 source = actor
    assert ctx.viewer == 42  # 默认 viewer = actor
    assert ctx.actor == 42


def test_new_context_source_explicit() -> None:
    """new_context 显式传 source（PrivilegedAction 路径 source != actor）。"""
    ctx = new_context(
        verb="look", raw_args="", actor=42, source=999
    )
    assert ctx.actor == 42
    assert ctx.source == 999  # 系统调用者
    assert ctx.source != ctx.actor  # PrivilegedAction 路径
    assert ctx.viewer == 42  # viewer 仍 = actor（被代执行者）


def test_action_context_is_frozen() -> None:
    """ActionContext 是 frozen dataclass（不可变，frozen dataclass 信封）。"""
    ctx = new_context(verb="look", raw_args="", actor=1)
    try:
        ctx.verb = "kill"  # type: ignore[misc]
        raise AssertionError("frozen dataclass 应不可变")
    except AttributeError:
        pass  # 预期：frozen 不可变


# ---- viewer 不变量（PronounContext 三元组）----


def test_pronoun_service_signature_has_viewer() -> None:
    """PronounService 函数签名含 viewer 参数（ADR-0021 B 类启动期校验）。"""
    for fn in (PronounService.can_see, PronounService.relation, visible):
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        # visible(viewer, target, world) 或 PronounService.relation(world, viewer, target)
        assert "viewer" in params, f"{fn.__qualname__} 缺 viewer 参数: {params}"


def test_visible_requires_viewer_param() -> None:
    """visible(viewer, target, world) 签名含 viewer（PronounContext 不变量）。"""
    sig = inspect.signature(visible)
    assert "viewer" in sig.parameters
    assert "target" in sig.parameters
    assert "world" in sig.parameters


def test_system_context_has_actor_target_only() -> None:
    """SystemContext 只含 actor/target，无 source/capability_token（ADR-0021 C 类）。"""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(SystemContext)}
    assert "actor" in fields
    assert "target" in fields
    # System 无"调用源"概念，无 source/capability_token
    assert "source" not in fields
    assert "capability_token" not in fields


def test_system_context_for_actor() -> None:
    """SystemContext.for_actor 构造无目标上下文（System tick 用）。"""
    ctx = SystemContext.for_actor(42)
    assert ctx.actor == 42
    assert ctx.target is None


# ---- 映射表覆盖 9 层规格典型调用点 ----


def test_map_covers_lpc_typical_call_sites() -> None:
    """映射表覆盖 9 层规格涉及的 LPC 典型调用点（收敛优先于完备，不穷尽 155 处）。"""
    lpc_funcs = {e.lpc_func for e in PREVIOUS_OBJECT_MAP}
    # 核心调用点（force_me/disable_player/set_status/visible/heart_beat/do_attack）
    expected = {"force_me", "disable_player", "set_status", "visible", "heart_beat", "do_attack"}
    assert expected <= lpc_funcs, f"缺调用点: {expected - lpc_funcs}"


def test_map_covers_lpc_files() -> None:
    """映射表覆盖关键 LPC 源文件。"""
    lpc_files = {e.lpc_file for e in PREVIOUS_OBJECT_MAP}
    assert "feature/command.c" in lpc_files
    assert "adm/daemons/securityd.c" in lpc_files
    assert "inherit/char/char.c" in lpc_files
    assert "adm/daemons/rankd.c" in lpc_files


def test_category_counts_sum() -> None:
    """各类别条目数之和 == 总条目数。"""
    counts = category_counts()
    assert sum(counts.values()) == len(PREVIOUS_OBJECT_MAP)
    # A 类约 60 处的典型代表（映射表覆盖 >= 4）
    assert counts[PreviousObjectCategory.A_COMMAND] >= 4
    # B 类约 40 处的典型代表（>= 3）
    assert counts[PreviousObjectCategory.B_PRONOUN] >= 3
    # C 类约 55 处的典型代表（>= 2）
    assert counts[PreviousObjectCategory.C_SYSTEM] >= 2
