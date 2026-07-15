"""层 H：核心守护进程 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="H"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 5 个守护进程都有函数规格（lpc_files 完整性）
- valid_cmd 的后置条件含返回值语义（1=允许 0=拒绝）
- LOGIN_D 状态机阶段数
- SECURITY_D 权限模型不变量
- NATURE_D 时间系统不变量
- CHINESE_D 无随机性
- hypothesis 属性测试（路径 A）：4 类属性验证规格模型自身一致性
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_h_daemons import (
    LAYER_SPEC,
    LoginState,
    WizLevel,
)

# ---------------------------------------------------------------------------
# smoke 测试
# ---------------------------------------------------------------------------


class TestSmoke:
    """LAYER_SPEC 基本可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id(self) -> None:
        assert LAYER_SPEC.layer_id == "H"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "核心守护进程"

    def test_lpc_files_complete(self) -> None:
        """6 个 LPC 文件都在 lpc_files 中（含 ADR-0028 新增的 rankd.c）。"""
        assert "adm/daemons/logind.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/chard.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/securityd.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/natured.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/chinesed.c" in LAYER_SPEC.lpc_files
        assert "adm/daemons/rankd.c" in LAYER_SPEC.lpc_files
        assert len(LAYER_SPEC.lpc_files) == 6

    def test_function_specs_nonempty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_spec_count(self) -> None:
        """应有 33 个 FunctionSpec（26 + RANK_D 7，ADR-0028 决策 7）。"""
        assert len(LAYER_SPEC.function_specs) == 33

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# 结构属性测试（保留函数名唯一性和期望函数名列表等层 H 特有断言）
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的结构完整性。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_expected_function_names(self, all_specs: list[FunctionSpec]) -> None:
        names = {spec.signature.name for spec in all_specs}
        expected = {
            # LOGIN_D
            "logon",
            "get_id",
            "get_passwd",
            "make_body",
            "enter_world",
            "reconnect",
            "check_legal_id",
            "check_legal_name",
            "random_gift",
            "init_new_player",
            # CHAR_D
            "setup_char",
            "break_relation",
            # SECURITY_D
            "valid_cmd",
            "valid_write",
            "valid_read",
            "get_status",
            "valid_wiz_login",
            "set_status",
            # NATURE_D
            "update_day_phase",
            "event_sunrise",
            "event_common",
            "init_day_phase",
            "game_time",
            # CHINESE_D
            "chinese_number",
            "chinese_date",
            "chinese",
            # RANK_D（ADR-0028 决策 7，rankd.c:8-651）
            "query_rank",
            "query_respect",
            "query_rude",
            "query_self",
            "query_self_rude",
            "query_close",
            "query_self_close",
        }
        assert names == expected, f"函数名不匹配: {names ^ expected}"


# ---------------------------------------------------------------------------
# 5 个守护进程函数分布测试
# ---------------------------------------------------------------------------


