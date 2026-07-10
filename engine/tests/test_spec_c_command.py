"""层 C 命令系统规格测试。

验证 LAYER_SPEC 结构完整性和方向别名映射正确性。
"""

from __future__ import annotations

import pytest

from xkx.spec.base import FunctionSpec, LayerSpec
from xkx.spec.layer_c_command import (
    COMMAND_OBJECTS,
    COMMAND_PATHS,
    DIRECTION_ALIASES,
    LAYER_SPEC,
    NON_DIRECTION_ALIASES,
    CommandHookBranch,
)

# ── smoke 测试 ────────────────────────────────────────────────────────


class TestLayerSpecSmoke:
    """LAYER_SPEC 基础可加载性。"""

    def test_layer_spec_loadable(self) -> None:
        assert LAYER_SPEC is not None
        assert isinstance(LAYER_SPEC, LayerSpec)

    def test_layer_id_is_c(self) -> None:
        assert LAYER_SPEC.layer_id == "C"

    def test_layer_name_is_command(self) -> None:
        assert LAYER_SPEC.layer_name == "命令系统"

    def test_function_specs_non_empty(self) -> None:
        assert len(LAYER_SPEC.function_specs) > 0

    def test_lpc_files_listed(self) -> None:
        expected_files = {
            "feature/command.c",
            "feature/alias.c",
            "adm/daemons/commandd.c",
            "adm/daemons/aliasd.c",
            "include/command.h",
        }
        assert set(LAYER_SPEC.lpc_files) == expected_files

    def test_cross_layer_refs_non_empty(self) -> None:
        assert len(LAYER_SPEC.cross_layer_refs) > 0


# ── FunctionSpec 结构属性 ─────────────────────────────────────────────


