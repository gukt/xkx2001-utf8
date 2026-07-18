"""World 存储的公开接口测试：新建实体 / 挂载组件 / 读取组件 / 判断是否有组件 /
移除组件 / 多类型联合查询。只测外部可观察行为，不断言内部存储结构。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

from dataclasses import dataclass

import pytest

from mud_engine.world import World


@dataclass
class Name:
    value: str


@dataclass
class Health:
    hp: int


class TestCreateEntity:
    def test_returns_unique_ids_across_calls(self) -> None:
        world = World()
        a = world.create_entity()
        b = world.create_entity()
        assert a != b


class TestAddComponent:
    def test_component_can_be_read_back_via_get_component(self) -> None:
        world = World()
        entity = world.create_entity()
        world.add_component(entity, Name("守卫"))
        assert world.get_component(entity, Name) == Name("守卫")

    def test_overwrites_existing_component_of_the_same_type(self) -> None:
        world = World()
        entity = world.create_entity()
        world.add_component(entity, Name("旧名字"))
        world.add_component(entity, Name("新名字"))
        assert world.get_component(entity, Name) == Name("新名字")


class TestGetComponent:
    def test_returns_none_when_component_was_never_added(self) -> None:
        world = World()
        entity = world.create_entity()
        assert world.get_component(entity, Name) is None


class TestHasComponent:
    def test_reflects_whether_the_component_is_present(self) -> None:
        world = World()
        entity = world.create_entity()
        assert world.has_component(entity, Name) is False
        world.add_component(entity, Name("商人"))
        assert world.has_component(entity, Name) is True


class TestRemoveComponent:
    def test_makes_has_component_false_afterwards(self) -> None:
        world = World()
        entity = world.create_entity()
        world.add_component(entity, Name("商人"))
        world.remove_component(entity, Name)
        assert world.has_component(entity, Name) is False

    def test_makes_get_component_return_none_afterwards(self) -> None:
        world = World()
        entity = world.create_entity()
        world.add_component(entity, Name("商人"))
        world.remove_component(entity, Name)
        assert world.get_component(entity, Name) is None

    def test_is_a_noop_when_the_component_was_never_added(self) -> None:
        world = World()
        entity = world.create_entity()
        world.remove_component(entity, Name)  # 不应抛异常


class TestRequireComponent:
    def test_returns_the_component_when_present(self) -> None:
        world = World()
        entity = world.create_entity()
        world.add_component(entity, Name("甲"))
        assert world.require_component(entity, Name) == Name("甲")

    def test_raises_a_clear_error_when_the_component_is_missing(self) -> None:
        world = World()
        entity = world.create_entity()
        with pytest.raises(LookupError):
            world.require_component(entity, Name)


class TestEntitiesWith:
    class WhenQueryingASingleComponentType:
        def test_returns_only_entities_that_have_it(self) -> None:
            world = World()
            a = world.create_entity()
            b = world.create_entity()
            world.add_component(a, Name("甲"))
            assert set(world.entities_with(Name)) == {a}
            assert b not in set(world.entities_with(Name))

    class WhenQueryingMultipleComponentTypes:
        def test_returns_only_entities_that_have_all_of_them(self) -> None:
            world = World()
            a = world.create_entity()
            b = world.create_entity()
            world.add_component(a, Name("甲"))
            world.add_component(a, Health(10))
            world.add_component(b, Name("乙"))
            assert set(world.entities_with(Name, Health)) == {a}

    class WhenNoEntityMatches:
        def test_returns_empty(self) -> None:
            world = World()
            world.create_entity()
            assert list(world.entities_with(Health)) == []
