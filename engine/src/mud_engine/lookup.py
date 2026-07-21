"""物品查找共享逻辑（30 号票去重：Duplicated Code）。

commands 与 parsing 原先各自内联同构查找：按 room/player 找挂 ``Container`` 的
同名物品，以及 look 用的 room/player + 一层嵌套遍历。本模块收敛为单一实现。

抽第三处而非放 commands 或 parsing：parsing 已 ``from mud_engine.commands import
execute, resolve_verb``，commands 不 import parsing，查找放任一侧都会引入反向
依赖或循环，故放独立叶子模块（只依赖 world + components）。
"""

from __future__ import annotations

from collections.abc import Iterator

from mud_engine.components import Container, Identity, Position
from mud_engine.world import EntityId, World


def find_reachable_container(world: World, player_id: EntityId, name: str) -> EntityId | None:
    """按规范名找可达容器物品：当前房间地面或玩家物品栏内挂 ``Container`` 的物品。

    take-from / put（commands）与 take-from 解析（parsing）共用。
    """
    room = world.require_component(player_id, Position).room
    for holder in (room, player_id):
        container = world.get_component(holder, Container)
        if container is None:
            continue
        for item in container.items:
            if world.require_component(item, Identity).name != name:
                continue
            if world.get_component(item, Container) is not None:
                return item
    return None


def iter_lookable_containers(world: World, player_id: EntityId) -> Iterator[Container]:
    """look 物品可达容器：房间地面、玩家物品栏、及其中一层嵌套容器（按 holder 分组）。

    ``commands._find_lookable_item``（找首个匹配 entity）与
    ``parsing._look_item_candidates``（收集去重候选）共用的遍历结构；调用方在
    此基础上各自做匹配 / 收集。yield 顺序与原 ``_find_lookable_item`` 一致
    （holder 直接容器在前、其嵌套容器紧随），保证首个匹配结果不回归。
    """
    room = world.require_component(player_id, Position).room
    for holder in (room, player_id):
        container = world.get_component(holder, Container)
        if container is None:
            continue
        yield container
        for item in container.items:
            nested = world.get_component(item, Container)
            if nested is not None:
                yield nested


__all__ = ["find_reachable_container", "iter_lookable_containers"]
