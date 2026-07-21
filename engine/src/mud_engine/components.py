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
的场景 DSL，所以每个字段都标了"是什么 + 例子"，并标注三态之一（避坑清单 §28，
12 号票）：

- **启动固定**：加载时定、之后不变（如 ``Identity.name``、``Description`` 文案）。
- **运行时可变进存档**：运行时会改、且要跨重启保留（如 ``Door.state``、
  ``Container.items``、动态增删的 ``Exits.by_direction``）--save.py 序列化保留。
- **瞬时（运行时可变不进存档）**：运行时派生/累加、重启后从默认值或真实时钟
  重算（如未来 Nature 的当前时辰）--用 ``transient_field()`` 标注，save.py
  序列化时一律剔除，恢复后回到默认值。为避坑清单 §37"短延迟内存态 vs 长周期
  持久态"分层铺路。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # ``EntityId`` 仅用于组件字段注解（``from __future__ import annotations`` 下注解
    # 不在运行时求值），故放 TYPE_CHECKING 而非运行时 import--这样 components 是运行时
    # 叶子，world.py 可运行时 ``from mud_engine.components import Position``（34 号票
    # ``entities_in_room`` 用）而不引入 components ↔ world 循环。
    from mud_engine.world import EntityId

# 组件字段三态中"瞬时"态的 dataclass field metadata key（12 号票）。
# ``transient_field()`` 写入此 key 标注，save.py 的序列化 chokepoint 读它过滤剔除。
TRANSIENT = "transient"


def transient_field(default):
    """标注一个组件字段为第三态"瞬时"：运行时可变、不进存档。

    用法 ``ticks_alive: int = transient_field(0)``。save.py 序列化时通过
    ``dataclasses.fields()`` 读 metadata，瞬时字段一律不进存档，恢复后回到默认值。
    Nature 衍生态（B 块）会是第一个真实用例。与"运行时可变进存档 / 启动固定"
    两态并列（见模块 docstring 三态说明，避坑清单 §28）。
    """
    return field(default=default, metadata={TRANSIENT: True})


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

    挂在房间与物品上（未来 NPC 也复用）；房间 look 展示 short/long，物品
    ``look <物品>``（23 号票）展示 long 与数值细节。``outdoors`` 标记户外房间
    （块 B Nature，spec US 20 决策：挂 Description 而非新建专属组件）：look 时
    追加时辰/天气文案；启动固定。
    """

    short: str  # 一句简述，look 时第一行展示，如"一块灰扑扑的石头"
    long: str  # 详细描述，look 时第二行展示，如"一块毫不起眼的石头，沉甸甸的……"
    outdoors: bool = False  # 户外房间标记；True 时 look 追加 Nature 时辰/天气 desc


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
    能力，不是两个专属命名的同构组件（03 号票）。箱子/背包等容器类物品直接
    复用同一组件（22 号票）。``max_capacity`` / ``max_weight`` 为可选上限
    （24 号票）：``None`` 表示不限制；超限由 ``transfer`` 拒绝放入。M1 容器
    始终可打开（不做 open/closed）。
    """

    items: set[EntityId] = field(
        default_factory=set
    )  # 持有的物品 entity id 集合；房间地面/玩家物品栏/箱子各挂一份
    # 运行时可变进存档：上限本身启动固定，但放在组件上便于 YAML 声明与存档恢复。
    max_capacity: int | None = None  # 最多容纳几个物品实体（堆叠合并不占新槽）；None=不限
    max_weight: float | None = None  # 容器内总重量上限；None=不限


@dataclass
class Stackable:
    """可堆叠：数量 + 单位重量（18/20 号票）。

    按需挂载；``transfer`` 到已有同名 Stackable 的容器时自动合并 amount。
    ``unit_weight * amount`` 参与重量校验（24 号票）。amount 运行时可变进存档。
    """

    amount: int  # 堆叠数量，运行时可变进存档
    unit_weight: float = 1.0  # 单件重量；启动固定


@dataclass
class Valuable:
    """有价值：纯数据占位（18 号票）。M1 不做买卖，value 仅供 look 展示与存档。"""

    value: int  # 价值数值；启动固定（M1 无改价命令）


@dataclass
class Equippable:
    """可装备占位（18 号票）。M1 不实现 wield/wear；slot / apply_hook 供 M2 接入。"""

    slot: str = ""  # 装备槽位名占位，如 "hand"；启动固定
    apply_hook: str | None = None  # 装备效果钩子名引用占位；启动固定


@dataclass
class Consumable:
    """可消耗占位（18 号票）。M1 不实现 eat/drink；uses 供 M2 状态系统接入。"""

    uses: int = 1  # 剩余使用次数；运行时可变进存档（M2 消耗时改）


