"""最小 ECS 风格的世界状态容器：entity 只是一个不透明 id，组件数据按类型分散存储。

提供 M1 骨架需要的核心操作：新建实体 / 挂载组件 / 读取某类型组件 /
判断是否有某类型组件 / 移除组件 / 查询同时拥有多个指定组件类型的实体集合。
05 号票另加按指定 id 重建实体（``create_entity_with_id``）、遍历全部实体
（``all_entities``）与某实体的全部组件（``components_of``），供存档序列化与恢复使用。
内部存储实现从零编写（参考 engine/prototypes/ecs_ugc/ 与旧引擎的形状，不搬迁代码）。
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from mud_engine.components import Position
from mud_engine.events import EventBus

if TYPE_CHECKING:
    from mud_engine.ai import AISystem, SpawnerBlueprint
    from mud_engine.combat import PowerModel
    from mud_engine.ferry import FerryState
    from mud_engine.nature import NatureState

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
        # 场景数据里引擎不识别的段（顶层 rules/world_rules/nature、实体级
        # on_use/effect/dialogue/behaviors 等，11 号票）原样透传留在这里，M1 不解析
        # 不执行，只留数据不丢，供 M3 规则引擎消费--这是"不锁死未来"的关键：引擎
        # 升级后旧场景数据不必重写。透传的是声明式静态数据、非运行时可变态，故不
        # 进存档（与 ``events`` 同：存档只序列化 entities/components，restore 后
        # 为空，由下次 ``load_scene`` 重新填充；restore 路径不读 YAML 故不重建，
        # M1 透传数据只供引擎内部留底、不参与运行时态）。
        self.extension_data: dict[str, object] = {}
        self._entity_extension_data: dict[EntityId, dict[str, object]] = {}
        # Nature 运行时态（13 号票，块 B）：纯内存、不进存档；由 ``attach_nature``
        # 挂载。TYPE_CHECKING 下标成 NatureState 供类型检查，避免循环 import。
        self.nature: NatureState | None = None
        # NPC AI 子系统运行时态（25 号票，块 D）：纯内存、不进存档；由
        # ``attach_ai_system`` 挂载。TYPE_CHECKING 下标成 AISystem 供类型检查
        # （与 ``nature`` 同，避免循环 import）。
        self.ai: AISystem | None = None
        # 战斗 PowerModel 策略（M2-02）：纯内存、不进存档；由 ``attach_power_model``
        # 挂载。缺省 None 时 resolve_attack / 命令层用 DefaultWuxiaPowerModel 兜底。
        self.power_model: PowerModel | None = None
        # NPC Spawner 蓝图注册表（M2-04）：纯内存、不进存档；由 scene_loader 建 NPC
        # 时注册。``_spawn_scan`` 遍历本表而非从存活实例反向聚合，避免 template
        # 全灭后丢失期望值。
        self.spawners: dict[str, SpawnerBlueprint] = {}
        # 物品模板原始 YAML（M2-07 商店 buy 实例化用）：纯内存、不进存档。
        self.item_templates: dict[str, dict] = {}
        # 渡口运行时态（M2-09）：纯内存、不进存档；由 ``attach_ferries`` 挂载。
        self.ferries: FerryState | None = None
        # 异步广播通道（16/28 号票）：Nature 相位切换、NPC Chatter 等推给玩家的
        # 文案落在这里；CLI 在 tick 后 drain 打印。M1 单机单玩家用扁平 list。不进存档。
        self.pending_messages: list[str] = []
        # 本 world 由哪份场景 YAML 加载（``load_scene`` 写入）。进存档 meta，供
        # restore 后重读题材包 ``nature:`` 配置（不能写死 DEFAULT_SCENE_PATH）。
        self.scene_path: Path | None = None

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

    def entities_in_room(
        self, room: EntityId, *, exclude: EntityId | None = None
    ) -> Iterable[EntityId]:
        """在该房间内的全部实体（挂 ``Position`` 且 ``room`` 字段匹配），可排除单个实体。

        34 号票去重：commands（``_sorted_npc_names_in_room`` / ``room_say`` /
        ``_find_npc_in_room``）与 parsing（``_npc_candidates``）四处重复"遍历
        ``entities_with(Position)`` + 按 room 过滤 + 排除某实体"，收敛到本方法。
        玩家与 NPC 都用 ``Position`` 表达"在房间里"（物品不挂，被 Container 持有）。
        """
        for entity in self.entities_with(Position):
            if entity == exclude:
                continue
            if self.require_component(entity, Position).room != room:
                continue
            yield entity

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

    def destroy_entity(self, entity: EntityId) -> None:
        """彻底移除一个实体及其全部组件（M2-04 重生 / 后续死亡流程用）。

        不存在的 id 静默忽略。同步清理该实体的 ``entity_extension_data``。
        不负责从他人 ``Container.items`` 里摘引用——调用方须先处理容器持有关系。
        """
        if entity not in self._entities:
            return
        for by_entity in self._components.values():
            by_entity.pop(entity, None)
        self._entities.discard(entity)
        self._entity_extension_data.pop(entity, None)

    def entity_extension_data(self, entity: EntityId) -> dict[str, object]:
        """取（惰性创建并存储）某实体的扩展数据 dict 引用（11 号票）。

        场景数据里引擎不识别的**实体级**段（物品 ``on_use``/``effect``、NPC
        ``dialogue``/``behaviors`` 等）由 ``scene_loader`` 原样透传到这里。M1 不解析
        不执行，只留数据不丢。惰性创建：查询一个从未被填过透传数据的实体返回空
        dict（不报错），有数据时返回已填的引用供调用方读写。

        与 ``extension_data`` 一样是声明式静态数据、非运行时可变态，不进存档
        （存档只遍历 entities/components，碰不到这里）；故 restore 后为空、由
        下次 ``load_scene`` 重新填充。透传数据按 entity 索引而非做成挂在 entity
        上的组件，是为了让它天然游离于存档序列化之外（做成组件会触发 05 号票
        "未注册 codec 报 TypeError"的护栏或被迫进存档，两难）。
        """
        return self._entity_extension_data.setdefault(entity, {})
