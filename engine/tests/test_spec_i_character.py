"""层 I：角色与登录 -- 规格提取测试。

测试内容：
- smoke：LAYER_SPEC 可加载、layer_id=="I"、function_specs 非空
- 结构属性：每个 FunctionSpec 签名完整
- 副作用 order 唯一且递增
- save 和 visible 都有规格
- cross_layer_refs 引用了层 H（LOGIN_D）和层 G（heart_beat）
"""

from __future__ import annotations

import pytest

from xkx.spec.base import FunctionSpec, LayerSpec, SideEffectType
from xkx.spec.layer_i_character import LAYER_SPEC, CharacterLifecycle

# ---------------------------------------------------------------------------
# smoke 测试
# ---------------------------------------------------------------------------


class TestSmoke:
    """LAYER_SPEC 基本可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id(self) -> None:
        assert LAYER_SPEC.layer_id == "I"

    def test_layer_name(self) -> None:
        assert LAYER_SPEC.layer_name == "角色与登录"

    def test_lpc_files(self) -> None:
        assert "inherit/char/char.c" in LAYER_SPEC.lpc_files
        assert "clone/user/user.c" in LAYER_SPEC.lpc_files
        assert "clone/user/login.c" in LAYER_SPEC.lpc_files

    def test_function_specs_nonempty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_function_spec_count(self) -> None:
        """应有 18 个 FunctionSpec：char.c 4 + user.c 9 + login.c 5。"""
        assert len(LAYER_SPEC.function_specs) == 18

    def test_cross_layer_refs_nonempty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ---------------------------------------------------------------------------
# 结构属性测试
# ---------------------------------------------------------------------------


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的结构完整性。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_signatures_have_name(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.name, f"函数名不能为空: {spec}"

    def test_all_signatures_have_return_type(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            assert spec.signature.return_type, (
                f"返回类型不能为空: {spec.signature.name}"
            )

    def test_all_signatures_have_lpc_file(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            assert spec.signature.lpc_file, (
                f"lpc_file 不能为空: {spec.signature.name}"
            )

    def test_all_specs_have_preconditions(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            assert len(spec.preconditions) > 0, (
                f"应至少有一个前置条件: {spec.signature.name}"
            )

    def test_all_specs_have_side_effects(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            assert len(spec.side_effects) > 0, (
                f"应至少有一个副作用: {spec.signature.name}"
            )

    def test_expected_function_names(self, all_specs: list[FunctionSpec]) -> None:
        names = {spec.signature.name for spec in all_specs}
        expected = {
            # char.c
            "create",
            "setup",
            "heart_beat",
            "visible",
            # user.c
            "save",
            "update_age",
            "restore_autoload",
            "net_dead",
            "reconnect",
            "user_dump",
            "reset",
            # login.c
            "logon",
            "time_out",
            "receive_message",
            "set",
        }
        # create / setup / net_dead 出现在多个文件中，names 是去重集合
        # 只检查关键函数都在
        for name in expected:
            assert name in names, f"缺少函数: {name}"


# ---------------------------------------------------------------------------
# 副作用 order 测试
# ---------------------------------------------------------------------------


class TestSideEffectOrder:
    """副作用 order 唯一且递增。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_order_unique_per_function(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            orders = [se.order for se in spec.side_effects]
            assert len(orders) == len(set(orders)), (
                f"副作用 order 不唯一: {spec.signature.name} orders={orders}"
            )

    def test_order_starts_from_1(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            orders = sorted(se.order for se in spec.side_effects)
            assert orders[0] == 1, (
                f"order 应从 1 开始: {spec.signature.name} first={orders[0]}"
            )

    def test_order_consecutive(self, all_specs: list[FunctionSpec]) -> None:
        """order 应连续递增（1, 2, 3, ... 无跳号）。"""
        for spec in all_specs:
            orders = sorted(se.order for se in spec.side_effects)
            expected = list(range(1, len(orders) + 1))
            assert orders == expected, (
                f"order 不连续: {spec.signature.name} orders={orders}"
            )


# ---------------------------------------------------------------------------
# save 规格测试
# ---------------------------------------------------------------------------


class TestSaveSpec:
    """user.c save() 玩家存档规格。"""

    @pytest.fixture
    def save_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "save" and "user.c" in s.signature.lpc_file
        )

    def test_save_has_specs(self, save_spec: FunctionSpec) -> None:
        assert save_spec is not None
        assert save_spec.signature.name == "save"

    def test_save_has_persistence(self, save_spec: FunctionSpec) -> None:
        """save 有持久化副作用。"""
        assert any(
            se.kind == SideEffectType.PERSISTENCE for se in save_spec.side_effects
        )

    def test_save_has_three_steps(self, save_spec: FunctionSpec) -> None:
        """save 有三步交织：save_autoload -> ::save -> clean_up_autoload。"""
        assert len(save_spec.side_effects) >= 3

    def test_save_has_atomic_write_invariant(
        self, save_spec: FunctionSpec
    ) -> None:
        """有原子写不变量（JSON 存档崩溃安全）。"""
        assert any(
            "原子" in inv.description
            or "atomic" in inv.description.lower()
            or "崩溃安全" in inv.description
            for inv in save_spec.invariants
        )

    def test_save_notes_mention_crash_safety(
        self, save_spec: FunctionSpec
    ) -> None:
        """notes 提到崩溃安全或原子写。"""
        assert save_spec.notes is not None
        assert "原子" in save_spec.notes or "崩溃安全" in save_spec.notes

    def test_save_ordering_invariant(self, save_spec: FunctionSpec) -> None:
        """有 save_autoload 在 ::save 之前的不变量。"""
        assert any(
            "save_autoload" in inv.description and "::save" in inv.description
            for inv in save_spec.invariants
        )


# ---------------------------------------------------------------------------
# visible 规格测试
# ---------------------------------------------------------------------------


class TestVisibleSpec:
    """char.c visible() 隐身/可见性判定规格。"""

    @pytest.fixture
    def visible_spec(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "visible"
        )

    def test_visible_has_specs(self, visible_spec: FunctionSpec) -> None:
        assert visible_spec is not None
        assert visible_spec.signature.name == "visible"

    def test_visible_has_viewer_target_invariant(
        self, visible_spec: FunctionSpec
    ) -> None:
        """有 viewer/target 语义不变量（PronounContext 必须携带 viewer）。"""
        assert any(
            "viewer" in inv.description and "target" in inv.description
            for inv in visible_spec.invariants
        )

    def test_visible_has_wiz_level_invariant(
        self, visible_spec: FunctionSpec
    ) -> None:
        """有巫师等级判定不变量。"""
        assert any(
            "巫师等级" in inv.description or "wiz_level" in (inv.lpc_expr or "")
            for inv in visible_spec.invariants
        )

    def test_visible_has_invisibility_invariant(
        self, visible_spec: FunctionSpec
    ) -> None:
        """有 invisibility 属性判定不变量。"""
        assert any(
            "invisibility" in inv.description.lower()
            or "invisibility" in (inv.lpc_expr or "").lower()
            for inv in visible_spec.invariants
        )

    def test_visible_has_ghost_invariant(
        self, visible_spec: FunctionSpec
    ) -> None:
        """有鬼魂可见性不变量。"""
        assert any(
            "鬼魂" in inv.description or "ghost" in inv.description.lower()
            for inv in visible_spec.invariants
        )

    def test_visible_notes_mention_pronoun_context(
        self, visible_spec: FunctionSpec
    ) -> None:
        """notes 提到 PronounContext 或 viewer 语义。"""
        assert visible_spec.notes is not None
        assert (
            "PronounContext" in visible_spec.notes
            or "viewer" in visible_spec.notes
        )


# ---------------------------------------------------------------------------
# cross_layer_refs 测试
# ---------------------------------------------------------------------------


class TestCrossLayerRefs:
    """跨层引用测试。"""

    @pytest.fixture
    def refs(self) -> list[str]:
        return LAYER_SPEC.cross_layer_refs

    def test_refs_mention_layer_h_login_d(self, refs: list[str]) -> None:
        """引用了层 H 的 LOGIN_D 状态机。"""
        assert any("LOGIN_D" in ref for ref in refs), (
            "cross_layer_refs 应引用 LOGIN_D（层 H）"
        )

    def test_refs_mention_layer_g_heart_beat(self, refs: list[str]) -> None:
        """引用了层 G 的 heart_beat 七步。"""
        assert any("heart_beat" in ref and "层 G" in ref for ref in refs), (
            "cross_layer_refs 应引用 heart_beat 七步（层 G）"
        )

    def test_refs_mention_layer_b_f_save(self, refs: list[str]) -> None:
        """引用了层 B 的 F_SAVE。"""
        assert any("F_SAVE" in ref or "save" in ref.lower() for ref in refs)

    def test_refs_mention_layer_a_driver(self, refs: list[str]) -> None:
        """引用了层 A 的 driver。"""
        assert any("层 A" in ref for ref in refs)

    def test_refs_mention_layer_c_command(self, refs: list[str]) -> None:
        """引用了层 C 的 command。"""
        assert any("层 C" in ref for ref in refs)

    def test_refs_mention_layer_f_death(self, refs: list[str]) -> None:
        """引用了层 F 的死亡轮回。"""
        assert any("层 F" in ref for ref in refs)

    def test_refs_mention_layer_h_nature_d(self, refs: list[str]) -> None:
        """引用了层 H 的 NATURE_D（时间系统）。"""
        assert any("NATURE_D" in ref for ref in refs)


# ---------------------------------------------------------------------------
# CharacterLifecycle 枚举测试
# ---------------------------------------------------------------------------


class TestCharacterLifecycleEnum:
    """CharacterLifecycle 枚举覆盖关键阶段。"""

    def test_has_create(self) -> None:
        assert CharacterLifecycle.CREATE == "create"

    def test_has_setup(self) -> None:
        assert CharacterLifecycle.SETUP == "setup"

    def test_has_active(self) -> None:
        assert CharacterLifecycle.ACTIVE == "active"

    def test_has_net_dead(self) -> None:
        assert CharacterLifecycle.NET_DEAD == "net_dead"

    def test_has_reconnect(self) -> None:
        assert CharacterLifecycle.RECONNECT == "reconnect"

    def test_count(self) -> None:
        assert len(list(CharacterLifecycle)) == 5


# ---------------------------------------------------------------------------
# char.c 函数测试
# ---------------------------------------------------------------------------


class TestCharCreate:
    """char.c create() 规格。"""

    @pytest.fixture
    def create_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "create" and "char.c" in s.signature.lpc_file
        )

    def test_has_seteuid_zero(self, create_spec: FunctionSpec) -> None:
        """create 有 seteuid(0) 副作用。"""
        assert any(
            "seteuid(0)" in (se.lpc_call or "") or "seteuid(0)" in se.description
            for se in create_spec.side_effects
        )


