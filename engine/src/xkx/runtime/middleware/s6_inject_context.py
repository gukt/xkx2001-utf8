"""段 6 previous_object 注入（ADR-0020 决策 1 + ADR-0021 决策 1）。

LPC ``this_player()`` / ``previous_object()`` 信任链显式化为 ActionContext 字段
（ADR-0021）。段 6 确保 actor/source/viewer/target 三元组在段 7 执行前就位。

**不变量**（ADR-0020 决策 2）：

- actor/viewer/source 必须在段 6 注入完成，段 7 执行段可依赖三者已就位。
- PronounContext 求值必须从 ActionContext 取 viewer，不得从全局 this_player() 取。
- 玩家命令路径下 actor == source == viewer（玩家发起命令时三者相同）。
- PrivilegedAction 路径下 actor == viewer（被代执行的玩家），source == 系统调用者。

段 6 阶段 1 最小：验证三元组已就位（new_context 已设默认值），可在此段做 target
解析（如 kill 命令从 parsed_args 解析 target entity_id）。target 解析后置到终端命令
（各命令 target 语义不同），段 6 仅做不变量校验。
"""

from __future__ import annotations

from xkx.runtime.action_context import Abort, ActionContext


def inject_context(ctx: ActionContext) -> ActionContext | Abort:
    """段 6：previous_object 注入（ADR-0020 决策 1 + ADR-0021 决策 1）。

    阶段 1 最小：校验三元组不变量（actor/source/viewer 已就位）。

    - actor 必须 > 0（有效 entity_id）
    - source 默认 = actor（new_context 已设，玩家命令路径）
    - viewer 默认 = actor（new_context 已设，玩家命令路径）
    - target 可为 None（无目标命令）

    段顺序不变量：段 6 必须在段 7 执行前（执行段依赖 actor/source/target）。
    """
    if ctx.actor <= 0:
        return Abort(reason="invalid_actor", messages=["无效的命令发起者。"])
    # source/viewer 默认已在 new_context 设置（= actor），此处仅校验非零
    if ctx.source <= 0:
        return Abort(reason="invalid_source", messages=[])
    if ctx.viewer <= 0:
        return Abort(reason="invalid_viewer", messages=[])
    # PronounContext 不变量：viewer 必须就位（ADR-0021 B 类）
    # 玩家命令路径下 viewer == actor；PrivilegedAction 路径下 viewer == actor
    # （被代执行的玩家是观察者），source == 系统调用者
    return ctx
