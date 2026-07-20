"""World 存储的公开接口测试：新建实体 / 挂载组件 / 读取组件 / 判断是否有组件 /
移除组件 / 多类型联合查询。只测外部可观察行为，不断言内部存储结构。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

from dataclasses import dataclass

import pytest

from mud_engine.components import Position
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


class TestEntitiesInRoom:
    """34 号票：房间内实体查询（遍历 Position + 按 room 过滤 + 排除）。

    commands（look 在场 NPC / room_say 广播 / _find_npc_in_room）与 parsing
    （_npc_candidates）四处重复逻辑收敛到本方法。玩家与 NPC 都用 Position 表达
    "在房间里"；物品不挂 Position（被 Container 持有）故天然不收进。
    """

    def test_returns_only_entities_whose_position_matches_the_room(self) -> None:
        world = World()
        room_a = world.create_entity()
        room_b = world.create_entity()
        in_a = world.create_entity()
        in_b = world.create_entity()
        world.add_component(in_a, Position(room=room_a))
        world.add_component(in_b, Position(room=room_b))
        assert set(world.entities_in_room(room_a)) == {in_a}

    def test_excludes_the_named_exclude_entity(self) -> None:
        world = World()
        room = world.create_entity()
        player = world.create_entity()
        npc = world.create_entity()
        world.add_component(player, Position(room=room))
        world.add_component(npc, Position(room=room))
        assert set(world.entities_in_room(room, exclude=player)) == {npc}

    def test_omits_entities_without_position(self) -> None:
        # 物品被 Container 持有、不挂 Position，不应被当作"在房间里"。
        world = World()
        room = world.create_entity()
        bare = world.create_entity()  # 无 Position
        world.add_component(bare, Name("裸实体"))
        assert list(world.entities_in_room(room)) == []

    def test_returns_empty_when_no_one_is_in_the_room(self) -> None:
        world = World()
        room = world.create_entity()
        assert list(world.entities_in_room(room)) == []


# ── 05 号票：存档/恢复需要的 World 能力 ─────────────────
# restore 要按存档里记录的 entity id 重建实体（stable id，让出口/门/容器引用
# 直接生效，无需 remap）；serialize 要能遍历全部实体与每个实体的全部组件。


class TestCreateEntityWithId:
    """restore 路径：用存档记录的 id 重建实体，保持引用图稳定。"""

    class WhenTheIdIsFree:
        def test_creates_an_entity_with_that_exact_id(self) -> None:
            world = World()
            assert world.create_entity_with_id(42) == 42

        def test_advances_the_counter_past_it(self) -> None:
            # 之后普通 create_entity 不会复用这个 id。
            world = World()
            world.create_entity_with_id(42)
            assert world.create_entity() == 43

    class WhenTheIdIsAlreadyTaken:
        def test_raises_a_clear_error(self) -> None:
            world = World()
            world.create_entity_with_id(7)
            with pytest.raises(ValueError):
                world.create_entity_with_id(7)


class TestAllEntities:
    def test_iterates_every_entity_ever_created(self) -> None:
        world = World()
        a = world.create_entity()
        b = world.create_entity()
        c = world.create_entity_with_id(100)
        assert set(world.all_entities()) == {a, b, c}


class TestComponentsOf:
    """serialize 用：拿到某实体挂载的全部 (类型, 组件) 对。"""

    def test_returns_each_component_paired_with_its_type(self) -> None:
        world = World()
        e = world.create_entity()
        world.add_component(e, Name("甲"))
        world.add_component(e, Health(5))
        pairs = dict(world.components_of(e))
        assert pairs[Name] == Name("甲")
        assert pairs[Health] == Health(5)

    def test_returns_empty_for_an_entity_with_no_components(self) -> None:
        world = World()
        e = world.create_entity()
        assert list(world.components_of(e)) == []

    def test_does_not_include_components_of_other_entities(self) -> None:
        world = World()
        a = world.create_entity()
        b = world.create_entity()
        world.add_component(a, Name("甲"))
        world.add_component(b, Name("乙"))
        assert dict(world.components_of(b)) == {Name: Name("乙")}
