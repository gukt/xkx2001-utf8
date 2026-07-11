"""PronounService：代词求值 + 可见性判定（阶段 1 Wave 2 T4，ADR-0021 B 类）。

LPC ``rankd.c`` 的 ``query_close``/``query_self_close`` 依赖 ``this_player()->query("age")``
决定称呼（长辈/平辈/晚辈），``visible(me, ob)`` 中 ``me=this_object()=viewer`` 判定 ``ob``
是否可见。greenfield 无全局 ``this_player()``，viewer 必须显式传参（PronounContext 不变量，
CLAUDE.md 关键不变量）。

**不变量**：

- PronounContext 求值（rankd 代词 / visible 可见性）必须从 ActionContext/SystemContext
  取 viewer，不得从全局 ``this_player()`` 取。
- 三元组 speaker/viewer/target：speaker 是说话者，viewer 是观察者，target 是被谈论对象。
  玩家命令路径下 viewer == actor；PrivilegedAction 路径下 viewer == actor（被代执行者）。

阶段 1 最小实现：

- ``rank_relation``：按 age 判定辈分关系（长辈/平辈/晚辈），对齐 LPC ``query_close`` 语义。
- ``visible``：对齐 LPC ``visible(me, ob)``，viewer 看 target 是否可见。阶段 1 最小集
  （无隐身/鬼魂，仅判定实体存在 + 玩家/NPC 差异），完整 invisibility/ghost 后置。

[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md) B 类
[ADR-0014](../../../docs/adr/ADR-0014-daemon-responsibility-redesign.md) 决策 3
[spec/layer_i_character.py](../spec/layer_i_character.py) ``_visible`` viewer/target 语义
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xkx.runtime.components import Attributes, Identity
    from xkx.runtime.ecs import World


class RankRelation(StrEnum):
    """辈分关系（对齐 LPC rankd.c query_close 长辈/平辈/晚辈）。"""

    ELDER = "elder"
    """长辈（target age > viewer age + 阈值）。"""

    PEER = "peer"
    """平辈（年龄相近）。"""

    JUNIOR = "junior"
    """晚辈（target age < viewer age - 阈值）。"""


# 辈分判定年龄阈值（对齐 LPC rankd.c query_close 的年龄差判定）
# 阶段 1 最小：年龄差 >= 5 视为长辈/晚辈，否则平辈
RANK_AGE_THRESHOLD = 5


def rank_relation(
    viewer_age: int, target_age: int, *, threshold: int = RANK_AGE_THRESHOLD
) -> RankRelation:
    """判定 viewer 与 target 的辈分关系（对齐 LPC rankd.c query_close）。

    ``viewer_age`` 来自 ``this_player()->query("age")``（greenfield 从 ActionContext.viewer
    的 Attributes.age 取）。target 比 viewer 年长 ``threshold`` 岁以上 -> 长辈；
    年轻 ``threshold`` 岁以上 -> 晚辈；否则平辈。
    """
    diff = target_age - viewer_age
    if diff >= threshold:
        return RankRelation.ELDER
    if diff <= -threshold:
        return RankRelation.JUNIOR
    return RankRelation.PEER


def visible(viewer: int, target: int, world: World) -> bool:
    """判定 viewer 能否看到 target（对齐 LPC visible(me, ob)，ADR-0021 B 类）。

    LPC ``visible(me, ob)`` 中 ``me=this_object()=viewer``，``ob=target``。
    判定优先级（LPC）：(1) 巫师等级 > (2) invisibility 属性 > (3) 鬼魂状态。

    阶段 1 最小实现（invisibility/ghost 后置）：

    - target 实体不存在 -> False
    - target 无 Identity 组件 -> False
    - 其余默认可见（无隐身/鬼魂系统）

    完整 invisibility/ghost/astral_vision 后置阶段 2/M3。
    """
    from xkx.runtime.components import Identity

    ident: Identity | None = world.get(target, Identity)
    # 阶段 1 最小：无 invisibility/ghost 系统，有 Identity 即可见
    # TODO 阶段 2/M3：补 invisibility > wiz_level(viewer) 判定 + is_ghost/astral_vision
    return ident is not None


class PronounService:
    """代词求值服务（对齐 LPC rankd.c，viewer 显式传参）。

    greenfield 无全局 ``this_player()``，所有代词求值函数签名含 ``viewer`` 参数。
    阶段 1 最小：``rank_relation`` + ``visible``，完整代词映射（你/他/前辈/晚辈）后置。
    """

    @staticmethod
    def relation(
        world: World, viewer: int, target: int, *, threshold: int = RANK_AGE_THRESHOLD
    ) -> RankRelation | None:
        """求 viewer 看 target 的辈分关系（对齐 rankd.c query_close）。

        从 ``ActionContext.viewer`` 的 ``Attributes.age`` 取 viewer 年龄，
        从 target 的 ``Attributes.age`` 取 target 年龄。任一缺失返回 None。
        """
        from xkx.runtime.components import Attributes

        va: Attributes | None = world.get(viewer, Attributes)
        ta: Attributes | None = world.get(target, Attributes)
        if va is None or ta is None:
            return None
        return rank_relation(va.age, ta.age, threshold=threshold)

    @staticmethod
    def can_see(world: World, viewer: int, target: int) -> bool:
        """求 viewer 能否看到 target（对齐 visible(me, ob)）。"""
        return visible(viewer, target, world)
