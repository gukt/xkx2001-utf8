"""SparseSet ECS 测试（阶段 1 T1，ADR-0017）。

覆盖 SparseSet 特有行为：swap-remove 正确性、同名组件覆盖、多组件交集查询、
缺存储降级。hypothesis 属性测试验证 SparseSet 与参考 dict 行为一致。

[ADR-0017](../../../docs/adr/ADR-0017-ecs-sparse-set-effect-component.md)
"""

from __future__ import annotations

from dataclasses import dataclass

import hypothesis.strategies as st
from hypothesis import given, settings

from xkx.runtime.ecs import World


@dataclass
class _A:
    x: int = 0


@dataclass
class _B:
    y: int = 0


@dataclass
class _C:
    z: int = 0


# ---- 基本功能 ----


def test_add_get_has_remove() -> None:
    w = World()
    e1 = w.new_entity()
    e2 = w.new_entity()
    w.add(e1, _A(x=1))
    w.add(e2, _A(x=2))
    w.add(e2, _B(y=3))
    assert w.get(e1, _A).x == 1
    assert w.get(e2, _A).x == 2
    assert w.get(e2, _B).y == 3
    assert w.has(e1, _A)
    assert not w.has(e1, _B)
    assert w.get(e1, _B) is None
    w.remove(e2, _B)
    assert not w.has(e2, _B)
    assert w.get(e2, _B) is None
    w.remove(e1, _B)  # remove 不存在的组件 no-op
    assert w.has(e1, _A)


def test_overwrite_same_type() -> None:
    """同类型覆盖：不增加计数，值更新。"""
    w = World()
    e = w.new_entity()
    w.add(e, _A(x=1))
    w.add(e, _A(x=99))
    assert w.get(e, _A).x == 99
    assert len(list(w.entities_with(_A))) == 1


def test_entities_with_intersection() -> None:
    w = World()
    e1, e2, e3 = w.new_entity(), w.new_entity(), w.new_entity()
    w.add(e1, _A())
    w.add(e1, _B())
    w.add(e2, _A())
    w.add(e2, _B())
    w.add(e2, _C())
    w.add(e3, _A())
    w.add(e3, _C())
    assert set(w.entities_with(_A)) == {e1, e2, e3}
    assert set(w.entities_with(_A, _B)) == {e1, e2}
    assert set(w.entities_with(_A, _B, _C)) == {e2}
    assert set(w.entities_with(_C, _A)) == {e2, e3}  # 顺序无关


def test_entities_with_missing_store() -> None:
    """某组件类型无存储时，entities_with 返回空。"""
    w = World()
    e = w.new_entity()
    w.add(e, _A())
    assert list(w.entities_with(_A, _B)) == []
    assert list(w.entities_with(_B)) == []
    assert list(w.entities_with()) == []  # 无参数


def test_swap_remove_preserves_others() -> None:
    """swap-remove 后剩余实体组件不错位。"""
    w = World()
    eids = [w.new_entity() for _ in range(5)]
    for i, e in enumerate(eids):
        w.add(e, _A(x=i))
    w.remove(eids[2], _A)  # 删中间，触发 swap-remove
    assert not w.has(eids[2], _A)
    remaining = set(w.entities_with(_A))
    assert remaining == {eids[0], eids[1], eids[3], eids[4]}
    for i, e in enumerate(eids):
        if e == eids[2]:
            continue
        assert w.get(e, _A).x == i  # 各自的 x 值未错位


def test_remove_then_re_add() -> None:
    """删除后可重新添加。"""
    w = World()
    e = w.new_entity()
    w.add(e, _A(x=1))
    w.remove(e, _A)
    w.add(e, _A(x=2))
    assert w.get(e, _A).x == 2
    assert len(list(w.entities_with(_A))) == 1


# ---- 属性测试 ----


_op_strategy = st.lists(
    st.tuples(
        st.sampled_from(["add", "remove", "get"]),
        st.integers(0, 4),
        st.integers(0, 100),
    ),
    min_size=5,
    max_size=25,
)


@given(_op_strategy)
@settings(max_examples=80)
def test_sparse_set_matches_reference_dict(
    ops: list[tuple[str, int, int]],
) -> None:
    """任意 add/remove/get 序列下，SparseSet 与参考 dict 行为一致。"""
    w = World()
    eids = [w.new_entity() for _ in range(5)]
    ref: dict[int, _A] = {}
    for kind, i, val in ops:
        eid = eids[i]
        if kind == "add":
            w.add(eid, _A(x=val))
            ref[eid] = _A(x=val)
        elif kind == "remove":
            w.remove(eid, _A)
            ref.pop(eid, None)
        else:  # get
            actual = w.get(eid, _A)
            expected = ref.get(eid)
            if expected is None:
                assert actual is None
                assert not w.has(eid, _A)
            else:
                assert actual is not None
                assert actual.x == expected.x
                assert w.has(eid, _A)
    # 最终一致性
    assert set(w.entities_with(_A)) == ref.keys()
