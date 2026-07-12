"""DBASE_KEY_MAP 测试（阶段 1 T3，ADR-0019）。

覆盖：
- validate_dbase_map 正常路径（with_builtins 全部合法）+ 校验逻辑（空 schema 全报）
- resolve_dbase_key 简单 key / 路径前缀 / 未映射
- POSTPONED_KEYS 不在已映射表
- hypothesis：DBASE_KEY_MAP 任意映射目标 has_field 为 True

[ADR-0019](../../../docs/adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)
[13-dbase-key-map.md](../../../docs/xkx-arch/13-dbase-key-map.md)
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from xkx.runtime.components import Identity, Marks, Progression, Skills, Vitals
from xkx.runtime.dbase_map import (
    DBASE_KEY_MAP,
    PATH_PREFIX_MAP,
    POSTPONED_KEYS,
    resolve_dbase_key,
    validate_dbase_map,
)
from xkx.runtime.schema import SchemaRegistry

# ---- validate_dbase_map ----


def test_validate_dbase_map_clean() -> None:
    """with_builtins 下 DBASE_KEY_MAP + PATH_PREFIX_MAP 全部映射目标合法。"""
    schema = SchemaRegistry.with_builtins()
    assert validate_dbase_map(schema) == []


def test_validate_dbase_map_empty_schema_reports_all() -> None:
    """空 schema 下所有映射目标报问题（校验逻辑工作）。"""
    schema = SchemaRegistry()  # 不注册任何组件
    issues = validate_dbase_map(schema)
    assert len(issues) == len(DBASE_KEY_MAP) + len(PATH_PREFIX_MAP)
    # 问题文案含组件名与字段名
    assert any("DBASE_KEY_MAP" in s for s in issues)
    assert any("PATH_PREFIX_MAP" in s for s in issues)


# ---- resolve_dbase_key ----


def test_resolve_simple_key() -> None:
    assert resolve_dbase_key("combat_exp") == (Progression, "combat_exp")
    assert resolve_dbase_key("qi") == (Vitals, "qi")
    assert resolve_dbase_key("name") == (Identity, "name")
    assert resolve_dbase_key("no_fight") is not None


def test_resolve_path_prefix() -> None:
    """路径访问 key 按前缀解析（LPC skill/axe / marks/酥）。"""
    assert resolve_dbase_key("skill/axe") == (Skills, "levels")
    assert resolve_dbase_key("skill/unarmed") == (Skills, "levels")
    assert resolve_dbase_key("marks/酥") == (Marks, "flags")


def test_resolve_unmapped_returns_none() -> None:
    """未映射 key（后置/未知/未映射路径前缀）返回 None。"""
    assert resolve_dbase_key("actions") is None  # 后置
    assert resolve_dbase_key("race") is None  # 后置（2.5 未激活，2.6 Race）
    assert resolve_dbase_key("nosuchkey") is None  # 未知
    assert resolve_dbase_key("env/immortal") is None  # 路径但前缀未映射
    assert resolve_dbase_key("apply/astral_vision") is None  # 后置路径


# ---- POSTPONED_KEYS 不污染已映射表 ----


def test_postponed_not_in_mapped_tables() -> None:
    """后置 key 不出现在 DBASE_KEY_MAP 或 PATH_PREFIX_MAP。"""
    for key in POSTPONED_KEYS:
        assert key not in DBASE_KEY_MAP
        prefix = key.split("/", 1)[0]
        assert prefix not in PATH_PREFIX_MAP


def test_postponed_keys_disjoint_from_mapped() -> None:
    """POSTPONED_KEYS 与 DBASE_KEY_MAP keys 不相交。"""
    assert POSTPONED_KEYS.isdisjoint(DBASE_KEY_MAP.keys())


# ---- 属性测试 ----


@given(st.sampled_from(sorted(DBASE_KEY_MAP.keys())))
@settings(max_examples=40)
def test_dbase_key_map_targets_valid(key: str) -> None:
    """DBASE_KEY_MAP 任意 key 的映射目标 has_field 为 True（T2 衔接）。"""
    schema = SchemaRegistry.with_builtins()
    comp_type, field_name = DBASE_KEY_MAP[key]
    assert schema.has_field(comp_type, field_name)


@given(st.sampled_from(sorted(PATH_PREFIX_MAP.keys())))
@settings(max_examples=10)
def test_path_prefix_map_targets_valid(prefix: str) -> None:
    """PATH_PREFIX_MAP 任意前缀的映射目标 has_field 为 True。"""
    schema = SchemaRegistry.with_builtins()
    comp_type, field_name = PATH_PREFIX_MAP[prefix]
    assert schema.has_field(comp_type, field_name)
