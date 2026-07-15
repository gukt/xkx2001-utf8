"""layer2 Ink 对话树最小实现测试（M2-2）：InquiryNode + 运行时 transaction。"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import NpcDef, load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.dsl.layer2 import (
    InkChoice,
    InkKnot,
    InkNode,
    InkStory,
    InquiryNode,
    compile_ink_to_inquiries,
)
from xkx.runtime.commands import Game, ask
from xkx.runtime.components import Identity, Inventory, Marks, NpcBehavior
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _game_with_inquiry(inquiry: dict[str, str | InquiryNode]) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    npcs[0] = NpcDef(**{**npcs[0].model_dump(), "inquiry": inquiry})
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", "xueshan/shanmen")
    return Game(world, room_idx, rules), pid


def _find_gelunbu_behavior(game: Game) -> NpcBehavior:
    for eid in game.world.entities_in_room("xueshan/shanmen"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            behavior = game.world.get(eid, NpcBehavior)
            if behavior is not None:
                return behavior
    raise RuntimeError("找不到测试 NPC")


def test_inquiry_node_yaml_round_trip() -> None:
    """InquiryNode 可被 pydantic 序列化/反序列化。"""
    node = InquiryNode(reply="给你", gives_item="coin", once=True)
    data = node.model_dump()
    restored = InquiryNode(**data)
    assert restored.reply == "给你"
    assert restored.gives_item == "coin"
    assert restored.once is True


def test_inquiry_node_gives_item() -> None:
    """ask 命中 InquiryNode 时执行 gives_item 副作用。"""
    game, pid = _game_with_inquiry({
        "供奉": InquiryNode(reply="这是供品。", gives_item="suyou_guan"),
    })
    msgs = ask(game, pid, "葛伦布", "供奉")
    assert msgs == ["这是供品。"]
    assert "suyou_guan" in game.world.get(pid, Inventory).items


def test_inquiry_node_takes_item() -> None:
    """ask 命中 InquiryNode 时执行 takes_item 副作用。"""
    game, pid = _game_with_inquiry({
        "献礼": InquiryNode(reply="收下了。", takes_item="coin"),
    })
    game.world.get(pid, Inventory).items.add("coin")
    ask(game, pid, "葛伦布", "献礼")
    assert "coin" not in game.world.get(pid, Inventory).items


def test_inquiry_node_requires_flag() -> None:
    """InquiryNode.requires_flag 未满足时返回摇头。"""
    game, pid = _game_with_inquiry({
        "密语": InquiryNode(reply="暗号对上了。", requires_flag="secret"),
    })
    msgs = ask(game, pid, "葛伦布", "密语")
    assert any("摇了" in m for m in msgs)


def test_inquiry_node_sets_flag_and_chain() -> None:
    """InquiryNode 设 flag 后通过 next_topic 进入下一节点。"""
    game, pid = _game_with_inquiry({
        "入门": InquiryNode(
            reply="你愿入我门？",
            sets_flag="pending/join",
            next_topic="确认",
        ),
        "确认": InquiryNode(reply="既入门，当守规矩。"),
    })
    msgs = ask(game, pid, "葛伦布", "入门")
    assert "你愿入我门？" in msgs
    assert "既入门，当守规矩。" in msgs
    assert "pending/join" in game.world.get(pid, Marks).flags


def test_inquiry_node_once_removed() -> None:
    """once=True 的节点触发后从 inquiry 中移除。"""
    game, pid = _game_with_inquiry({
        "机缘": InquiryNode(reply="仅此一次。", once=True),
    })
    behavior = _find_gelunbu_behavior(game)
    ask(game, pid, "葛伦布", "机缘")
    assert "机缘" not in behavior.inquiry


def test_inquiry_node_cycle_guard() -> None:
    """next_topic 成环时 visited 集合防止无限递归。"""
    game, pid = _game_with_inquiry({
        "a": InquiryNode(reply="A", next_topic="b"),
        "b": InquiryNode(reply="B", next_topic="a"),
    })
    msgs = ask(game, pid, "葛伦布", "a")
    assert "A" in msgs
    assert msgs.count("A") == 1


def test_compile_ink_to_inquiries() -> None:
    """轻量 InkStory 可编译为 InquiryNode 字典。"""
    story = InkStory(
        id="test",
        start_knot="start",
        knots=[
            InkKnot(
                id="start",
                nodes=[
                    InkNode(
                        text="你要什么？",
                        choices=[InkChoice(text="coin", target="")],
                    ),
                ],
            ),
        ],
    )
    inquiries = compile_ink_to_inquiries(story)
    assert "knot/start" in inquiries
    node = inquiries["knot/start"]
    assert isinstance(node, InquiryNode)
    assert node.reply == "你要什么？"


def test_plain_string_inquiry_still_works() -> None:
    """纯字符串 inquiry 保持向后兼容。"""
    game, pid = _game_with_inquiry({"你好": "你好。"})
    msgs = ask(game, pid, "葛伦布", "你好")
    assert msgs == ["你好。"]