class TestDaemonCoverage:
    """每个守护进程都有足够的函数规格。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_login_d_functions(self, all_specs: list[FunctionSpec]) -> None:
        """LOGIN_D 有 10 个函数规格。"""
        login_funcs = [
            s for s in all_specs if s.signature.lpc_file == "adm/daemons/logind.c"
        ]
        assert len(login_funcs) == 10

    def test_char_d_functions(self, all_specs: list[FunctionSpec]) -> None:
        """CHAR_D 有 2 个函数规格（setup_char + break_relation）。"""
        char_funcs = [
            s for s in all_specs if s.signature.lpc_file == "adm/daemons/chard.c"
        ]
        assert len(char_funcs) == 2

    def test_security_d_functions(self, all_specs: list[FunctionSpec]) -> None:
        """SECURITY_D 有 6 个函数规格。"""
        sec_funcs = [
            s for s in all_specs if s.signature.lpc_file == "adm/daemons/securityd.c"
        ]
        assert len(sec_funcs) == 6

    def test_nature_d_functions(self, all_specs: list[FunctionSpec]) -> None:
        """NATURE_D 有 5 个函数规格。"""
        nature_funcs = [
            s for s in all_specs if s.signature.lpc_file == "adm/daemons/natured.c"
        ]
        assert len(nature_funcs) == 5

    def test_chinese_d_functions(self, all_specs: list[FunctionSpec]) -> None:
        """CHINESE_D 有 3 个函数规格。"""
        chinese_funcs = [
            s for s in all_specs if s.signature.lpc_file == "adm/daemons/chinesed.c"
        ]
        assert len(chinese_funcs) == 3


# ---------------------------------------------------------------------------
# valid_cmd 测试
# ---------------------------------------------------------------------------


class TestValidCmd:
    """valid_cmd 的后置条件含返回值语义（1=允许 0=拒绝）。"""

    @pytest.fixture
    def valid_cmd(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "valid_cmd"
        )

    def test_return_value_semantics(self, valid_cmd: FunctionSpec) -> None:
        """valid_cmd 后置条件含 '1=允许, 0=拒绝' 返回值语义。"""
        rv_postconds = [
            pc for pc in valid_cmd.postconditions if pc.return_value is not None
        ]
        assert len(rv_postconds) > 0
        rv_text = " ".join(pc.return_value or "" for pc in rv_postconds)
        assert "1" in rv_text and "0" in rv_text
        assert "允许" in rv_text or "拒绝" in rv_text

    def test_has_fail_closed_invariant(self, valid_cmd: FunctionSpec) -> None:
        """valid_cmd 有 fail-closed 不变量。"""
        assert any(
            "fail-closed" in inv.description.lower()
            or "fail-closed" in (inv.lpc_expr or "").lower()
            for inv in valid_cmd.invariants
        )

    def test_has_exclude_before_authorized_invariant(self, valid_cmd: FunctionSpec) -> None:
        """valid_cmd 有 exclude 优先于 authorized 的不变量。"""
        assert any(
            "exclude" in inv.description.lower() and "authorized" in inv.description.lower()
            for inv in valid_cmd.invariants
        )

    def test_has_command_hook_invariant(self, valid_cmd: FunctionSpec) -> None:
        """valid_cmd 有被 command_hook 调用的系统级不变量。"""
        assert any(
            "command_hook" in inv.description.lower()
            or "command_hook" in (inv.lpc_expr or "").lower()
            for inv in valid_cmd.invariants
        )

    def test_has_cmd_dirs_postcondition(self, valid_cmd: FunctionSpec) -> None:
        """valid_cmd 有 cmds/std/skill/usr 对所有玩家开放的后置条件。"""
        postcond_text = " ".join(
            pc.description for pc in valid_cmd.postconditions
        )
        assert "cmds/std" in postcond_text or "cmds/skill" in postcond_text

    def test_has_log_side_effect(self, valid_cmd: FunctionSpec) -> None:
        """valid_cmd 有 CMD_LOG 日志副作用。"""
        assert any(
            "CMD_LOG" in (se.lpc_call or "") or "CMD_LOG" in se.description
            for se in valid_cmd.side_effects
        )


# ---------------------------------------------------------------------------
# LOGIN_D 状态机测试
# ---------------------------------------------------------------------------


class TestLoginStateMachine:
    """LOGIN_D 状态机完整性测试。"""

    def test_login_state_enum_count(self) -> None:
        """LoginState 枚举有 13 个状态。"""
        states = list(LoginState)
        assert len(states) == 13

    def test_login_state_values(self) -> None:
        """LoginState 枚举值正确。"""
        assert LoginState.LOGON == "logon"
        assert LoginState.GET_ID == "get_id"
        assert LoginState.GET_PASSWD == "get_passwd"
        assert LoginState.ENTER_WORLD == "enter_world"
        assert LoginState.RECONNECT == "reconnect"

    def test_logon_is_entry_point(self) -> None:
        """logon 是连接入口函数。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "logon"
        )
        assert any(
            "入口" in inv.description for inv in spec.invariants
        )

    def test_enter_world_is_final_step(self) -> None:
        """enter_world 是进入游戏世界的最终步骤。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "enter_world"
        )
        assert any(
            "exec" in (se.lpc_call or "") for se in spec.side_effects
        )
        assert any(
            "setup" in (se.lpc_call or "") for se in spec.side_effects
        )

    def test_get_id_has_branch_invariant(self) -> None:
        """get_id 有存档存在性分支不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "get_id"
        )
        assert len(spec.postconditions) >= 3

    def test_random_gift_has_invariants(self) -> None:
        """random_gift 有天赋总和恒等不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "random_gift"
        )
        assert any(
            "100" in inv.description for inv in spec.invariants
        )
        assert any(
            "60" in inv.description for inv in spec.invariants
        )

    def test_random_gift_has_random_specs(self) -> None:
        """random_gift 有随机性规格。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "random_gift"
        )
        assert len(spec.random_specs) >= 1


