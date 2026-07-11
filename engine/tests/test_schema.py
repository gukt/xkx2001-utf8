"""SchemaRegistry 测试（阶段 1 T2，ADR-0019）。

覆盖：
- 注册 / 解析 / 字段查询基本功能
- 重复注册幂等 + 类型名冲突 raise SchemaError
- 未注册类型 resolve raise SchemaError（非静默 None）
- World(schema=None) 不校验（向后兼容）/ World(with_builtins) 校验
- build_world 返回的 World 带 schema（拼写错误类型访问失败）
- hypothesis：字段集自动提取与 dataclasses.fields 一致

[ADR-0019](../../../docs/adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import hypothesis.strategies as st
from hypothesis import given, settings

from xkx.runtime.components import (
    Attributes,
    CombatState,
    EffectComp,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.schema import SchemaError, SchemaRegistry
from xkx.runtime.world import build_world

_BUILTIN_TYPES = [
    Identity,
    Position,
    Attributes,
    Vitals,
    Progression,
    Skills,
    CombatState,
    NpcBehavior,
    Inventory,
    Marks,
    QuestLog,
    EffectComp,
    RoomComp,
]


@dataclass
class _Unregistered:
    """未注册的临时组件（模拟拼写错误类型）。"""

    x: int = 0


# ---- 注册 / 解析基本功能 ----


def test_register_and_resolve() -> None:
    reg = SchemaRegistry()
    reg.register(Identity)
    assert reg.resolve(Identity) is Identity
    assert reg.resolve_name("Identity") is Identity


def test_register_idempotent() -> None:
    """重复注册同一类型 no-op（幂等）。"""
    reg = SchemaRegistry()
    reg.register(Identity)
    reg.register(Identity)  # 不 raise
    assert len(list(reg.registered_types())) == 1


def test_register_name_conflict() -> None:
    """类型名冲突（不同类型同名）raise SchemaError。"""
    from xkx.runtime.components import Identity as BuiltinIdentity

    @dataclass
    class Identity:  # noqa: F811 - 同名冲突测试用
        fake: bool = True

    reg = SchemaRegistry()
    reg.register(BuiltinIdentity)
    try:
        reg.register(Identity)
    except SchemaError:
        return
    raise AssertionError("类型名冲突应 raise SchemaError")


def test_register_non_dataclass() -> None:
    """非 dataclass 注册 raise SchemaError（ADR-0017 组件须 dataclass）。"""

    class NotADataclass:
        pass

    reg = SchemaRegistry()
    try:
        reg.register(NotADataclass)
    except SchemaError:
        return
    raise AssertionError("非 dataclass 注册应 raise SchemaError")


def test_resolve_unregistered() -> None:
    """未注册类型 resolve raise SchemaError（非静默 None）。"""
    reg = SchemaRegistry()
    try:
        reg.resolve(_Unregistered)
    except SchemaError:
        return
    raise AssertionError("未注册类型 resolve 应 raise SchemaError")


def test_resolve_name_unknown() -> None:
    reg = SchemaRegistry()
    try:
        reg.resolve_name("NoSuchComponent")
    except SchemaError:
        return
    raise AssertionError("未知类型名 resolve_name 应 raise SchemaError")


# ---- 字段查询 ----


def test_has_field() -> None:
    reg = SchemaRegistry()
    reg.register(Progression)
    assert reg.has_field(Progression, "combat_exp")
    assert reg.has_field(Progression, "potential")
    assert not reg.has_field(Progression, "cobmat_exp")  # 拼写错误
    assert not reg.has_field(Progression, "xyz")


def test_field_names() -> None:
    reg = SchemaRegistry()
    reg.register(Vitals)
    names = reg.field_names(Vitals)
    assert "qi" in names
    assert "max_qi" in names
    assert "eff_qi" in names
    assert "neili" in names


def test_has_field_unregistered_type() -> None:
    """未注册类型 has_field 返回 False（不 raise，供 T3 探测用）。"""
    reg = SchemaRegistry()
    assert not reg.has_field(_Unregistered, "x")


# ---- with_builtins ----


def test_with_builtins_registers_all() -> None:
    """with_builtins 注册全部 13 个内置组件。"""
    reg = SchemaRegistry.with_builtins()
    for t in _BUILTIN_TYPES:
        assert reg.resolve(t) is t
    assert len(list(reg.registered_types())) == len(_BUILTIN_TYPES)


def test_with_builtins_independent() -> None:
    """两次 with_builtins 调用各自独立（无共享状态）。"""
    reg1 = SchemaRegistry.with_builtins()
    reg2 = SchemaRegistry.with_builtins()
    assert reg1 is not reg2
    # reg1 注册临时类型不影响 reg2
    reg1.register(_Unregistered)
    assert reg1.resolve(_Unregistered) is _Unregistered
    try:
        reg2.resolve(_Unregistered)
    except SchemaError:
        return
    raise AssertionError("reg2 不应受 reg1 影响")


# ---- World 校验集成 ----


def test_world_no_schema_backward_compat() -> None:
    """World(schema=None) 不校验，向后兼容 test_ecs 的临时组件用法。"""
    w = World()  # 无 schema
    e = w.new_entity()
    w.add(e, _Unregistered(x=1))  # 未注册类型不 raise
    assert w.get(e, _Unregistered).x == 1
    assert w.has(e, _Unregistered)
    w.remove(e, _Unregistered)
    assert not w.has(e, _Unregistered)


def test_world_with_schema_rejects_unregistered() -> None:
    """World(with_builtins) 未注册类型 get/add/has/remove/entities_with raise SchemaError。"""
    w = World(SchemaRegistry.with_builtins())
    e = w.new_entity()
    for op in (
        lambda: w.add(e, _Unregistered(x=1)),
        lambda: w.get(e, _Unregistered),
        lambda: w.has(e, _Unregistered),
        lambda: w.remove(e, _Unregistered),
        lambda: list(w.entities_with(_Unregistered)),
    ):
        try:
            op()
        except SchemaError:
            continue
        raise AssertionError(f"{op} 应 raise SchemaError")


def test_world_with_schema_allows_registered() -> None:
    """World(with_builtins) 已注册类型正常工作。"""
    w = World(SchemaRegistry.with_builtins())
    e = w.new_entity()
    w.add(e, Identity(name="测试"))
    assert w.get(e, Identity).name == "测试"
    assert w.has(e, Identity)
    assert set(w.entities_with(Identity)) == {e}


def test_build_world_has_schema() -> None:
    """build_world 返回的 World 带 schema（生产路径强制校验）。"""
    ir = {
        "rooms": [
            {"id": "r1", "short": "s", "long": "l", "exits": {}, "objects": {}},
        ],
        "npcs": [],
    }
    world, _, _ = build_world(ir)
    e = world.new_entity()
    try:
        world.get(e, _Unregistered)  # 拼写错误/未注册类型
    except SchemaError:
        return
    raise AssertionError("build_world 的 World 对未注册类型应 raise SchemaError")


# ---- 属性测试 ----


@given(st.sampled_from(_BUILTIN_TYPES))
@settings(max_examples=20)
def test_field_names_match_dataclasses(comp_type: type) -> None:
    """with_builtins 的任意内置组件，field_names == dataclasses.fields。"""
    reg = SchemaRegistry.with_builtins()
    expected = frozenset(f.name for f in dataclasses.fields(comp_type))
    assert reg.field_names(comp_type) == expected


@given(
    st.sampled_from(_BUILTIN_TYPES),
    st.text(min_size=1, max_size=20),
)
@settings(max_examples=50)
def test_has_field_consistent_with_field_names(comp_type: type, name: str) -> None:
    """has_field 与 field_names 一致。"""
    reg = SchemaRegistry.with_builtins()
    assert reg.has_field(comp_type, name) == (name in reg.field_names(comp_type))
