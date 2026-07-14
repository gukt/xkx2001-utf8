"""拜师系统单元测试（M3-1 ADR-0032 决策 1）。

覆盖 FamilyComp 组件 + bai/kneel/recruit/betrayer 命令 + attempt_apprentice
声明式入门条件求值。行为等价对照 LPC：

- [feature/apprentice.c](../../feature/apprentice.c)：is_apprentice_of /
  recruit_apprentice / assign_apprentice
- [cmds/skill/apprentice.c](../../cmds/skill/apprentice.c)：bai 命令主流程
- [kungfu/class/xueshan/gongcang.c](../../kungfu/class/xueshan/gongcang.c)：
  attempt_apprentice 入门条件（拒女徒 / 外派高手）+ do_kneel 剃度
"""

from __future__ import annotations

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import (
    ApprenticeConditions,
    ApprenticeDef,
    KneelDef,
    NpcDef,
    RoomDef,
)
from xkx.runtime.commands import Game, _is_apprentice_of, bai, betrayer, kneel, recruit
from xkx.runtime.components import (
    Attributes,
    FamilyComp,
    Identity,
    Marks,
    NpcBehavior,
    Progression,
    Skills,
    TitleComp,
)
from xkx.runtime.world import build_world, spawn_player


def _gongcang_npc() -> NpcDef:
    """雪山派贡藏师傅 NPC（对照 kungfu/class/xueshan/gongcang.c）。

    create_family("雪山派", 12, "弟子") + attempt_apprentice（拒女徒 + 外派高手
    combat_exp>=10000 拒绝，允许雪山派/血刀门）+ do_kneel 剃度（set class=lama）。
    """
    return NpcDef(
        id="xueshan/gongcang",
        name="贡藏",
        aliases=["gong cang", "gongcang"],
        gender="男性",
        apprentice=ApprenticeDef(
            family_name="雪山派",
            generation=12,
            title="弟子",
            conditions=ApprenticeConditions(
                reject_gender="女性",
                allow_families=["雪山派", "血刀门"],
                other_family_max_combat_exp=10000,
            ),
            kneel=KneelDef(
                set_class="lama",
                require_flag="pending/join_lama",
                message="贡藏伸出手掌，在你头顶轻轻地摩挲了几下，将你的头发尽数剃去。",
            ),
            success_message="贡藏说道：好吧，我就收下你了，可不要忘了去度母殿敬奉酥油。",
        ),
    )


def _game(
    *,
    npc: NpcDef | None = None,
    player_family: str = "",
    combat_exp: int = 500,
    gender: str = "男性",
    skills: dict[str, int] | None = None,
    flags: set[str] | None = None,
    player_generation: int = 13,
) -> tuple[Game, int]:
    """构建测试场景：1 房间 + 师傅 NPC + 玩家（可调属性/门派/标记）。"""
    npc = npc or _gongcang_npc()
    room = RoomDef(id="room/test", short="测试房", long="测试房间。", objects={npc.id: 1})
    ir = compile_scene([room], [npc])
    world, room_idx, _ = build_world(ir)
    pid = spawn_player(world, "玩家", "room/test")
    attrs = world.get(pid, Attributes)
    if attrs:
        attrs.gender = gender
        if player_family:
            attrs.family = player_family
    prog = world.get(pid, Progression)
    if prog:
        prog.combat_exp = combat_exp
    if player_family:
        fam = world.get(pid, FamilyComp)
        if fam:
            fam.family_name = player_family
            fam.generation = player_generation
    if skills:
        sk = world.get(pid, Skills)
        if sk:
            sk.levels.update(skills)
    if flags:
        marks = world.get(pid, Marks)
        if marks:
            marks.flags.update(flags)
    return Game(world, room_idx, rules=[]), pid


def _master_eid(game: Game) -> int:
    """找房间内的师傅 NPC eid。"""
    for eid in game.world.entities_in_room("room/test"):
        ident = game.world.get(eid, Identity)
        if ident and not ident.is_player:
            return eid
    raise AssertionError("师傅 NPC 未找到")


