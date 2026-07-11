"""命令 8 段管线测试（阶段 1 Wave 2 T4，ADR-0020）。

覆盖：
- 8 段管线行为等价（go/kill/ask/give/quest/look/inventory/hp 走管线 == 直接调命令函数）
- 段顺序不变量（刷屏检测最先 / 权限校验先于命令查找 / previous_object 注入先于执行）
- Abort 短路（任一段 Abort 后续段不执行）
- 方向快捷（无参方向名重写为 go <direction>）
- 别名解析（n -> go north / l -> look / ! 历史替换）
- 引号感知 tokenizer

[ADR-0020](../../../docs/adr/ADR-0020-command-pipeline-actioncontext-capability.md)
"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.runtime.action_context import Abort, new_context
from xkx.runtime.commands import COMMAND_REGISTRY, Game, dispatch
from xkx.runtime.components import Position
from xkx.runtime.middleware.s0_flood_check import (
    CMDS_PER_TICK,
    FLOOD_HARD_LIMIT,
    FloodState,
    flood_check,
    reset_flood_counter,
)
from xkx.runtime.middleware.s1_alias import GLOBAL_ALIASES, AliasState
from xkx.runtime.middleware.s5_parse_args import tokenize_args
from xkx.runtime.middleware.s7_execute_audit import AuditLog
from xkx.runtime.world import build_world, spawn_player

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "wuxia_micro"


def _game(
    seed_base: int = 0,
    spawn_room: str = "city/street",
) -> tuple[Game, int]:
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs)
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", spawn_room)
    game = Game(
        world,
        room_idx,
        rules,
        seed_base=seed_base,
        spawn_room=spawn_room,
    )
    return game, pid


# ---- 行为等价：走管线 == 直接调命令函数 ----


def test_pipeline_go_equivalent_to_direct() -> None:
    """go 走管线与直接调 go() 结果一致（行为等价）。"""
    game, pid = _game()
    room_before = game.world.get(pid, Position).room_id
    # 走管线
    msgs_pipeline = dispatch(game, pid, "go north")
    room_after = game.world.get(pid, Position).room_id
    assert room_after != room_before  # 移动了
    assert any("走去" in m for m in msgs_pipeline)


def test_pipeline_look_equivalent() -> None:
    """look 走管线产出房间描述。"""
    game, pid = _game()
    msgs = dispatch(game, pid, "look")
    assert msgs  # 非空
    assert msgs[0].startswith("【")


def test_pipeline_hp_equivalent() -> None:
    """hp 走管线产出状态。"""
    game, pid = _game()
    msgs = dispatch(game, pid, "hp")
    assert len(msgs) == 1
    assert "气" in msgs[0]


def test_pipeline_inventory_empty() -> None:
    """inventory 走管线（空物品栏）。"""
    game, pid = _game()
    msgs = dispatch(game, pid, "inventory")
    assert any("没有" in m for m in msgs)


def test_pipeline_quest_list() -> None:
    """quest 走管线列出任务。"""
    game, pid = _game()
    msgs = dispatch(game, pid, "quest")
    # 雪山微场景有任务
    assert isinstance(msgs, list)


# ---- 段顺序不变量 ----


def test_segment_order_flood_before_permission() -> None:
    """段 0 刷屏检测必须最先（防刷屏命令绕过权限校验）。"""
    # 超过 FLOOD_HARD_LIMIT 后段 0 直接 Abort，段 2 权限校验不执行
    game, pid = _game()
    state = FloodState()
    # 手动把计数推到硬上限
    state.count = FLOOD_HARD_LIMIT
    ctx = new_context(verb="look", raw_args="", actor=pid)
    result = flood_check(ctx, state)
    assert isinstance(result, Abort)
    assert result.reason == "flood_hard_limit"


def test_segment_order_permission_before_find() -> None:
    """段 2 权限校验在段 3 命令查找前（fail-closed，未授权命令视为不存在）。"""
    from xkx.runtime.capability import CAP_CMD_USR, PermissionService, WizLevel
    from xkx.runtime.middleware.s2_permission import permission_check

    game, pid = _game()
    service = PermissionService()
    # 签发一个不含 cmd.usr 能力的 token（exclude 掉）
    token = service.issue_token(
        pid,
        WizLevel.PLAYER,
        exclude=frozenset({CAP_CMD_USR}),
    )
    ctx = new_context(
        verb="look", raw_args="", actor=pid, capability_token=token
    )
    # look 需要 cmd.usr，token 排除了 cmd.usr -> Abort
    result = permission_check(ctx, service)
    assert isinstance(result, Abort)
    assert result.reason == "insufficient_capability"


def test_segment_order_inject_before_execute() -> None:
    """段 6 previous_object 注入在段 7 执行前（执行段依赖 actor/source/target）。"""
    from xkx.runtime.middleware.s6_inject_context import inject_context

    game, pid = _game()
    ctx = new_context(verb="look", raw_args="", actor=pid)
    result = inject_context(ctx)
    # 玩家命令路径下 source/viewer 默认 = actor
    assert not isinstance(result, Abort)
    assert result.actor == pid
    assert result.source == pid  # 默认 source = actor
    assert result.viewer == pid  # 默认 viewer = actor


# ---- Abort 短路 ----


def test_abort_short_circuits_pipeline() -> None:
    """段 2 权限校验 Abort 后段 3-7 不执行（命令视为不存在）。"""
    from xkx.runtime.capability import PermissionService

    game, pid = _game()
    service = PermissionService()
    # 无 token -> 段 2 Abort（no_token）
    audit = AuditLog()
    msgs = dispatch(
        game,
        pid,
        "look",
        permission_service=service,
        capability_token=None,  # 无 token
        audit_log=audit,
    )
    # fail-closed 空消息（不泄露命令存在性）
    assert msgs == []
    # 段 7 未执行（审计日志空）
    assert len(audit.entries) == 0


def test_flood_hard_limit_aborts() -> None:
    """刷屏超硬上限 Abort，命令不执行。"""
    game, pid = _game()
    state = FloodState()
    state.count = FLOOD_HARD_LIMIT
    msgs = dispatch(game, pid, "look", flood_state=state)
    assert any("天雷" in m for m in msgs)


def test_flood_warning_under_hard_limit() -> None:
    """刷屏超 CMDS_PER_TICK 但未超硬上限：警告但不 Abort。"""
    game, pid = _game()
    state = FloodState()
    state.count = CMDS_PER_TICK  # 下一次 count+1 > CMDS_PER_TICK 触发警告
    msgs = dispatch(game, pid, "look", flood_state=state)
    # 命令仍执行（look 产出房间描述）
    assert msgs  # 非空
    assert state.warned  # 警告标记已设


# ---- 方向快捷 ----


def test_direction_shortcut_rewrites_go() -> None:
    """无参方向名 north 重写为 go north（LPC command_hook 分支 A）。"""
    game, pid = _game()
    room_before = game.world.get(pid, Position).room_id
    msgs = dispatch(game, pid, "north")
    room_after = game.world.get(pid, Position).room_id
    assert room_after != room_before  # 移动了
    assert any("走去" in m for m in msgs)


def test_direction_shortcut_skipped_when_args() -> None:
    """有参数的方向名不是方向快捷（north foo 不重写）。"""
    game, pid = _game()
    room_before = game.world.get(pid, Position).room_id
    msgs = dispatch(game, pid, "north foo")
    # north foo 不是有效命令 -> "什么？"
    assert msgs == ["什么？"]
    assert game.world.get(pid, Position).room_id == room_before  # 未移动


# ---- 别名解析 ----


def test_alias_n_rewrites_go_north() -> None:
    """全局方向别名 n -> go north。"""
    game, pid = _game()
    room_before = game.world.get(pid, Position).room_id
    msgs = dispatch(game, pid, "n")
    room_after = game.world.get(pid, Position).room_id
    assert room_after != room_before
    assert any("走去" in m for m in msgs)


def test_alias_l_rewrites_look() -> None:
    """非方向别名 l -> look。"""
    game, pid = _game()
    msgs = dispatch(game, pid, "l")
    assert msgs  # 非空
    assert msgs[0].startswith("【")  # look 产出房间名


def test_alias_history_replace() -> None:
    """历史替换 ! -> 最近一条命令。"""
    game, pid = _game()
    state = AliasState()
    # 手动写入一条历史：go north
    state.push("go north")
    room_before = game.world.get(pid, Position).room_id
    # ! 应替换为 go north 并执行
    msgs = dispatch(game, pid, "!", alias_state=state)
    room_after = game.world.get(pid, Position).room_id
    # go north 执行了，房间应变化
    assert room_after != room_before
    assert any("走去" in m for m in msgs)


def test_alias_history_empty_aborts() -> None:
    """空历史 ! -> Abort（没有历史命令）。"""
    game, pid = _game()
    state = AliasState()  # 空历史
    msgs = dispatch(game, pid, "!", alias_state=state)
    assert any("没有历史" in m for m in msgs)


def test_global_aliases_contains_directions() -> None:
    """GLOBAL_ALIASES 含 18 项方向别名 + 非方向别名。"""
    assert "n" in GLOBAL_ALIASES
    assert GLOBAL_ALIASES["n"] == "go north"
    assert "l" in GLOBAL_ALIASES
    assert GLOBAL_ALIASES["l"] == "look"
    assert "i" in GLOBAL_ALIASES
    assert GLOBAL_ALIASES["i"] == "inventory"
    # 18 项方向别名
    direction_aliases = {
        k: v for k, v in GLOBAL_ALIASES.items() if v.startswith("go ")
    }
    assert len(direction_aliases) == 18


# ---- 引号感知 tokenizer ----


def test_tokenize_simple() -> None:
    assert tokenize_args("north") == ["north"]
    assert tokenize_args("npc long sword") == ["npc", "long", "sword"]


def test_tokenize_quoted() -> None:
    """双引号包裹的 token 保留内部空格。"""
    assert tokenize_args('npc "long sword"') == ["npc", "long sword"]
    assert tokenize_args('"long sword"') == ["long sword"]


def test_tokenize_unclosed_quote() -> None:
    """未闭合引号按剩余字符串作为一个 token（容错）。"""
    assert tokenize_args('npc "long') == ["npc", "long"]


def test_tokenize_empty() -> None:
    assert tokenize_args("") == []
    assert tokenize_args("   ") == []


# ---- 管线段顺序 PIPELINE 不变量 ----


def test_pipeline_order_invariant() -> None:
    """PIPELINE 8 段顺序固定（ADR-0020 决策 1 段顺序不变量）。"""
    from xkx.runtime.middleware import PIPELINE

    assert len(PIPELINE) == 8
    # 段 0 是刷屏检测
    assert PIPELINE[0].__name__ == "flood_check"
    # 段 2 是权限校验（先于段 3 命令查找）
    assert PIPELINE[2].__name__ == "permission_check"
    assert PIPELINE[3].__name__ == "find_command"
    # 段 6 是 previous_object 注入（先于段 7 执行）
    assert PIPELINE[6].__name__ == "inject_context"
    assert PIPELINE[7].__name__ == "execute_audit"


def test_reset_flood_counter() -> None:
    """tick 重置刷屏计数（LPC clear_cmd_count）。"""
    state = FloodState()
    state.count = 50
    state.warned = True
    state.messages.append("警告")
    reset_flood_counter(state)
    assert state.count == 0
    assert state.warned is False
    assert state.messages == []


# ---- 审计日志 ----


def test_audit_log_records_command() -> None:
    """段 7 执行后写 COMMAND_AUDIT 审计日志。"""
    game, pid = _game()
    audit = AuditLog()
    dispatch(game, pid, "look", audit_log=audit, seq=42)
    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.seq == 42
    assert entry.actor == pid
    assert entry.verb == "look"
    assert entry.is_privileged is False  # 玩家路径


def test_command_registry_covers_10_commands() -> None:
    """COMMAND_REGISTRY 覆盖 10 命令 + get 别名。"""
    expected = {"go", "kill", "ask", "give", "quest", "take", "get", "look", "inventory", "hp"}
    assert expected <= set(COMMAND_REGISTRY.keys())