@dataclass
class ItemFlags:
    """物品流转标志位（21 号票）：no_get / no_drop。

    声明式数据字段（非闭包）。``no_drop_message`` 为自定义拒绝提示；缺省时用
    引擎默认文案。挂在需要限制流转的物品上，无标志则不挂本组件。
    """

    no_get: bool = False  # True 时不能拿起（如固定家具）；启动固定
    no_drop: bool = False  # True 时不能丢弃/放入容器；启动固定
    no_drop_message: str | None = None  # no_drop 时的自定义提示；None 用默认文案


@dataclass
class Weight:
    """物品自重（24 号票）。非 Stackable 物品用本组件；Stackable 用 unit_weight*amount。

    两者都不挂时重量视为 0（不参与超重拒绝）。
    """

    value: float = 0.0  # 物品重量；启动固定


# ── NPC / 玩家驱动源组件（块 D，25~29 号票）──────────────────────────
# 玩家与 NPC 挂同一批基础组件（Identity/Description/Position/Container），
# 区别只在驱动源：NPC 挂 ``AIController``，玩家挂 ``PlayerSession``
# （spec 块 D user story 33；28 号票落地）。


@dataclass
class PlayerSession:
    """玩家驱动源标记（US33 / 28 号票）。

    空 marker dataclass：有本组件即视为在线玩家会话实体。与 ``AIController``
    对仗——玩家与 NPC 共用组件池，靠驱动源组件区分。房间广播 / Nature 户外
    推送等"只发给玩家"的路径一律查本组件，不用 Container 启发式。
    """


@dataclass
class AIController:
    """NPC 驱动源标记 + tick 频率（25 号票，D1）。

    挂在需要由引擎 tick 驱动行为的实体上（有行为的 NPC）。``TickLoop.advance``
    经 ``on_tick`` 遍历带本组件的实体，按 ``tick_interval`` 跳过不足间隔的 tick，
    再对其 ``Behaviors`` 逐条调度。玩家与静态展示型 NPC（无行为）不挂本组件。
    """

    tick_interval: int = 1  # 启动固定：每隔多少 tick 评估一次行为；1=每 tick


@dataclass(frozen=True)
class BehaviorSpec:
    """单条行为的声明式规格（纯数据，可序列化；25/29 号票）。

    ``kind`` 区分行为类型（M1 仅 ``"chatter"``；M2 可扩 ``aggro`` 等）。Chatter
    字段（``chat_msgs`` / ``chat_chance`` / ``when``）对其他 kind 可为空。
    ``when`` 是条件表达式的结构化 dict 占位（喂给 ``conditions`` 求值），**不**
    放裸 Python lambda（避坑清单 §F）。形状为未来可变状态进存档留好（§L）。
    """

    kind: str  # 行为类型名，如 "chatter"
    chat_msgs: tuple[str, ...] = ()  # Chatter：闲聊消息列表
    chat_chance: float = 0.0  # Chatter：触发概率 [0, 1]
    when: dict | None = None  # 可选条件（如 {"predicate": "is_night"}）；None=无条件


@dataclass
class Behaviors:
    """行为列表组件：挂在带 ``AIController`` 的实体上（25 号票，D1）。

    ``entries`` 是声明式 ``BehaviorSpec`` 列表；M1 Chatter 无可变状态，但组件
    形状预留未来"对话进度 / 库存计数"等可变态进存档的空间（避坑清单 §L）。
    """

    entries: list[BehaviorSpec] = field(default_factory=list)


@dataclass
class Inquiry:
    """ask 对话的 topic -> 响应字符串映射（27 号票，D3）。

    启动固定（从 YAML 加载后不变）。``default`` 是未知 topic 的兜底文案；
    ``None`` 表示未知 topic 时用引擎内置提示。``handler`` 是可选的
    DialogueHandler 钩子名引用占位（同 ``Equippable.apply_hook``）；M1 不执行，
    供 M2 接入 ``on_topic``，不实现 RestrictedPython。
    """

    topics: dict[str, str] = field(default_factory=dict)  # topic -> 响应文案
    default: str | None = None  # 未知 topic 兜底；None=用引擎内置提示
    handler: str | None = None  # DialogueHandler 钩子名占位；启动固定；M1 未用


@dataclass
class NpcSpawnMeta:
    """NPC 生成/重生元数据（26 号票，D2）。

    场景加载时按模板挂到每个实例上；低频 Spawn/Reset 扫描用 ``template_key``
    聚合并对照 ``desired_count`` / ``respawn``。M1 NPC 不死，扫描多为空转，
    机制地基先埋。``startroom`` 是出生房间（与加载时 ``in_room`` 通常相同）。
    """

    template_key: str  # 启动固定：YAML npcs 段的模板键，如 "stone_guard"
    startroom: EntityId  # 启动固定：出生房间 entity id
    desired_count: int = 1  # 启动固定：该模板期望存活实例数
    respawn: bool = False  # 启动固定：不足 desired_count 时是否补齐