# ──────────────────────── FamilyComp 组件 + 序列化 ────────────────────────


def test_familycomp_fields_and_serialization() -> None:
    """FamilyComp 7 字段 + betrayer，可序列化往返（ADR-0022 崩溃安全）。"""
    from xkx.runtime.schema import SchemaRegistry
    from xkx.runtime.serialization import deserialize_component, serialize_component

    schema = SchemaRegistry.with_builtins()
    assert schema.has_field(FamilyComp, "family_name")
    assert schema.has_field(FamilyComp, "betrayer")
    fam = FamilyComp(
        family_name="雪山派",
        generation=13,
        master_id="xueshan/gongcang",
        master_name="贡藏",
        title="弟子",
        privs=0,
        betrayer=1,
    )
    data = serialize_component(fam)
    assert data["family_name"] == "雪山派"
    assert data["generation"] == 13
    assert data["betrayer"] == 1
    assert deserialize_component(FamilyComp, data) == fam


def test_apprentice_config_compiled_to_npc() -> None:
    """NpcDef.apprentice 编译到 IR + spawn 衔接：NPC 有 FamilyComp + apprentice_config。"""
    game, _ = _game()
    eid = _master_eid(game)
    fam = game.world.get(eid, FamilyComp)
    behavior = game.world.get(eid, NpcBehavior)
    assert fam is not None and behavior is not None
    # 师傅自己的 family（create_family 语义，privs=-1 全部权限）
    assert fam.family_name == "雪山派"
    assert fam.generation == 12
    assert fam.title == "弟子"
    assert fam.privs == -1
    # apprentice_config 来自 NpcDef.apprentice model_dump
    assert behavior.apprentice_config is not None
    assert behavior.apprentice_config["family_name"] == "雪山派"
    assert behavior.apprentice_config["generation"] == 12
    assert behavior.apprentice_config["kneel"]["set_class"] == "lama"


def test_player_has_default_empty_familycomp() -> None:
    """spawn_player 加 FamilyComp 空实例（拜师 recruit 写入）。"""
    game, pid = _game()
    fam = game.world.get(pid, FamilyComp)
    assert fam is not None
    assert fam.family_name == ""
    assert fam.betrayer == 0


# ──────────────────────── bai 拜师闭环 ────────────────────────


def test_bai_apprentice_success() -> None:
    """男性玩家 bai gongcang -> 通过入门条件 -> recruit 写 FamilyComp + 头衔。"""
    game, pid = _game()
    msgs = bai(game, pid, "贡藏")
    fam = game.world.get(pid, FamilyComp)
    attrs = game.world.get(pid, Attributes)
    title = game.world.get(pid, TitleComp)
    assert fam.family_name == "雪山派"
    assert fam.generation == 13  # 师傅 12 + 1
    assert fam.master_id == "xueshan/gongcang"
    assert fam.master_name == "贡藏"
    assert fam.title == "弟子"
    assert fam.privs == 0
    # Attributes.family 同步（兼容 family_eq 谓词 + FamilyBonus 分发）
    assert attrs.family == "雪山派"
    # assign_apprentice 设 TitleComp.title（对照 apprentice.c:34 sprintf）
    assert title.title == "雪山派第13代弟子"
    assert any("恭喜您成为雪山派的第13代弟子" in m for m in msgs)
    assert any("好吧，我就收下你了" in m for m in msgs)  # success_message


def test_bai_reject_gender() -> None:
    """女性玩家 bai gongcang -> 拒绝（对照 gongcang.c:66 拒女徒）。"""
    game, pid = _game(gender="女性")
    msgs = bai(game, pid, "贡藏")
    assert any("不收女性徒" in m for m in msgs)
    assert game.world.get(pid, FamilyComp).family_name == ""  # 未拜师


def test_bai_reject_other_family_high_exp() -> None:
    """武当高手（combat_exp>=10000）bai gongcang -> 拒绝（对照 gongcang.c:75-81）。"""
    game, pid = _game(player_family="武当派", combat_exp=10000)
    msgs = bai(game, pid, "贡藏")
    assert any("武当派高手" in m for m in msgs)
    assert game.world.get(pid, FamilyComp).family_name == "武当派"  # 未改门派