class TestCharSetup:
    """char.c setup() 规格。"""

    @pytest.fixture
    def setup_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "setup" and "char.c" in s.signature.lpc_file
        )

    def test_has_heart_beat_enable(self, setup_spec: FunctionSpec) -> None:
        """setup 有 set_heart_beat(1) 副作用。"""
        assert any(
            "set_heart_beat(1)" in (se.lpc_call or "")
            for se in setup_spec.side_effects
        )

    def test_has_enable_player(self, setup_spec: FunctionSpec) -> None:
        """setup 有 enable_player 副作用。"""
        assert any(
            "enable_player" in (se.lpc_call or "")
            or "enable_player" in se.description
            for se in setup_spec.side_effects
        )

    def test_has_setup_char(self, setup_spec: FunctionSpec) -> None:
        """setup 有 CHAR_D->setup_char 副作用。"""
        assert any(
            "setup_char" in (se.lpc_call or "") or "setup_char" in se.description
            for se in setup_spec.side_effects
        )


class TestHeartBeatSkeleton:
    """char.c heart_beat() 骨架规格。"""

    @pytest.fixture
    def heart_beat_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "heart_beat"
        )

    def test_has_player_npc_branch_invariant(
        self, heart_beat_spec: FunctionSpec
    ) -> None:
        """有玩家 vs NPC 分支不变量。"""
        assert any(
            "玩家" in inv.description and "NPC" in inv.description
            for inv in heart_beat_spec.invariants
        )

    def test_has_tick_invariant(self, heart_beat_spec: FunctionSpec) -> None:
        """有 tick=1s 不变量。"""
        assert any(
            "tick" in inv.description.lower()
            or "1s" in inv.description
            or "set_heart_beat(1)" in (inv.lpc_expr or "")
            for inv in heart_beat_spec.invariants
        )

    def test_has_update_age_side_effect(
        self, heart_beat_spec: FunctionSpec
    ) -> None:
        """有 update_age 副作用（玩家分支）。"""
        assert any(
            "update_age" in se.description or "update_age" in (se.lpc_call or "")
            for se in heart_beat_spec.side_effects
        )

    def test_has_idle_check_side_effect(
        self, heart_beat_spec: FunctionSpec
    ) -> None:
        """有 idle 超时检查副作用（玩家分支）。"""
        assert any(
            "idle" in se.description.lower()
            or "DUMP_IDLE" in (se.lpc_call or "")
            for se in heart_beat_spec.side_effects
        )


