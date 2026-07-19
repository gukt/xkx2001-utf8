"""最小 ECS 风格的世界状态容器：entity 只是一个不透明 id，组件数据按类型分散存储。

提供 M1 骨架需要的核心操作：新建实体 / 挂载组件 / 读取某类型组件 /
判断是否有某类型组件 / 移除组件 / 查询同时拥有多个指定组件类型的实体集合。
05 号票另加按指定 id 重建实体（``create_entity_with_id``）、遍历全部实体
（``all_entities``）与某实体的全部组件（``components_of``），供存档序列化与恢复使用。
内部存储实现从零编写（参考 engine/prototypes/ecs_ugc/ 与旧引擎的形状，不搬迁代码）。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from mud_engine.events import EventBus

EntityId = int

TComponent = TypeVar("TComponent")


class World:
    """实体与组件的容器，也是引擎全局可变态的落脚点。

    查询按组件类型索引，不做强类型 schema 校验（M1 阶段组件少、字段简单，
    校验层收益不足以覆盖引入成本，见 M1 spec「对象模型」）。
    """

    def __init__(self) -> None:
        """初始化一个空世界：没有实体、没有组件、未请求退出。"""
        # int 计数器（而非 itertools.count）：05 号票的 restore 路径需要把
        # 计数器推过存档里已有的最大 id，用 int 才能任意 bump。
        self._next_id = 1
        self._entities: set[EntityId] = set()
        self._components: dict[type, dict[EntityId, object]] = {}
        # 全局引擎态（不属于任何单个 entity，因此不建成组件）：命令处理函数
        # 通过它请求 CLI 循环结束；05 号票的 tick 计数会用同样的方式挂在这里。
        self.should_quit = False
        # 事件总线 / 钩子注册表（07 号票，块 A 地基）：按事件 key 路由到 handler
        # 列表，``TickLoop.advance`` 用它分发 on_tick。挂 world 上做实例隔离；不进
        # 存档（存档只序列化 entities/components，见 save.py），restore 后为空，
        # 订阅者由各子系统在启动 / restore 后重新注册（M1 save_fn 不依赖 events，
        # 故存档行为不受影响）。
        self.events = EventBus()

    def create_entity(self) -> EntityId:
        """分配一个新的、全局唯一的实体 id（本身不带任何组件）。"""
        entity = self._next_id
        self._next_id += 1
        self._entities.add(entity)
        return entity

    def create_entity_with_id(self, entity_id: EntityId) -> EntityId:
        """用调用方指定的 id 重建实体（存档恢复路径，05 号票）。

        restore 时按存档里记录的 entity id 重建，使出口/门/容器对 entity id
        的引用在恢复后直接生效（stable id，无需 remap 翻译）。id 已存在时抛
        ValueError（restore 容错层负责把它当作"单条目损坏"跳过记警告）；
        同时把计数器推过该 id，之后普通 ``create_entity`` 不会与之冲突。
        """
        if entity_id in self._entities:
            raise ValueError(f"entity id {entity_id} 已存在")
        self._entities.add(entity_id)
        if entity_id >= self._next_id:
            self._next_id = entity_id + 1
        return entity_id

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

    def all_entities(self) -> Iterable[EntityId]:
        """遍历全部已建实体（05 号票 serialize 全量存档用）。"""
        return iter(self._entities)

    def components_of(self, entity: EntityId) -> Iterable[tuple[type, object]]:
        """遍历某实体挂载的全部 (组件类型, 组件实例) 对（05 号票 serialize 用）。

        组件存储按类型索引（``dict[type, dict[eid, object]]``），因此"某实体的
        全部组件"要扫一遍类型表；M1 实体与组件数量都小，O(类型数) 可接受。
        """
        for component_type, by_entity in self._components.items():
            component = by_entity.get(entity)
            if component is not None:
                yield (component_type, component)