# ---------------------------------------------------------------------------
# SECURITY_D 权限模型测试
# ---------------------------------------------------------------------------


class TestSecurityModel:
    """SECURITY_D 权限模型测试。"""

    def test_wiz_level_enum_count(self) -> None:
        """WizLevel 枚举有 10 级。"""
        levels = list(WizLevel)
        assert len(levels) == 10

    def test_wiz_level_values(self) -> None:
        """WizLevel 枚举值正确。"""
        assert WizLevel.PLAYER == "(player)"
        assert WizLevel.ADMIN == "(admin)"
        assert WizLevel.WIZARD == "(wizard)"
        assert WizLevel.ARCH == "(arch)"

    def test_valid_write_has_exclude_before_trusted(self) -> None:
        """valid_write 有 exclude 优先于 trusted 不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "valid_write"
        )
        assert any(
            "exclude" in inv.description.lower() and "trusted" in inv.description.lower()
            for inv in spec.invariants
        )

    def test_valid_read_has_public_dirs(self) -> None:
        """valid_read 有公共可读目录不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "valid_read"
        )
        assert any(
            "/data/" in inv.description or "/log/" in inv.description
            for inv in spec.invariants
        )

    def test_get_status_default_player(self) -> None:
        """get_status 未知 uid 默认返回 (player)。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "get_status"
        )
        assert any(
            "(player)" in pc.description and "默认" in pc.description
            for pc in spec.postconditions
        )

    def test_set_status_requires_root(self) -> None:
        """set_status 有 ROOT_UID 前置条件。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "set_status"
        )
        assert any(
            "ROOT_UID" in (pre.lpc_expr or "") or "ROOT_UID" in pre.description
            for pre in spec.preconditions
        )


# ---------------------------------------------------------------------------
# NATURE_D 时间系统测试
# ---------------------------------------------------------------------------


class TestNatureTimeSystem:
    """NATURE_D 时间系统测试。"""

    def test_update_day_phase_has_8_phases(self) -> None:
        """update_day_phase 有 8 阶段循环不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "update_day_phase"
        )
        assert any(
            "8" in inv.description and "阶段" in inv.description
            for inv in spec.invariants
        )

    def test_update_day_phase_has_time_scale(self) -> None:
        """update_day_phase 有真实 1 秒 = 游戏 1 分钟不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "update_day_phase"
        )
        assert any(
            "1 秒" in inv.description and "1 分钟" in inv.description
            for inv in spec.invariants
        )

    def test_event_sunrise_has_save_side_effects(self) -> None:
        """event_sunrise 有 PERSISTENCE 副作用（自动保存）。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "event_sunrise"
        )
        persistence_effects = [
            se for se in spec.side_effects if se.kind == SideEffectType.PERSISTENCE
        ]
        assert len(persistence_effects) >= 2  # link_ob save + body save

    def test_event_sunrise_has_crash_safety_invariant(self) -> None:
        """event_sunrise 有 JSON 存档崩溃安全不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "event_sunrise"
        )
        assert any(
            "崩溃安全" in inv.description or "原子写" in inv.description
            for inv in spec.invariants
        )

    def test_event_common_has_destruct_side_effect(self) -> None:
        """event_common 有 OBJECT_LIFECYCLE 副作用（清理无环境对象）。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "event_common"
        )
        assert any(
            se.kind == SideEffectType.OBJECT_LIFECYCLE
            for se in spec.side_effects
        )

    def test_game_time_delegates_to_chinese_d(self) -> None:
        """game_time 委托 CHINESE_D->chinese_date。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "game_time"
        )
        assert any(
            "CHINESE_D" in (se.lpc_call or "")
            for se in spec.side_effects
        )


# ---------------------------------------------------------------------------
# CHINESE_D 测试
# ---------------------------------------------------------------------------


class TestChineseD:
    """CHINESE_D 确定性映射函数测试。"""

    def test_chinese_number_no_random(self) -> None:
        """chinese_number 无随机性规格。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "chinese_number"
        )
        assert len(spec.random_specs) == 0

    def test_chinese_number_has_no_random_invariant(self) -> None:
        """chinese_number 有无随机性不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "chinese_number"
        )
        assert any(
            "无随机性" in inv.description or "no random" in inv.description.lower()
            for inv in spec.invariants
        )

    def test_chinese_date_no_random(self) -> None:
        """chinese_date 无随机性规格。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "chinese_date"
        )
        assert len(spec.random_specs) == 0

    def test_chinese_date_has_ganzhi_invariant(self) -> None:
        """chinese_date 有天干地支不变量。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "chinese_date"
        )
        assert any(
            "天干" in inv.description and "地支" in inv.description
            for inv in spec.invariants
        )