# ---------------------------------------------------------------------------
# user.c 函数测试
# ---------------------------------------------------------------------------


class TestUserSetup:
    """user.c setup() 规格。"""

    @pytest.fixture
    def setup_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "setup" and "user.c" in s.signature.lpc_file
        )

    def test_has_three_step_invariant(self, setup_spec: FunctionSpec) -> None:
        """有三步交织不变量。"""
        assert any(
            "三步" in inv.description or "update_age" in inv.description
            for inv in setup_spec.invariants
        )

    def test_has_restore_autoload(self, setup_spec: FunctionSpec) -> None:
        """有 restore_autoload 副作用。"""
        assert any(
            "restore_autoload" in (se.lpc_call or "")
            or "restore_autoload" in se.description
            for se in setup_spec.side_effects
        )


class TestUpdateAge:
    """user.c update_age() 规格。"""

    @pytest.fixture
    def update_age_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "update_age"
        )

    def test_has_time_mapping_invariant(
        self, update_age_spec: FunctionSpec
    ) -> None:
        """有游戏时间映射不变量（真实 1 秒 = 游戏 1 分钟）。"""
        assert any(
            "86400" in inv.description
            or "86400" in (inv.lpc_expr or "")
            or "游戏" in inv.description
            for inv in update_age_spec.invariants
        )

    def test_has_age_base_14(self, update_age_spec: FunctionSpec) -> None:
        """有初始年龄 14 岁不变量。"""
        assert any(
            "14" in inv.description or "14" in (inv.lpc_expr or "")
            for inv in update_age_spec.invariants
        )

    def test_has_slow_aging_invariant(
        self, update_age_spec: FunctionSpec
    ) -> None:
        """有 24 岁后衰老减速不变量。"""
        assert any(
            "24" in inv.description or "减速" in inv.description
            for inv in update_age_spec.invariants
        )

    def test_has_mud_age_side_effect(
        self, update_age_spec: FunctionSpec
    ) -> None:
        """有 mud_age 累加副作用。"""
        assert any(
            "mud_age" in se.description or "mud_age" in (se.lpc_call or "")
            for se in update_age_spec.side_effects
        )


