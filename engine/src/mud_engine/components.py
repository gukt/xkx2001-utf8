"""M1 骨架的最小组件集合。

拆分依据是"能否被多种实体类型复用"，不是字段数量（见 M1 spec「对象模型」）：

- ``Identity``、``Description`` 是房间与物品/NPC 等一切"需要被玩家用名字指代/
  展示描述"的实体通用组件。``Identity`` 自带 ``aliases``（03 号票起按需扩展：
  物品/NPC 名称别名匹配走 ``matching.match_target``，规范名与别名同权）。
- ``Position`` 是"存在于某个房间里"的实体（玩家等）通用组件。
- ``Exits`` 只有房间会用到，但独立成组件，为"一个地点通向哪些其他地点"这条
  能力未来被其他实体（如载具内部空间）复用留空间；出口表在运行时可增删
  （04 号票验证），每个出口还能携带方向别名（``Exit.aliases``，02 号票）。
- ``Doors`` 是房间出口的门状态集合（``DoorState`` 开/关/锁 + 可选钥匙物品），
  按方向索引但独立于 ``Exits`` 存储--"可开合/上锁"是预期被箱子/密室入口等非
  出口实体复用的能力，单独建模、不并入 ``Exits``（04 号票）。
- ``Container`` 是"持有一堆物品"的通用能力--房间地面与玩家物品栏本质同一种
  能力，用同一种组件各挂一份，不做成两个专属命名的同构组件（03 号票，spec
  「对象模型」"通用能力提炼成独立组件"），顺带给未来的箱子/背包留复用。

出口方向别名（``Exit.aliases``，方向维度）与实体指代别名（``Identity.aliases``，
指代维度）是两个不同维度的别名，各放各的组件。

字段注释面向未来 UGC 创作层的 Agent：它需要从组件字段读懂语义才能生成正确
的场景 DSL，所以每个字段都标了"是什么 + 例子"，并说明运行时可变 vs 启动固定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from mud_engine.world import EntityId


@dataclass
class Identity:
    """给一个实体一个名字（+可选别名），供玩家用名字/别名指代、CLI 用名字展示。

    挂在一切"需要被玩家用名字指代"的实体上：房间、物品、（未来）NPC。
    """

    name: str  # 规范名，玩家指代与展示用，如"石头"/"起始庭院"
    aliases: tuple[str, ...] = ()  # 规范名的替代指代，匹配时与 name 同权，如 ("石","顽石")


@dataclass
class Description:
    """展示文本：一句简述 + 一段详细描述，房间与物品共用同一形状。

    挂在房间与物品上（未来 NPC 也复用）；M1 的命令只展示房间的 short/long 与
    物品的 name，物品的 short/long 留给未来 examine 命令消费。
    """

    short: str  # 一句简述，look 时第一行展示，如"一块灰扑扑的石头"
    long: str  # 详细描述，look 时第二行展示，如"一块毫不起眼的石头，沉甸甸的……"


@dataclass
class Position:
    """一个实体当前所在的房间。

    挂在"存在于某个房间里"的实体上（玩家等）；物品不挂它（物品被 Container
    持有，位置隐含在哪个容器里）。
    """

    room: EntityId  # 所在房间的 entity id


@dataclass(frozen=True)
class Exit:
    """一条出口：目标房间 id + 可选的方向别名（如"北道"/"前门"）。

    别名参与 ``matching.match_target`` 的方向匹配，让玩家不必输入完全规范的
    方向名。target 与 aliases 是同一个"通往哪里"概念的自然组成部分，留在一起
    不强行拆（见 spec「对象模型」拆分标准）。
    """

    target: EntityId  # 出口指向的目标房间 entity id
    aliases: tuple[str, ...] = ()  # 方向别名，如 ("北道","前门")，匹配时与规范方向名同权


@dataclass
class Exits:
    """方向 -> 出口。运行时可增删条目（04 号票会验证这一点）。

    只挂在房间上（"一个地点通向哪些其他地点"），但独立成组件为未来载具内部
    空间等实体复用留空间。某个出口暂时不存在时，直接不在 by_direction 里即可。
    """

    by_direction: dict[str, Exit] = field(
        default_factory=dict
    )  # 方向名 -> 出口；方向名如"north"/"east"，运行时可增删


class DoorState(Enum):
    """门的三种状态：开 / 关 / 锁。

    用枚举而非裸字符串，让"状态只能取这三个值之一"在类型层就锁死，避免误传
    ``"ajar"`` 之类非法值。值用小写字符串，方便 YAML 里直接 ``door: closed``
    映射（``DoorState("closed")`` 即可由值构造）。
    """

    OPEN = "open"  # 开着，go 可通行
    CLOSED = "closed"  # 关着，挡住 go；可 open 打开
    LOCKED = "locked"  # 锁着，挡住 go；需先 unlock（可能需要匹配钥匙）


@dataclass
class Door:
    """一条门的状态 + 可选钥匙引用：可复用的"可开合/上锁"数据单元。

    独立于 ``Exit``（出口目标/方向别名）存在--门状态是预期会被出口之外的其他实体
    （箱子、密室入口等）复用的能力，所以单独建模，不塞进 ``Exit``（04 号票
    acceptance 第 7 条）。``state`` 运行时可变（``open``/``close``/``unlock``
    直接改）；``key_item_id`` 是 LOCKED 状态解锁所需钥匙物品的 entity id，
    ``None`` 表示该锁不绑定特定钥匙（或当前不是锁）。
    """

    state: DoorState
    key_item_id: EntityId | None = None  # LOCKED 时解锁需要的钥匙物品 entity id；None=不绑定钥匙


@dataclass
class Doors:
    """房间出口的门状态集合，按方向索引（与 ``Exits`` 同方向键）。

    独立成组件、不并入 ``Exits``：``Exits`` 表达"通向哪里"（出口目标+别名），
    ``Doors`` 表达"能不能过"（开/关/锁）--两条能力正交，分开存储让"可开合/上锁"
    未来能被非出口实体复用（04 号票）。某个方向没有门时，该方向不在
    ``by_direction`` 里即可，不强制每个出口都配门。
    """

    by_direction: dict[str, Door] = field(
        default_factory=dict
    )  # 方向名 -> 门状态；只含有门的方向，方向键与 Exits.by_direction 一致


@dataclass
class Container:
    """一个实体持有的一堆物品（entity id 集合）。

    房间地面与玩家物品栏都是这个组件的一个实例--同一个"持有一堆物品"的通用
    能力，不是两个专属命名的同构组件（03 号票）。未来箱子/背包等容器类物品
    直接复用同一组件即可。
    """

    items: set[EntityId] = field(
        default_factory=set
    )  # 持有的物品 entity id 集合；房间地面/玩家物品栏/未来箱子各挂一份
