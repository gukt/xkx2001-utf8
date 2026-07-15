"""层2：Ink 对话树最小实现（M2-2）。

本次只落地 "inquiry 交易原子节点"：把 NPC 的 ``inquiry`` 从纯文本 reply 扩展为
结构化 ``InquiryNode``，支持条件、副作用、单发与 next_topic 链。运行时不解释完整
Ink 语法，而是把轻量 ``InkStory`` 编译为 ``InquiryNode`` 运行时原子，复用现有
layer1 ``ask`` 路径。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class InquiryNode(BaseModel):
    """inquiry 交易原子节点。

    ``NpcDef.inquiry`` 的值可以是普通字符串（向后兼容）或本节点。运行时 ``ask``
    命中节点后：先检查 ``requires_flag``，再执行 transaction 副作用
    （set/clear flag、给/收物品），最后输出 ``reply``；若 ``next_topic`` 非空，
    自动继续该话题，形成最小对话链。
    """

    reply: str  # 显示给玩家的回复文本
    requires_flag: str = ""  # 玩家须持有此 flag，空=无条件
    sets_flag: str = ""  # 执行后给玩家设的 flag
    clears_flag: str = ""  # 执行后清除的 flag
    gives_item: str = ""  # 执行后给玩家的物品 id
    takes_item: str = ""  # 执行后从玩家物品栏收走的物品 id
    once: bool = False  # 是否只触发一次（触发后从 inquiry 中移除/标记）
    next_topic: str = ""  # 触发后自动继续的下一个话题


class InkChoice(BaseModel):
    """Ink 风格选择支（创作期表示）。"""

    text: str  # 显示给玩家的选项文本
    target: str = ""  # 跳转目标 knot id；空=结束
    condition_flag: str = ""  # 出现该选项需要的 flag
    sets_flag: str = ""  # 选后设 flag
    gives_item: str = ""  # 选后给物品
    takes_item: str = ""  # 选后收物品


class InkNode(BaseModel):
    """Ink knot 内的一个节点（文本 + 选择支）。"""

    text: str
    choices: list[InkChoice] = Field(default_factory=list)
    condition_flag: str = ""  # 本节点出现条件


class InkKnot(BaseModel):
    """Ink knot（一段可跳转的对话片段）。"""

    id: str
    nodes: list[InkNode] = Field(default_factory=list)


class InkStory(BaseModel):
    """轻量 Ink 对话树（创作期表示）。

    通过 ``compile_ink_to_inquiries`` 编译为 ``dict[str, str | InquiryNode]``，
    作为 ``NpcDef.inquiry`` 写入。运行时不直接解释本模型。
    """

    id: str
    start_knot: str
    knots: list[InkKnot] = Field(default_factory=list)


def compile_ink_to_inquiries(story: InkStory) -> dict[str, str | InquiryNode]:
    """把轻量 InkStory 编译为 ``InquiryNode`` 运行时原子字典。

    简单实现：每个 knot 的第一条非条件节点文本作为 topic ``knot/<id>`` 的 reply，
    选择支映射为 ``next_topic`` 链。复杂分支/循环后续按需扩展。
    """
    inquiries: dict[str, str | InquiryNode] = {}
    knot_map = {k.id: k for k in story.knots}
    start_knot = knot_map.get(story.start_knot)
    if start_knot and start_knot.nodes:
        first = start_knot.nodes[0]
        node = InquiryNode(
            reply=first.text,
            next_topic=f"knot/{start_knot.id}/1" if len(start_knot.nodes) > 1 else "",
        )
        inquiries[f"knot/{start_knot.id}"] = node

    for knot in story.knots:
        for idx, node in enumerate(knot.nodes):
            if idx == 0:
                continue
            topic = f"knot/{knot.id}/{idx}"
            if node.choices:
                choice = node.choices[0]
                inquiries[topic] = InquiryNode(
                    reply=node.text,
                    sets_flag=choice.sets_flag,
                    gives_item=choice.gives_item,
                    takes_item=choice.takes_item,
                    next_topic=f"knot/{choice.target}" if choice.target else "",
                )
            else:
                inquiries[topic] = node.text
    return inquiries
