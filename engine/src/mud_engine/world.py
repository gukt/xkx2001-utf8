"""最小 ECS 风格的世界状态容器：entity 只是一个不透明 id，组件数据按类型分散存储。

只提供 M1 骨架需要的六种操作：新建实体 / 挂载组件 / 读取某类型组件 /
判断是否有某类型组件 / 移除组件 / 查询同时拥有多个指定组件类型的实体集合。
内部存储实现从零编写（参考 engine/prototypes/ecs_ugc/ 与旧引擎的形状，不搬迁代码）。
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import count
from typing import TypeVar

EntityId = int

TComponent = TypeVar("TComponent")


class World:
    """实体与组件的容器，也是引擎全局可变态的落脚点。

    查询按组件类型索引，不做强类型 schema 校验（M1 阶段组件少、字段简单，
    校验层收益不足以覆盖引入成本，见 M1 spec「对象模型」）。
    """

    def __init__(self) -> None:
        """初始化一个空世界：没有实体、没有组件、未请求退出。"""
        self._next_id = count(1)
        self._entities: set[EntityId] = set()
        self._components: dict[type, dict[EntityId, object]] = {}
        # 全局引擎态（不属于任何单个 entity，因此不建成组件）：命令处理函数
        # 通过它请求 CLI 循环结束；05 号票的 tick 计数会用同样的方式挂在这里。
        self.should_quit = False

    def create_entity(self) -> EntityId:
        """分配一个新的、全局唯一的实体 id（本身不带任何组件）。"""
        entity = next(self._next_id)
        self._entities.add(entity)
        return entity

    def add_component(self, entity: EntityId, component: object) -> None:
        """给实体挂载一个组件；同类型组件已存在时直接覆盖。"""
        component_type = type(component)
        self._components.setdefault(component_type, {})[entity] = component

    def get_component(
        self, entity: EntityId, component_type: type[TComponent]
    ) -> TComponent | None:
        """读取实体上某类型的组件，不存在则返回 None（由调用方决定如何处理缺失）。"""
        return self._components.get(component_type, {}).get(entity)  # type: ignore[return-value]

    def require_component(self, entity: EntityId, component_type: type[TComponent]) -> TComponent:
        """读取某类型组件，缺失时抛出明确异常，而不是返回 None 让调用方自己判断。

        用于"这个组件按场景数据/对象模型约定必须存在"的场景（例如一个房间必有
        Exits/Description）——这类缺失是数据/程序错误，应该尽早、明确地暴露。
        **不要**用它处理"玩家输入引用的目标可能不存在"这种情况（如玩家想拾取一个
        不在房间里的物品）：那种情况需要给玩家一句提示、不移动/不改变状态，不是
        抛异常——`assert` 在 `python -O` 下会被整体剥离，用普通异常保证这条检查
        任何运行模式下都生效。
        """
        component = self.get_component(entity, component_type)
        if component is None:
            raise LookupError(f"entity {entity} 缺少必需组件 {component_type.__name__}")
        return component

    def has_component(self, entity: EntityId, component_type: type) -> bool:
        """判断实体是否挂载了某类型的组件。"""
        return entity in self._components.get(component_type, {})

    def remove_component(self, entity: EntityId, component_type: type) -> None:
        """移除实体上某类型的组件；组件本就不存在时静默忽略，不抛异常。"""
        self._components.get(component_type, {}).pop(entity, None)

    def entities_with(self, *component_types: type) -> Iterable[EntityId]:
        """查询同时拥有全部给定组件类型的实体集合（未传类型时返回空）。"""
        if not component_types:
            return iter(())
        matching_sets = [set(self._components.get(t, {})) for t in component_types]
        return iter(set.intersection(*matching_sets))