# ---------------------------------------------------------------------------
# CHAR_D 测试
# ---------------------------------------------------------------------------


class TestCharD:
    """CHAR_D setup_char 角色初始化测试。"""

    @pytest.fixture
    def setup_char(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "setup_char"
        )

    def test_has_race_dispatch_postcondition(self, setup_char: FunctionSpec) -> None:
        """setup_char 有种族分派后置条件。"""
        assert any(
            "种族" in pc.description for pc in setup_char.postconditions
        )

    def test_has_attribute_clamp_postcondition(self, setup_char: FunctionSpec) -> None:
        """setup_char 有属性钳位后置条件。"""
        postcond_text = " ".join(
            pc.description for pc in setup_char.postconditions
        )
        assert "钳位" in postcond_text or "eff_jing" in postcond_text

    def test_has_jing_qi_hierarchy_invariant(self, setup_char: FunctionSpec) -> None:
        """setup_char 有 jing <= eff_jing <= max_jing 层次不变量。"""
        assert any(
            "eff_jing" in inv.description and "max_jing" in inv.description
            for inv in setup_char.invariants
        )

    def test_has_reset_action_side_effect(self, setup_char: FunctionSpec) -> None:
        """setup_char 有 reset_action 副作用。"""
        assert any(
            "reset_action" in (se.lpc_call or "") or "reset_action" in se.description
            for se in setup_char.side_effects
        )

    def test_break_relation_has_huashan_invariant(self) -> None:
        """break_relation 仅处理华山派。"""
        spec = next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "break_relation"
        )
        assert any(
            "华山" in inv.description for inv in spec.invariants
        )


# ---------------------------------------------------------------------------
# 层级规格测试
# ---------------------------------------------------------------------------


class TestLayerNotes:
    """层规格的 notes 覆盖关键信息。"""

    def test_notes_mention_five_daemons(self) -> None:
        """notes 中提到 5 个守护进程。"""
        assert LAYER_SPEC.notes is not None
        assert "LOGIN_D" in LAYER_SPEC.notes
        assert "CHAR_D" in LAYER_SPEC.notes
        assert "SECURITY_D" in LAYER_SPEC.notes
        assert "NATURE_D" in LAYER_SPEC.notes
        assert "CHINESE_D" in LAYER_SPEC.notes

    def test_notes_mention_fail_closed(self) -> None:
        """notes 中提到 fail-closed。"""
        assert LAYER_SPEC.notes is not None
        assert "fail-closed" in LAYER_SPEC.notes.lower()

    def test_notes_mention_time_system(self) -> None:
        """notes 中提到时间系统（1 秒 = 1 分钟）。"""
        assert LAYER_SPEC.notes is not None
        assert "1 秒" in LAYER_SPEC.notes and "1 分钟" in LAYER_SPEC.notes

    def test_notes_mention_crash_safety(self) -> None:
        """notes 中提到存档崩溃安全。"""
        assert LAYER_SPEC.notes is not None
        assert "崩溃安全" in LAYER_SPEC.notes or "原子写" in LAYER_SPEC.notes

    def test_cross_layer_refs_include_command_hook(self) -> None:
        """跨层引用包含 command_hook（层 C）。"""
        refs = " ".join(LAYER_SPEC.cross_layer_refs)
        assert "command_hook" in refs or "层 C" in refs

    def test_cross_layer_refs_include_setup(self) -> None:
        """跨层引用包含 setup（层 G）。"""
        refs = " ".join(LAYER_SPEC.cross_layer_refs)
        assert "setup" in refs or "层 G" in refs


# ---------------------------------------------------------------------------
# hypothesis 属性测试（路径 A）
#
# 4 类属性：随机函数索引 / 副作用子集 / random_specs 完整性 / invariants-side_effects 对应
# 验证规格模型自身一致性，不依赖被测实现。
# ---------------------------------------------------------------------------

_N = len(LAYER_SPEC.function_specs) - 1


# ── 第 1 类：随机函数索引 ──────────────────────────────────────────────────