def test_bai_allow_other_family_low_exp_betray() -> None:
    """武当低手（combat_exp<10000）bai gongcang -> 允许 + 叛师 betrayer+1。"""
    game, pid = _game(player_family="武当派", combat_exp=5000)
    msgs = bai(game, pid, "贡藏")
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"  # 改投雪山
    assert fam.betrayer == 1  # 叛师（武当 -> 雪山，对照 apprentice.c:70）
    assert any("背叛师门" in m for m in msgs)


def test_bai_same_allow_family_betray() -> None:
    """血刀门玩家（在 allow_families）bai gongcang -> 允许 + 叛师（不同门派）。"""
    game, pid = _game(player_family="血刀门", combat_exp=5000)
    bai(game, pid, "贡藏")
    fam = game.world.get(pid, FamilyComp)
    assert fam.family_name == "雪山派"
    assert fam.betrayer == 1  # 血刀门 != 雪山派 -> 叛师


def test_bai_reject_min_skills() -> None:
    """min_skills 不满足 -> 拒绝。"""
    npc = _gongcang_npc()
    npc.apprentice.conditions.min_skills = {"unarmed": 50}
    game, pid = _game(npc=npc, skills={"unarmed": 30})
    msgs = bai(game, pid, "贡藏")
    assert any("unarmed还不够纯熟" in m for m in msgs)


def test_bai_reject_require_flags() -> None:
    """缺 require_flags 标记 -> 拒绝（对照 darba 打赢设标记解锁拜师）。"""
    npc = _gongcang_npc()
    npc.apprentice.conditions.require_flags = ["darba_defeated"]
    game, pid = _game(npc=npc)
    msgs = bai(game, pid, "贡藏")
    assert any("还未证明自己的实力" in m for m in msgs)


def test_bai_require_flags_satisfied() -> None:
    """有 require_flags 标记 -> 允许拜师。"""
    npc = _gongcang_npc()
    npc.apprentice.conditions.require_flags = ["darba_defeated"]
    game, pid = _game(npc=npc, flags={"darba_defeated"})
    bai(game, pid, "贡藏")
    assert game.world.get(pid, FamilyComp).family_name == "雪山派"


def test_bai_already_apprentice_greets() -> None:
    """已是 gongcang 徒弟 -> 请安（对照 apprentice.c:46）。"""
    game, pid = _game()
    bai(game, pid, "贡藏")  # 先拜师
    msgs = bai(game, pid, "贡藏")  # 再 bai -> 请安
    assert any("磕头请安" in m for m in msgs)
    assert "师父" in msgs[0]


def test_bai_generation_check_reject_lower_master() -> None:
    """同门派 + 师傅辈分>=玩家辈分 -> 拒绝拜平辈晚辈（对照 apprentice.c:55-58）。

    玩家雪山派 11 代（辈分高于 gongcang 12 代），拜 gongcang -> 12>=11 -> 拒绝。
    """
    game, pid = _game(player_family="雪山派", player_generation=11)
    msgs = bai(game, pid, "贡藏")
    assert any("辈分不对" in m for m in msgs)


def test_bai_npc_no_family() -> None:
    """NPC 无 family（非师傅）-> 拒绝（对照 apprentice.c:52-53）。"""
    npc = NpcDef(id="npc/villager", name="村民", aliases=["villager"])
    game, pid = _game(npc=npc)
    msgs = bai(game, pid, "村民")
    assert any("不属于任何门派" in m for m in msgs)


def test_bai_npc_not_accepting() -> None:
    """NPC 有 family 但无 apprentice_config（不收徒）-> 拒绝。"""
    # 构造一个有 FamilyComp 但无 apprentice 的 NPC：直接用 NpcDef 无 apprentice
    # 但 build_world 只在 apprentice 非空时加 FamilyComp。此处验证 bai 的 app_config
    # None 分支：用 gongcang 但手动清 apprentice_config。
    game, pid = _game()
    eid = _master_eid(game)
    game.world.get(eid, NpcBehavior).apprentice_config = None
    msgs = bai(game, pid, "贡藏")
    assert any("不想收徒" in m for m in msgs)