# ── 角色成长（M2-05 / spec B2）──────────────────────────────────────────
# 三个独立组件，不合并成跨领域大杂烩。玩家与 NPC 都可挂（木桩/怪物需 Vitals）。


@dataclass
class Vitals:
    """气血 / 内力 / 精力两层资源（当前值 + 上限）。运行时可变进存档。"""

    qi_current: int
    qi_max: int
    neili_current: int
    neili_max: int
    jingli_current: int
    jingli_max: int


@dataclass
class BaseAttributes:
    """四维基础属性。字段名避开 Python 关键字；展示文案用中文。

    启动固定为主（M2 无改属性命令），仍进存档以便场景初值跨重启保留。
    """

    str_: int = 10  # 力量
    con: int = 10  # 根骨
    dex: int = 10  # 敏捷
    int_: int = 10  # 智力


@dataclass(frozen=True)
class SkillProgress:
    """单技能进度：等级 + 经验。招式内容查全局 ``SKILLS``，不复制。"""

    level: int = 0
    exp: int = 0


@dataclass
class SkillLevels:
    """已学技能表（skill_id -> 进度）。运行时可变进存档。"""

    levels: dict[str, SkillProgress] = field(default_factory=dict)


# ── 死亡状态机标记（M2-06 / spec C1）────────────────────────────────────
# 存活 = 两者都不挂；不新增 Alive，避免三态用两个布尔表达出非法组合。


@dataclass
class Unconscious:
    """昏迷中（marker）。运行时可变进存档。"""


@dataclass
class Dead:
    """死亡、等待复活流程处理（marker）。运行时可变进存档。"""


@dataclass
class NoDeathZone:
    """房间级免死区标记：气血耗尽只昏迷、不转 Dead。启动固定。"""


# ── 货币与商店（M2-07 / spec D1）────────────────────────────────────────


@dataclass
class Currency:
    """单一货币余额（银两）。运行时可变进存档。"""

    amount: int = 0


@dataclass(frozen=True)
class ShopEntry:
    """商店清单一条：物品模板键或坐骑模板键 + 可选定价/回购折扣。

    物品条目：``item_template_key`` 非空，价格取物品 ``Valuable``。
    坐骑条目（M2-10）：``mount_template_key`` 非空，``price`` 必填；买后
    在玩家房间生成坐骑实例（不进物品栏）。二者互斥。
    """

    item_template_key: str | None = None
    mount_template_key: str | None = None
    resell_discount: float = 1.0
    price: int | None = None


@dataclass
class ShopInventory:
    """NPC 商店声明式清单。启动固定（MVP 库存无限，按模板实例化）。"""

    entries: tuple[ShopEntry, ...] = ()


# ── 门派归属（M2-08 / spec E1）──────────────────────────────────────────


@dataclass
class Faction:
    """角色门派归属。``None`` = 无门派。运行时可变进存档。"""

    faction_id: str | None = None


# ── 交战（M2-12 / spec A1）──────────────────────────────────────────────


@dataclass
class Engaged:
    """交战关系：指向当前对手。双方各挂一份互相指向；运行时可变进存档。

    MVP 1 对 1：同一实体同时只允许一份 ``Engaged``。
    """

    opponent: EntityId


# ── 坐骑与骑乘（M2-10 / spec F1）────────────────────────────────────────


@dataclass
class Mount:
    """坐骑能力：通行能力值 + 精力 + 当前骑手。运行时可变进存档（ridden_by）。"""

    ability: int
    jingli_current: int
    jingli_max: int
    ridden_by: EntityId | None = None


@dataclass
class Riding:
    """骑乘中：指向所骑坐骑实体。运行时可变进存档。"""

    mount_id: EntityId


# ── 门槏与身份快照辅助（M2-11 / spec E2）────────────────────────────────


@dataclass
class Gender:
    """性别标记。题材包决定取值集合，引擎不校验枚举。启动固定为主。"""

    value: str


@dataclass(frozen=True)
class ItemTags:
    """物品语义标签（如 weapon/edged），供门槏现算。启动固定。"""

    tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EntryGuard:
    """房间进入门槏：条件 + 拒绝文案。启动固定。

    ``condition`` 存结构化 dict（与 ``condition_from_data`` 同形），求值时再转节点，
    避免 Condition 图进存档时的复杂序列化。
    """

    condition: dict
    deny_message: str


# ── 渡口（M2-09 / spec F2）──────────────────────────────────────────────


@dataclass
class Ferry:
    """渡口房间组件：对岸房间 + 往返周期 + 过河方向名。

    场景加载时不预先建过河 Exit；由 ``attach_ferries`` 的 on_tick 系统按周期
    增删。``far_bank`` 在加载期从房间键解析为 EntityId。
    ``_far_bank_key`` 仅加载中间态（瞬时），解析完成后清空。
    """

    far_bank: EntityId
    cross_interval: int
    direction: str
    _far_bank_key: str | None = transient_field(None)
