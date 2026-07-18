"""M1 骨架的最小组件集合。

拆分依据是"能否被多种实体类型复用"，不是字段数量（见 M1 spec「对象模型」）：

- ``Identity``、``Description`` 是房间与（未来）物品/NPC 等一切"需要被玩家
  用名字指代/展示描述"的实体通用组件。
- ``Position`` 是"存在于某个房间里"的实体（玩家等）通用组件。
- ``Exits`` 只有房间会用到，但独立成组件，为"一个地点通向哪些其他地点"这条
  能力未来被其他实体（如载具内部空间）复用留空间；出口表在运行时可增删。

别名（命令/目标的别名匹配）留给 02 号票，本票 ``Identity`` 暂不含别名字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mud_engine.world import EntityId


@dataclass
class Identity:
    """给一个实体一个名字，供玩家用名字指代、CLI 用名字展示。"""

    name: str


@dataclass
class Description:
    """展示文本：一句简述 + 一段详细描述，房间与（未来）物品共用同一形状。"""

    short: str
    long: str


@dataclass
class Position:
    """一个实体当前所在的房间。"""

    room: EntityId


@dataclass
class Exits:
    """方向 -> 目标房间 id 的映射。运行时可增删条目（04 号票会验证这一点）。"""

    by_direction: dict[str, EntityId] = field(default_factory=dict)