class TestFunctionSpecStructure:
    """每个 FunctionSpec 的结构完整性。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_all_specs_have_name(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.name, f"FunctionSpec 缺少 name: {spec}"

    def test_all_specs_have_return_type(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.return_type, f"{spec.signature.name} 缺少 return_type"

    def test_all_specs_have_lpc_file(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.lpc_file, f"{spec.signature.name} 缺少 lpc_file"

    def test_all_specs_have_line_range(self, all_specs: list[FunctionSpec]) -> None:
        for spec in all_specs:
            assert spec.signature.line_range is not None, (
                f"{spec.signature.name} 缺少 line_range"
            )

    def test_expected_function_count(self, all_specs: list[FunctionSpec]) -> None:
        assert len(all_specs) == 10

    def test_expected_function_names(self, all_specs: list[FunctionSpec]) -> None:
        names = {spec.signature.name for spec in all_specs}
        expected = {
            "command_hook",
            "enable_player",
            "disable_player",
            "process_input",
            "find_command",  # 两个同名（commandd.c + command.c wrapper）
            "rehash",
            "process_global_alias",
            "force_me",
            "set_alias",
        }
        assert expected.issubset(names), f"缺少函数: {expected - names}"

    def test_command_hook_has_four_branches_in_notes(self, all_specs: list[FunctionSpec]) -> None:
        hook_spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert hook_spec.notes is not None
        assert "四分支" in hook_spec.notes or "分支" in hook_spec.notes


# ── 副作用 order 唯一且递增 ───────────────────────────────────────────


class TestSideEffectOrdering:
    """每个 FunctionSpec 的副作用 order 唯一且递增。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_side_effect_orders_unique_and_ascending(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            orders = [se.order for se in spec.side_effects]
            if not orders:
                continue
            assert orders == sorted(orders), (
                f"{spec.signature.name} 副作用 order 不递增: {orders}"
            )
            assert len(orders) == len(set(orders)), (
                f"{spec.signature.name} 副作用 order 有重复: {orders}"
            )

    def test_side_effect_orders_start_from_1(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        for spec in all_specs:
            if spec.side_effects:
                assert spec.side_effects[0].order == 1, (
                    f"{spec.signature.name} 首个副作用 order != 1"
                )


# ── 方向别名映射 ─────────────────────────────────────────────────────


class TestDirectionAliases:
    """DIRECTION_ALIASES 关键映射验证。"""

    def test_n_to_north(self) -> None:
        assert DIRECTION_ALIASES["n"] == "go north"

    def test_s_to_south(self) -> None:
        assert DIRECTION_ALIASES["s"] == "go south"

    def test_e_to_east(self) -> None:
        assert DIRECTION_ALIASES["e"] == "go east"

    def test_w_to_west(self) -> None:
        assert DIRECTION_ALIASES["w"] == "go west"

    def test_u_to_up(self) -> None:
        assert DIRECTION_ALIASES["u"] == "go up"

    def test_d_to_down(self) -> None:
        assert DIRECTION_ALIASES["d"] == "go down"

    def test_diagonal_directions(self) -> None:
        assert DIRECTION_ALIASES["ne"] == "go northeast"
        assert DIRECTION_ALIASES["nw"] == "go northwest"
        assert DIRECTION_ALIASES["se"] == "go southeast"
        assert DIRECTION_ALIASES["sw"] == "go southwest"

    def test_up_down_directions(self) -> None:
        assert DIRECTION_ALIASES["nu"] == "go northup"
        assert DIRECTION_ALIASES["su"] == "go southup"
        assert DIRECTION_ALIASES["eu"] == "go eastup"
        assert DIRECTION_ALIASES["wu"] == "go westup"
        assert DIRECTION_ALIASES["nd"] == "go northdown"
        assert DIRECTION_ALIASES["sd"] == "go southdown"
        assert DIRECTION_ALIASES["ed"] == "go eastdown"
        assert DIRECTION_ALIASES["wd"] == "go westdown"

    def test_direction_alias_count(self) -> None:
        """方向别名共 18 个（8 基本 + 4 对角 + 4 上坡 + 4 下坡 + u/d）。"""
        assert len(DIRECTION_ALIASES) == 18

    def test_all_values_prefixed_with_go(self) -> None:
        for key, value in DIRECTION_ALIASES.items():
            assert value.startswith("go "), f"{key} -> {value} 不是 go 前缀"

    def test_non_direction_aliases(self) -> None:
        assert NON_DIRECTION_ALIASES["l"] == "look"
        assert NON_DIRECTION_ALIASES["i"] == "inventory"


# ── 命令路径常量 ──────────────────────────────────────────────────────


class TestCommandPaths:
    """COMMAND_PATHS 常量验证。"""

    def test_plr_path(self) -> None:
        assert COMMAND_PATHS["PLR_PATH"] == ["/cmds/std/", "/cmds/usr/", "/cmds/skill/"]

    def test_npc_path(self) -> None:
        assert COMMAND_PATHS["NPC_PATH"] == ["/cmds/std/", "/cmds/skill/"]

    def test_unr_path(self) -> None:
        assert COMMAND_PATHS["UNR_PATH"] == ["/cmds/usr/", "/cmds/std/"]

    def test_adm_path_includes_all(self) -> None:
        adm = COMMAND_PATHS["ADM_PATH"]
        assert "/cmds/adm/" in adm
        assert "/cmds/std/" in adm
        assert "/cmds/skill/" in adm

    def test_all_paths_end_with_slash(self) -> None:
        for path_name, dirs in COMMAND_PATHS.items():
            for d in dirs:
                assert d.endswith("/"), f"{path_name} 中的 {d} 不以 / 结尾"


class TestCommandObjects:
    """COMMAND_OBJECTS 常量验证。"""

    def test_go_cmd(self) -> None:
        assert COMMAND_OBJECTS["GO_CMD"] == "/cmds/std/go"

    def test_kill_cmd(self) -> None:
        assert COMMAND_OBJECTS["KILL_CMD"] == "/cmds/std/kill"

    def test_all_objects_under_cmds(self) -> None:
        for name, path in COMMAND_OBJECTS.items():
            assert path.startswith("/cmds/"), f"{name} -> {path} 不在 /cmds/ 下"


# ── CommandHookBranch 枚举 ────────────────────────────────────────────


class TestCommandHookBranch:
    """四分支枚举验证。"""

    def test_four_branches(self) -> None:
        assert len(CommandHookBranch) == 4

    def test_branch_values(self) -> None:
        assert CommandHookBranch.DIRECTION_SHORTCUT == "direction_shortcut"
        assert CommandHookBranch.NORMAL_COMMAND == "normal_command"
        assert CommandHookBranch.EMOTE == "emote"
        assert CommandHookBranch.CHANNEL == "channel"


# ── 前置/后置条件/不变量非空 ─────────────────────────────────────────


class TestSpecCompleteness:
    """核心函数的六要素完整性。"""

    @pytest.fixture
    def all_specs(self) -> list[FunctionSpec]:
        return LAYER_SPEC.function_specs

    def test_command_hook_has_preconditions(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert len(spec.preconditions) >= 2

    def test_command_hook_has_invariants(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert len(spec.invariants) >= 3

    def test_command_hook_has_side_effects(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "command_hook")
        assert len(spec.side_effects) == 4

    def test_enable_player_has_postconditions(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "enable_player")
        assert len(spec.postconditions) >= 4

    def test_find_command_has_valid_cmd_invariant(
        self, all_specs: list[FunctionSpec]
    ) -> None:
        find_specs = [s for s in all_specs if s.signature.name == "find_command"]
        # 至少 commandd.c 版本有 valid_cmd 不变量
        has_valid_cmd = any(
            any("valid_cmd" in (inv.lpc_expr or "") for inv in s.invariants)
            for s in find_specs
        )
        assert has_valid_cmd, "find_command 缺少 valid_cmd 不变量"

    def test_process_input_has_random_spec(self, all_specs: list[FunctionSpec]) -> None:
        spec = next(s for s in all_specs if s.signature.name == "process_input")
        assert len(spec.random_specs) == 1
        assert spec.random_specs[0].lpc_call == "random(2)"
