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
- 可见性门控（ADR-0028 决策 2）：PronounContext 求值前过 ``visible`` 门控。viewer 看不到
  target 时，``$n``/``$p``/``$C``/``$c``/``$R``/``$r`` 退化为基础代词（避免泄露隐身目标）。

阶段 1 最小实现（保留）：``rank_relation`` + ``visible``。
阶段 2.5 扩展（ADR-0028 决策 2）：PronounContext 10 变量 + 7 函数委托 title.py +
``build_context`` + ``render`` + ``build_context_for_system``（System tick 回退，决策 4）。

[ADR-0028](../../../docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 2/4
[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md) B 类
[ADR-0014](../../../docs/adr/ADR-0014-daemon-responsibility-redesign.md) 决策 3
[spec/layer_i_character.py](../spec/layer_i_character.py) ``_visible`` viewer/target 语义
"""

from __future__ import annotations

from dataclasses import dataclass
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

    阶段 2.5 实现（ADR-0028 决策 2，补 is_ghost 判定）：

    - target 实体不存在 -> False
    - target 无 Identity 组件 -> False
    - target TitleComp.is_ghost True -> False（无 astral_vision 系统，鬼魂默认不可见；
      2.6 阴间系统补 astral_vision 后鬼魂对有此能力的 viewer 可见）

    完整 invisibility/astral_vision 后置阶段 2.6/M3。
    """
    from xkx.runtime.components import Identity, TitleComp

    ident: Identity | None = world.get(target, Identity)
    if ident is None:
        return False
    # 2.5 补 is_ghost 判定（ADR-0028 决策 2）：鬼魂目标默认不可见
    title = world.get(target, TitleComp)
    is_ghost = title is not None and title.is_ghost
    # TODO 阶段 2.6/M3：补 astral_vision 判定（有 astral_vision 的 viewer 可见鬼魂）
    # TODO 阶段 2.6/M3：补 invisibility > wiz_level(viewer) 判定
    return not is_ghost


# ──────────────────────── gender 代词（对齐 gender.c） ────────────────────────


def gender_self(gender: str) -> str:
    """性别 self 代词（对齐 LPC [gender.c] gender_self，message.c:13）。

    LPC gender_self 恒返回 "你"（所有性别）。保留参数对齐 LPC 签名。
    """
    _ = gender  # LPC gender_self 不分性别，恒 "你"
    return "你"


def gender_pronoun(gender: str) -> str:
    """性别 pronoun 代词（对齐 LPC [gender.c] gender_pronoun，message.c:25）。

    - 男性 / 中性神 / 无性 -> "他"
    - 女性 -> "她"
    - 雄性 / 雌性 / default -> "它"
    """
    if gender in ("男性", "中性神", "无性"):
        return "他"
    if gender == "女性":
        return "她"
    return "它"


# ──────────────────────── PronounContext 10 变量（ADR-0028 决策 2） ────────────────────────


# 10 变量占位符 -> PronounContext 字段名（render 用，对齐 message_vision 扩展到 10 变量）
# 大写=speaker 视角对 target，小写=target 视角对 speaker（角色互换，viewer 翻转）
_PRONOUN_PLACEHOLDERS: list[tuple[str, str]] = [
    ("$N", "name_me"),
    ("$n", "name_you"),
    ("$P", "pronoun_me"),
    ("$p", "pronoun_you"),
    ("$C", "close"),
    ("$c", "close_rev"),
    ("$R", "respect"),
    ("$r", "respect_rev"),
    ("$S", "self"),
    ("$s", "self_rude"),
]

# target 不可见时退化占位（避免泄露隐身目标信息，ADR-0028 决策 2 可见性不变量）
_HIDDEN_NAME = "某人"
_HIDDEN_PRONOUN = "它"
_HIDDEN_RANK = ""


@dataclass(frozen=True, slots=True)
class PronounContext:
    """10 变量代词上下文（服务端预求值，下发前端做纯字符串替换）。

    [00] §渲染下沉：服务端求值 PronounContext，前端只做 $X -> context[X] 替换。
    RANK_D 7 函数是业务逻辑求值（依赖年龄/性别/职业/门派/官职/武功/善恶/鬼魂），
    非纯渲染函数（[_archive/01-v2] §P1）。

    字段对应占位符（ADR-0028 决策 2 表）：

    - ``name_me`` ($N) / ``name_you`` ($n)：speaker/target name（message_vision 4 变量）
    - ``pronoun_me`` ($P) / ``pronoun_you`` ($p)：speaker/target 性别代词
    - ``close`` ($C) / ``close_rev`` ($c)：speaker 看 target / target 看 speaker 的
      亲近称谓（query_close，viewer 翻转）
    - ``respect`` ($R) / ``respect_rev`` ($r)：speaker 看 target / target 看 speaker
      的尊敬称谓（query_respect）
    - ``self`` ($S) / ``self_rude`` ($s)：speaker 自称 / 傲慢自称（query_self/_rude）
    """

    name_me: str
    name_you: str
    pronoun_me: str
    pronoun_you: str
    close: str
    close_rev: str
    respect: str
    respect_rev: str
    self: str  # noqa: A003 - 对齐 $S 占位符字段名（shadow 内置无副作用，dataclass 字段）
    self_rude: str


class PronounService:
    """代词求值服务（对齐 LPC rankd.c，viewer 显式传参）。

    greenfield 无全局 ``this_player()``，所有代词求值函数签名含 ``viewer`` 参数。
    阶段 1 最小：``rank_relation`` + ``visible``（保留）。
    阶段 2.5 扩展（ADR-0028 决策 2）：7 函数委托 ``title.py`` + PronounContext
    构造 + render。
    """

    # ---- 阶段 1 保留（previous_object_map 启动期校验签名含 viewer）----

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

    # ---- 阶段 2.5 扩展：7 函数委托 title.py（ADR-0028 决策 1）----

    @staticmethod
    def query_rank(world: World, target: int) -> str:
        """求 target 等级称谓（委托 title.query_rank，对齐 rankd.c 行 8-320）。"""
        from xkx.runtime import title

        return title.query_rank(world, target)

    @staticmethod
    def query_respect(world: World, target: int) -> str:
        """求 target 尊敬称谓（委托 title.query_respect，行 322-404）。"""
        from xkx.runtime import title

        return title.query_respect(world, target)

    @staticmethod
    def query_rude(world: World, target: int) -> str:
        """求 target 粗鄙称谓（委托 title.query_rude，行 406-461）。"""
        from xkx.runtime import title

        return title.query_rude(world, target)

    @staticmethod
    def query_self(world: World, target: int) -> str:
        """求 target 自称（委托 title.query_self，行 463-513）。"""
        from xkx.runtime import title

        return title.query_self(world, target)

    @staticmethod
    def query_self_rude(world: World, target: int) -> str:
        """求 target 傲慢自称（委托 title.query_self_rude，行 515-569）。"""
        from xkx.runtime import title

        return title.query_self_rude(world, target)

    @staticmethod
    def query_close(world: World, viewer: int, target: int) -> str:
        """求 viewer 看 target 的亲近称谓（委托 title.query_close，行 570-613）。

        观察者相对的二元关系函数（专家 3 承重论断 2），依赖 viewer age。
        """
        from xkx.runtime import title

        return title.query_close(world, viewer, target)

    @staticmethod
    def query_self_close(world: World, viewer: int, target: int) -> str:
        """求 viewer 对 target 的亲近自称（委托 title.query_self_close，行 615-651）。

        gender 取自 viewer（行 630/635）。
        """
        from xkx.runtime import title

        return title.query_self_close(world, viewer, target)

    # ---- PronounContext 构造 + render（ADR-0028 决策 2）----

    @staticmethod
    def build_context(world: World, speaker: int, target: int) -> PronounContext:
        """构造 10 变量 PronounContext（speaker/target 二元，viewer 内部翻转）。

        **$C/$c 角色互换的 viewer 翻转**（决策 2 核心求值规则）：

        - ``$C``（speaker 看 target 亲近称谓）：``query_close(viewer=speaker, target=target)``
        - ``$c``（target 看 speaker 亲近称谓）：``query_close(viewer=target, target=speaker)``

        $R/$r 同理（query_respect 角色互换，但 query_respect 是单实体无 viewer 依赖，
        respect=speaker 看 target=query_respect(target)，respect_rev=target 看 speaker=
        query_respect(speaker)）。

        **可见性门控**（决策 2 不变量）：求值前过 ``visible``。viewer 看不到 target 时，
        $n/$p/$C/$c/$R/$r 退化为基础代词（避免泄露隐身目标）。

        本函数 viewer 默认 = speaker（玩家命令路径 + PrivilegedAction 路径）。
        System tick 路径 viewer 回退 speaker 自身，用 ``build_context_for_system``。
        """
        from xkx.runtime import title
        from xkx.runtime.components import Attributes, Identity

        # speaker 基础代词（$N/$P/$S/$s）
        s_ident = world.get(speaker, Identity)
        s_attrs = world.get(speaker, Attributes)
        s_gender = s_attrs.gender if s_attrs else "男性"
        name_me = s_ident.name if s_ident else ""
        pronoun_me = gender_self(s_gender)
        self_ = title.query_self(world, speaker)
        self_rude = title.query_self_rude(world, speaker)

        # 可见性门控：speaker 看 target
        can_see_target = visible(speaker, target, world)
        if can_see_target:
            t_ident = world.get(target, Identity)
            t_attrs = world.get(target, Attributes)
            t_gender = t_attrs.gender if t_attrs else "男性"
            name_you = t_ident.name if t_ident else ""
            pronoun_you = gender_pronoun(t_gender)
            # $C：speaker 看 target（viewer=speaker）；$c：target 看 speaker（viewer=target）
            close = title.query_close(world, speaker, target)
            close_rev = title.query_close(world, target, speaker)
            respect = title.query_respect(world, target)
            respect_rev = title.query_respect(world, speaker)
        else:
            # 退化：target 不可见，$n/$p/$C/$c/$R/$r 用占位（避免泄露隐身目标）
            name_you = _HIDDEN_NAME
            pronoun_you = _HIDDEN_PRONOUN
            close = _HIDDEN_RANK
            close_rev = _HIDDEN_RANK
            respect = _HIDDEN_RANK
            respect_rev = _HIDDEN_RANK

        return PronounContext(
            name_me=name_me,
            name_you=name_you,
            pronoun_me=pronoun_me,
            pronoun_you=pronoun_you,
            close=close,
            close_rev=close_rev,
            respect=respect,
            respect_rev=respect_rev,
            self=self_,
            self_rude=self_rude,
        )

    @staticmethod
    def build_context_for_system(
        world: World, speaker: int, target: int
    ) -> PronounContext:
        """System tick 路径 PronounContext 构造（ADR-0028 决策 4）。

        System tick 路径无"当前说话者"（无 ActionContext），viewer 回退为 speaker 自身
        （``viewer == speaker``）。语义：System 产生的消息（如 combat 招式文本）speaker
        是行动者，viewer 也是行动者自身。

        **不变量**：System 路径 viewer == speaker，但 ``$C``/``$c`` 内部仍翻转 viewer
        （$C viewer=speaker，$c viewer=target），不因 System 路径而退化。故本函数
        与 ``build_context`` 行为一致（viewer=speaker 已是 build_context 默认），保留
        独立方法以显式标注 System 路径语义 + 便于后续扩展（如 System 路径的可见性
        门控差异）。
        """
        return PronounService.build_context(world, speaker, target)

    @staticmethod
    def render(template: str, ctx: PronounContext) -> str:
        """$X -> ctx 字段纯字符串替换（对齐 message_vision replace_string，扩展 10 变量）。

        10 变量占位符：$N/$n/$P/$p/$C/$c/$R/$r/$S/$s（决策 2 表）。每个占位符唯一，
        无嵌套问题，按顺序 str.replace。前端渲染等价（服务端也可用，[00] §渲染下沉）。
        """
        result = template
        for placeholder, field_name in _PRONOUN_PLACEHOLDERS:
            value = getattr(ctx, field_name)
            result = result.replace(placeholder, value)
        return result
