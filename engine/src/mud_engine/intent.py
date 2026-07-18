"""解析阶段的稳定中间表示：意图与结构化解析失败信号。

解析器（文本 -> 意图）的唯一产出物是 ``Intent`` 或一个 ``ParseFailure``；执行
阶段只接收 ``Intent``，不感知原始输入文本或解析器身份（02 号票，见 M1 spec
「命令解析」）。Intent 的形状刻意稳定且通用，使未来接入 AI 兜底解析器时其
输出也能装进同一类型，无需回头改执行层或已有解析器（spec 用户故事 25/26）。

本模块独立成文件、不依赖任何其他引擎模块，是为了让命令调度（commands）与
解析（parsing）都能依赖它而不互相循环依赖。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Reason(Enum):
    """解析失败的分类，供兜底逻辑判断"该不该、能不能接手"。"""

    UNKNOWN_VERB = "unknown_verb"  # 完全无法识别的动词
    NO_TARGET_MATCH = "no_target_match"  # 目标 token 无任何候选命中
    AMBIGUOUS_TARGET = "ambiguous_target"  # 目标 token 同时命中多个候选


@dataclass(frozen=True)
class Intent:
    """一个已解析的动作意图：动词 + 目标引用 + 参数。

    target 是"已解析的规范目标名"（别名已在解析阶段展开）；无目标的命令
    （look/help/quit）为 None。args 是动词位置参数里目标之外的部分，M1
    阶段通常为空，保留字段是为了让形状能装下未来更复杂的意图。
    """

    verb: str
    target: str | None
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParseFailure:
    """结构化的"无法理解"结果：reason 分类 + 原始输入 + 触发命令 + 可选候选。

    解析阶段失败时返回它而非抛异常；形状被测试锁定，供未来兜底解析器判断
    是否接手（spec 用户故事 26）。verb 记录是哪个命令的目标解析失败，让提示
    能按命令给不同措辞（go 的"那个方向"、take 的"这里没有"、drop 的"你没有"）；
    未知动词时 verb 为 None（没识别出动词无从填）。
    """

    reason: Reason
    original: str
    verb: str | None = None
    candidates: tuple[str, ...] = ()


__all__ = ["Intent", "ParseFailure", "Reason"]