class TestNetDead:
    """user.c net_dead() 规格。"""

    @pytest.fixture
    def net_dead_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "net_dead" and "user.c" in s.signature.lpc_file
        )

    def test_has_heart_beat_off(self, net_dead_spec: FunctionSpec) -> None:
        """net_dead 有 set_heart_beat(0) 副作用。"""
        assert any(
            "set_heart_beat(0)" in (se.lpc_call or "")
            for se in net_dead_spec.side_effects
        )

    def test_has_call_out(self, net_dead_spec: FunctionSpec) -> None:
        """net_dead 有 call_out 副作用（user_dump 定时器）。"""
        assert any(
            se.kind == SideEffectType.CALL_OUT for se in net_dead_spec.side_effects
        )


class TestReconnect:
    """user.c reconnect() 规格。"""

    @pytest.fixture
    def reconnect_spec(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "reconnect"
        )

    def test_has_heart_beat_on(self, reconnect_spec: FunctionSpec) -> None:
        """reconnect 有 set_heart_beat(1) 副作用。"""
        assert any(
            "set_heart_beat(1)" in (se.lpc_call or "")
            for se in reconnect_spec.side_effects
        )

    def test_has_remove_call_out(self, reconnect_spec: FunctionSpec) -> None:
        """reconnect 有 remove_call_out 副作用（取消 user_dump）。"""
        assert any(
            "remove_call_out" in (se.lpc_call or "")
            for se in reconnect_spec.side_effects
        )


# ---------------------------------------------------------------------------
# login.c 函数测试
# ---------------------------------------------------------------------------


class TestLoginLogon:
    """login.c logon() 规格。"""

    @pytest.fixture
    def logon_spec(self) -> FunctionSpec:
        return next(
            s for s in LAYER_SPEC.function_specs if s.signature.name == "logon"
        )

    def test_has_login_d_delegate(self, logon_spec: FunctionSpec) -> None:
        """logon 有 LOGIN_D->logon 委托副作用。"""
        assert any(
            "LOGIN_D" in (se.lpc_call or "") or "LOGIN_D" in se.description
            for se in logon_spec.side_effects
        )

    def test_has_call_out_timeout(self, logon_spec: FunctionSpec) -> None:
        """logon 有 call_out 超时副作用。"""
        assert any(
            se.kind == SideEffectType.CALL_OUT for se in logon_spec.side_effects
        )


class TestLoginSet:
    """login.c set() 安全防护规格。"""

    @pytest.fixture
    def set_spec(self) -> FunctionSpec:
        return next(
            s
            for s in LAYER_SPEC.function_specs
            if s.signature.name == "set" and "login.c" in s.signature.lpc_file
        )

    def test_has_root_uid_guard(self, set_spec: FunctionSpec) -> None:
        """set 有 ROOT_UID 前置守卫。"""
        assert any(
            "ROOT_UID" in pre.description or "ROOT_UID" in (pre.lpc_expr or "")
            for pre in set_spec.preconditions
        )

    def test_has_security_invariant(self, set_spec: FunctionSpec) -> None:
        """有安全防护不变量。"""
        assert any(
            "安全" in inv.description or "nomask" in inv.description
            or "ROOT" in inv.description
            for inv in set_spec.invariants
        )