def test_bai_not_found() -> None:
    """bai 不存在的 NPC -> 提示。"""
    game, pid = _game()
    msgs = bai(game, pid, "张三丰")
    assert any("没有「张三丰」" in m for m in msgs)


def test_is_apprentice_of() -> None:
    """拜师后 is_apprentice_of 为真（对照 apprentice.c:8）。"""
    game, pid = _game()
    eid = _master_eid(game)
    assert not _is_apprentice_of(game.world, pid, eid)
    bai(game, pid, "贡藏")
    assert _is_apprentice_of(game.world, pid, eid)


# ──────────────────────── kneel 剃度 ────────────────────────


def test_kneel_tonsure() -> None:
    """kneel（有 pending/join_lama 标记）-> 设 class=lama + 清标记 + 消息。"""
    game, pid = _game(flags={"pending/join_lama"})
    msgs = kneel(game, pid)
    title = game.world.get(pid, TitleComp)
    marks = game.world.get(pid, Marks)
    assert title.char_class == "lama"  # 对照 gongcang.c:127 set("class","lama")
    assert "pending/join_lama" not in marks.flags  # 清标记（对照 do_kneel:126）
    assert any("剃去" in m for m in msgs)


def test_kneel_message_pronoun_render() -> None:
    """kneel message 占位符渲染（C6）：$N/$n 经 PronounContext 替换为名。"""
    game, pid = _game(flags={"pending/join_lama"})
    # 改师傅 kneel message 含 $N（speaker=玩家）/ $n（target=师傅）占位符
    master = _master_eid(game)
    behavior = game.world.get(master, NpcBehavior)
    behavior.apprentice_config["kneel"]["message"] = "$N跪在$n面前，剃度出家。"
    msgs = kneel(game, pid)
    # $N -> 玩家名（"玩家"），$n -> 师傅名（"贡藏"）；占位符已替换
    assert any("玩家跪在贡藏面前" in m for m in msgs)
    assert not any("$N" in m or "$n" in m for m in msgs)


def test_kneel_no_permission() -> None:
    """kneel（无 pending 标记）-> 拒绝（对照 gongcang.c:117 检查 pending）。"""
    game, pid = _game()
    msgs = kneel(game, pid)
    assert any("受戒的许可" in m for m in msgs)
    assert game.world.get(pid, TitleComp).char_class == ""  # 未设 class


def test_kneel_no_master_in_room() -> None:
    """房间内无 kneel 配置的师傅 -> 提示没人理会。"""
    npc = NpcDef(id="npc/villager", name="村民", aliases=["villager"])
    game, pid = _game(npc=npc)
    msgs = kneel(game, pid)
    assert any("没人理会" in m for m in msgs)


# ──────────────────────── recruit / betrayer ────────────────────────


def test_recruit_player_path_hint() -> None:
    """recruit 玩家路径 -> 提示（NPC AI 后置，bai 内部已 recruit）。"""
    game, pid = _game()
    msgs = recruit(game, pid, "玩家")
    assert any("bai 拜师" in m for m in msgs)


def test_betrayer_minimal() -> None:
    """betrayer -> betrayer+1 + family 清空 + Attributes.family 同步。"""
    game, pid = _game()
    bai(game, pid, "贡藏")  # 先拜师
    msgs = betrayer(game, pid)
    fam = game.world.get(pid, FamilyComp)
    attrs = game.world.get(pid, Attributes)
    title = game.world.get(pid, TitleComp)
    assert fam.betrayer == 1
    assert fam.family_name == ""
    assert fam.generation == 0
    assert fam.master_id == ""
    assert attrs.family == ""
    assert title.title == ""  # 头衔清
    assert any("背叛了雪山派" in m for m in msgs)


def test_betrayer_no_family() -> None:
    """无门派 -> 提示。"""
    game, pid = _game()
    msgs = betrayer(game, pid)
    assert any("还没有加入任何门派" in m for m in msgs)