@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_spec_by_index_valid(idx: int) -> None:
    """属性：任意索引的 FunctionSpec 签名完整。"""
    spec = LAYER_SPEC.function_specs[idx]
    assert spec.signature.name
    assert spec.signature.return_type
    assert spec.signature.lpc_file


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_monotonic(idx: int) -> None:
    """属性：任意函数的副作用 order 严格递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = [se.order for se in spec.side_effects]
        assert orders == sorted(orders), (
            f"{spec.signature.name}: side_effect order 非递增"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_order_consecutive_from_one(idx: int) -> None:
    """属性：任意函数的副作用 order 从 1 连续递增。"""
    spec = LAYER_SPEC.function_specs[idx]
    if spec.side_effects:
        orders = sorted(se.order for se in spec.side_effects)
        expected = list(range(1, len(orders) + 1))
        assert orders == expected, (
            f"{spec.signature.name}: order 不连续: {orders}"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_side_effect_kind_and_description_nonempty(idx: int) -> None:
    """属性：任意副作用 kind/description 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for se in spec.side_effects:
        assert se.kind is not None, (
            f"{spec.signature.name}: order={se.order} kind 为空"
        )
        assert se.description, (
            f"{spec.signature.name}: order={se.order} description 为空"
        )


@given(idx=st.integers(min_value=0, max_value=_N))
def test_function_has_post_conditions(idx: int) -> None:
    """属性：任意函数至少有一个后置条件。

    层 H 部分函数（chinese_number/check_legal_name 等）无前置条件，
    故仅断言后置条件存在。
    """
    spec = LAYER_SPEC.function_specs[idx]
    assert len(spec.postconditions) > 0, f"{spec.signature.name}: 无后置条件"


# ── 第 2 类：副作用子集 ────────────────────────────────────────────────────

@st.composite
def _spec_with_subset(draw: st.DrawFn) -> tuple[FunctionSpec, list]:
    """生成 (函数, 非空副作用子集)，子集保持原顺序。"""
    specs_with_se = [s for s in LAYER_SPEC.function_specs if s.side_effects]
    spec = draw(st.sampled_from(specs_with_se))
    n = len(spec.side_effects)
    indices = draw(
        st.lists(st.integers(0, n - 1), min_size=1, max_size=n, unique=True)
    )
    subset = [spec.side_effects[i] for i in sorted(indices)]
    return spec, subset


@given(data=_spec_with_subset())
def test_side_effect_subset_order_preserved(
    data: tuple[FunctionSpec, list],
) -> None:
    """属性：任意函数副作用的随机子集，order 仍递增（子集保有序性）。"""
    spec, subset = data
    orders = [se.order for se in subset]
    assert orders == sorted(orders), (
        f"{spec.signature.name}: 子集 order 非递增: {orders}"
    )


# ── 第 3 类：random_specs 完整性 ───────────────────────────────────────────
# 层 H 有 4 个 random_specs（random_gift 2 个 + event_common 1 个 + query_close 1 个）。

@given(idx=st.integers(min_value=0, max_value=_N))
def test_random_specs_fields_nonempty(idx: int) -> None:
    """属性：任意有 random_specs 的函数，每个 random_spec 的
    probability_model/semantic/lpc_call 非空。"""
    spec = LAYER_SPEC.function_specs[idx]
    for rs in spec.random_specs:
        assert rs.probability_model, (
            f"{spec.signature.name}: random_spec probability_model 为空"
        )
        assert rs.semantic, (
            f"{spec.signature.name}: random_spec semantic 为空"
        )
        assert rs.lpc_call, (
            f"{spec.signature.name}: random_spec lpc_call 为空"
        )


# ── 第 4 类：invariants-side_effects 对应 ──────────────────────────────────

@given(idx=st.integers(min_value=0, max_value=_N))
def test_state_invariant_implies_state_mutation(idx: int) -> None:
    """属性：不变量提到状态/qi/state/状态/eff_/max_/jing/neili 的函数，
    副作用含 STATE_MUTATION。"""
    spec = LAYER_SPEC.function_specs[idx]
    state_keywords = ("qi", "state", "状态", "eff_", "max_", "jing", "neili")
    has_state_invariant = any(
        any(kw in inv.description.lower() or kw in (inv.lpc_expr or "").lower()
            for kw in state_keywords)
        for inv in spec.invariants
    )
    if has_state_invariant and spec.side_effects:
        kinds = {se.kind for se in spec.side_effects}
        assert SideEffectType.STATE_MUTATION in kinds, (
            f"{spec.signature.name}: 有状态不变量但无 STATE_MUTATION 副作用"
        )
