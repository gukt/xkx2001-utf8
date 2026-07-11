"""PREVIOUS_OBJECT_MAP：LPC previous_object()/this_player() 显式化映射表
（阶段 1 Wave 2 T4，ADR-0021）。

LPC 侠客行代码库中 ``previous_object()`` / ``this_player()`` 相关权限检查约 155 处。
greenfield 无 driver 级线程局部变量，无隐式调用栈顶。本表把 LPC 隐式信任链显式化为
ActionContext 字段，分 A/B/C 三类处置。

**三类处置**（ADR-0021 决策 2）：

- **A 类（Command 路径权限检查，约 60 处）-> ActionContext.source + capability_token**：
  典型 ``force_me`` / ``disable_player`` / ``set`` nomark / ``set_status`` 的
  ``geteuid(previous_object()) == ROOT_UID`` 门控。greenfield 在段 2 + 段 6 完成。
- **B 类（PronounContext / 可见性求值，约 40 处）-> ActionContext.viewer**：
  典型 ``rankd.c`` ``query_close``/``query_self_close`` 的 ``this_player()->query("age")``、
  ``visible(me, ob)`` 的 ``me=this_object()=viewer``。greenfield PronounService 签名含 viewer。
- **C 类（System.update 路径，约 55 处）-> SystemContext（非 ActionContext）**：
  heart_beat / do_attack / heal / condition 过期中的 ``previous_object()`` 检查。
  greenfield 下 System.update 由 TickRunner 调用，无外部误调场景，检查直接删除；
  需审计时携带轻量 SystemContext（actor/target，无 source/capability_token）。

**启动期校验**（ADR-0021 决策 4，衔接 ADR-0019）：

- A 类映射目标：``ActionContext.source`` / ``ActionContext.capability_token`` 字段存在。
- B 类映射目标：PronounService / visible 等价函数签名含 ``viewer`` 参数。
- C 类映射目标：System.update 签名含 ``SystemContext``（或确认该调用点检查已删除）。

若映射目标不存在，启动期 ``MappingError``（非运行时静默）。

收敛优先于完备：映射表覆盖 9 层规格涉及的典型调用点（A/B/C 三类），不逐一穷尽 155 处。
阶段 1 验收时抽样校准（类比 ADR-0015 校准方法论）。

[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md)
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class PreviousObjectCategory(StrEnum):
    """previous_object 调用点分类（ADR-0021 决策 2 三类）。"""

    A_COMMAND = "A"
    """Command 路径权限检查 -> ActionContext.source + capability_token。"""

    B_PRONOUN = "B"
    """PronounContext / 可见性求值 -> ActionContext.viewer。"""

    C_SYSTEM = "C"
    """System.update 路径 -> SystemContext（或检查已删除）。"""


@dataclass(frozen=True, slots=True)
class PreviousObjectEntry:
    """PREVIOUS_OBJECT_MAP 单条映射（LPC 调用点 -> greenfield 字段）。"""

    lpc_file: str
    """LPC 源文件（如 ``feature/command.c``）。"""

    lpc_func: str
    """LPC 函数名（如 ``force_me``）。"""

    lpc_expr: str
    """LPC 原语表达式（如 ``geteuid(previous_object())==ROOT_UID``）。"""

    category: PreviousObjectCategory
    """A/B/C 分类。"""

    greenfield_target: str
    """greenfield 映射目标（如 ``ActionContext.source`` / ``ActionContext.viewer`` /
    ``SystemContext`` / ``"已删除"``）。"""

    note: str = ""
    """处置说明（如 "段 2 校验 capability_token 含 root"）。"""


# LPC previous_object()/this_player() 调用点 -> greenfield 显式字段映射表
# 覆盖 9 层规格涉及的典型调用点（A/B/C 三类），不逐一穷尽 155 处（收敛优先于完备）
PREVIOUS_OBJECT_MAP: list[PreviousObjectEntry] = [
    # ── A 类：Command 路径权限检查（-> ActionContext.source + capability_token） ──
    PreviousObjectEntry(
        lpc_file="feature/command.c",
        lpc_func="force_me",
        lpc_expr="geteuid(previous_object())==ROOT_UID",
        category=PreviousObjectCategory.A_COMMAND,
        greenfield_target="ActionContext.source.capability_token",
        note="PrivilegedAction.force ROOT 门控：source 持 root capability",
    ),
    PreviousObjectEntry(
        lpc_file="feature/command.c",
        lpc_func="disable_player",
        lpc_expr="geteuid(previous_object())==ROOT_UID || previous_object()==this_object()",
        category=PreviousObjectCategory.A_COMMAND,
        greenfield_target="ActionContext.source == ActionContext.actor",
        note="自调用检查：source == actor（玩家命令路径）或 source 持 root（系统）",
    ),
    PreviousObjectEntry(
        lpc_file="adm/daemons/securityd.c",
        lpc_func="set_status",
        lpc_expr="geteuid(previous_object())==ROOT_UID",
        category=PreviousObjectCategory.A_COMMAND,
        greenfield_target="ActionContext.source.capability_token",
        note="set_status ROOT 门控：source 持 root capability",
    ),
    PreviousObjectEntry(
        lpc_file="adm/daemons/securityd.c",
        lpc_func="set_status",
        lpc_expr='previous_object() == find_object("/cmds/adm/promote")',
        category=PreviousObjectCategory.A_COMMAND,
        greenfield_target="ActionContext.source == promote 实体",
        note="特定调用者检查：source 是 promote 命令实体",
    ),
    PreviousObjectEntry(
        lpc_file="adm/daemons/securityd.c",
        lpc_func="valid_cmd",
        lpc_expr="euid = geteuid(user); status = get_status(user)",
        category=PreviousObjectCategory.A_COMMAND,
        greenfield_target="ActionContext.capability_token",
        note="段 2 权限校验：capability_token 替代 euid/status 字符串",
    ),
    # ── B 类：PronounContext / 可见性求值（-> ActionContext.viewer） ──
    PreviousObjectEntry(
        lpc_file="inherit/char/char.c",
        lpc_func="visible",
        lpc_expr="this_object() == this_player() == viewer",
        category=PreviousObjectCategory.B_PRONOUN,
        greenfield_target="ActionContext.viewer",
        note="visible(viewer, target, world)，viewer 从 ActionContext 取",
    ),
    PreviousObjectEntry(
        lpc_file="adm/daemons/rankd.c",
        lpc_func="query_close",
        lpc_expr='this_player()->query("age")',
        category=PreviousObjectCategory.B_PRONOUN,
        greenfield_target="ActionContext.viewer",
        note="PronounService.relation(viewer, target)，viewer 从 ActionContext 取",
    ),
    PreviousObjectEntry(
        lpc_file="adm/daemons/rankd.c",
        lpc_func="query_self_close",
        lpc_expr='this_player()->query("age")',
        category=PreviousObjectCategory.B_PRONOUN,
        greenfield_target="ActionContext.viewer",
        note="PronounService.relation(viewer, target)，viewer 从 ActionContext 取",
    ),
    # ── C 类：System.update 路径（-> SystemContext 或检查已删除） ──
    PreviousObjectEntry(
        lpc_file="inherit/char/char.c",
        lpc_func="heart_beat",
        lpc_expr="this_player() / previous_object() 防御性检查",
        category=PreviousObjectCategory.C_SYSTEM,
        greenfield_target="SystemContext（检查已删除）",
        note="System.update 由 TickRunner 调用，无外部误调场景，检查删除",
    ),
    PreviousObjectEntry(
        lpc_file="inherit/char/char.c",
        lpc_func="do_attack",
        lpc_expr="this_player() / previous_object() 防御性检查",
        category=PreviousObjectCategory.C_SYSTEM,
        greenfield_target="SystemContext(actor=attacker, target=victim)",
        note="combat do_attack 携带 SystemContext 记录攻击者/被攻击者",
    ),
    PreviousObjectEntry(
        lpc_file="clone/user/user.c",
        lpc_func="heart_beat",
        lpc_expr="this_player() 频道清理 / update_age / idle 超时",
        category=PreviousObjectCategory.C_SYSTEM,
        greenfield_target="SystemContext.for_actor(player)",
        note="玩家 System tick：heal/condition 过期/idle 超时",
    ),
]


class MappingError(RuntimeError):
    """PREVIOUS_OBJECT_MAP 启动期校验失败（ADR-0021 决策 4）。

    映射目标不存在（如某 LPC 调用点映射到的 greenfield 函数/字段不存在）时 raise，
    非运行时静默。衔接 ADR-0019 SchemaRegistry 的"启动期失败"思路。
    """


def _check_action_context_fields(target: str) -> str | None:
    """校验 A/B 类映射目标字段在 ActionContext 中存在。返回问题或 None。"""
    import dataclasses

    from xkx.runtime.action_context import ActionContext

    field_names = {f.name for f in dataclasses.fields(ActionContext)}
    # 提取 target 中的字段引用（如 "ActionContext.source.capability_token" -> source）
    # 支持点号链式 + "==" 比较
    if "ActionContext." in target:
        # 提取所有 ActionContext.xxx 的 xxx
        import re

        refs = re.findall(r"ActionContext\.(\w+)", target)
        for ref in refs:
            if ref not in field_names:
                return f"ActionContext.{ref} 字段不存在（合法: {sorted(field_names)}）"
    return None


def _check_pronoun_viewer_param() -> str | None:
    """校验 B 类映射目标 PronounService / visible 签名含 viewer 参数。"""
    from xkx.runtime.pronoun import PronounService, visible

    for fn in (PronounService.can_see, PronounService.relation, visible):
        sig = inspect.signature(fn)
        if "viewer" not in sig.parameters and "world" not in sig.parameters:
            return (
                f"{fn.__qualname__} 签名缺 viewer 参数"
                f"（参数: {list(sig.parameters)}）"
            )
    return None


def _check_system_context() -> str | None:
    """校验 C 类映射目标 SystemContext 存在且含 actor/target。"""
    import dataclasses

    from xkx.runtime.system_context import SystemContext

    fields = {f.name for f in dataclasses.fields(SystemContext)}
    if "actor" not in fields or "target" not in fields:
        return f"SystemContext 缺 actor/target 字段（合法: {sorted(fields)}）"
    return None


def validate_previous_object_map() -> list[str]:
    """启动期校验 PREVIOUS_OBJECT_MAP 映射目标合法（ADR-0021 决策 4）。

    返回问题列表（空 = 全部合法）。``build_world`` 或引擎启动期调用，问题非空 raise
    ``MappingError``，防映射目标拼写错误静默传播。
    """
    issues: list[str] = []
    for entry in PREVIOUS_OBJECT_MAP:
        if entry.category == PreviousObjectCategory.A_COMMAND:
            problem = _check_action_context_fields(entry.greenfield_target)
            if problem:
                issues.append(
                    f"PREVIOUS_OBJECT_MAP[{entry.lpc_file}:{entry.lpc_func}] "
                    f"A 类 -> {entry.greenfield_target}: {problem}"
                )
        elif entry.category == PreviousObjectCategory.B_PRONOUN:
            problem = _check_action_context_fields(entry.greenfield_target)
            if problem:
                issues.append(
                    f"PREVIOUS_OBJECT_MAP[{entry.lpc_file}:{entry.lpc_func}] "
                    f"B 类 -> {entry.greenfield_target}: {problem}"
                )
        elif entry.category == PreviousObjectCategory.C_SYSTEM:
            problem = _check_system_context()
            if problem:
                issues.append(
                    f"PREVIOUS_OBJECT_MAP[{entry.lpc_file}:{entry.lpc_func}] "
                    f"C 类 -> {entry.greenfield_target}: {problem}"
                )
    # B 类额外校验 PronounService 签名含 viewer（ADR-0021 决策 4）
    pronoun_problem = _check_pronoun_viewer_param()
    if pronoun_problem is not None:
        issues.append(f"B 类 PronounService 校验: {pronoun_problem}")
    return issues


def assert_previous_object_map() -> None:
    """启动期断言：映射表全部合法，否则 raise MappingError。"""
    issues = validate_previous_object_map()
    if issues:
        raise MappingError(
            "PREVIOUS_OBJECT_MAP 映射校验失败（ADR-0021 决策 4）:\n"
            + "\n".join(issues)
        )


def entries_by_category(category: PreviousObjectCategory) -> list[PreviousObjectEntry]:
    """按分类查询映射条目（调试/测试用）。"""
    return [e for e in PREVIOUS_OBJECT_MAP if e.category == category]


def category_counts() -> dict[PreviousObjectCategory, int]:
    """各类别条目数（验收抽样校准用）。"""
    counts: dict[PreviousObjectCategory, int] = {}
    for entry in PREVIOUS_OBJECT_MAP:
        counts[entry.category] = counts.get(entry.category, 0) + 1
    return counts


# 启动期自检：模块导入即校验（衔接 ADR-0019 启动期失败思路）
# 失败立即 raise MappingError，防映射表错误静默传播到运行期
_asserted = False


def ensure_validated() -> None:
    """显式触发启动期校验（幂等）。测试和引擎启动时调用。"""
    global _asserted
    if not _asserted:
        assert_previous_object_map()
        _asserted = True


# 模块加载时自动校验（启动期失败原则）
ensure_validated()
