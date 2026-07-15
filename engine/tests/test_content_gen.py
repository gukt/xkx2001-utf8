"""content_gen 生成管线测试（ADR-0036）：FakeLLMClient，无真实 API。"""

from __future__ import annotations

from typing import Any

import pytest

from xkx.content_gen.generate import (
    extract_yaml,
    generate_item,
    generate_npc,
    generate_quest,
    generate_room,
    generate_rule,
    generate_skill,
    revise_asset,
)
from xkx.content_gen.llm_client import LLMClient
from xkx.content_gen.prompts import (
    build_item_prompt,
    build_npc_prompt,
    build_quest_prompt,
    build_revision_prompt,
    build_room_prompt,
    build_rule_prompt,
    build_skill_prompt,
)


class FakeLLMClient:
    """记录 messages + 返回预设响应的假客户端（满足 LLMClient 协议）。"""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[dict]] = []

    def chat(
        self, messages: list[dict[str, str]], *, model: str | None = None, **kwargs: Any
    ) -> str:
        self.calls.append(messages)
        return self.response


class TestExtractYaml:
    """extract_yaml 从 LLM 响应提取 YAML（去围栏 + 前后解释）。"""

    def test_plain_yaml(self) -> None:
        text = "id: x\nname: y\n"
        assert "id: x" in extract_yaml(text)

    def test_fenced_yaml(self) -> None:
        text = "好的，结果如下：\n```yaml\nid: x\nname: y\n```\n希望对你有用。"
        result = extract_yaml(text)
        assert "id: x" in result
        assert "name: y" in result
        assert "希望" not in result

    def test_fenced_without_lang(self) -> None:
        text = "```\n- id: a\n- id: b\n```"
        result = extract_yaml(text)
        assert "- id: a" in result

    def test_leading_prose_stripped(self) -> None:
        text = "这是转译结果。\n\nid: x\nname: y"
        result = extract_yaml(text)
        assert result.startswith("id: x")


class TestGenerateFunctions:
    """generate_* 构建 prompt + 解析 YAML + 填默认 id。"""

    def test_generate_npc_parses_and_sets_id(self) -> None:
        resp = "```yaml\nname: 测试NPC\ncombat_exp: 100\n```"
        llm = FakeLLMClient(resp)
        data = generate_npc(llm, "// LPC src", "xueshan/npc/test")
        assert data["name"] == "测试NPC"
        assert data["combat_exp"] == 100
        assert data["id"] == "xueshan/npc/test"
        # prompt 含 system + user，user 含 LPC 源
        assert len(llm.calls) == 1
        assert llm.calls[0][0]["role"] == "system"
        assert "// LPC src" in llm.calls[0][1]["content"]

    def test_generate_skill_parses_and_sets_skill_id(self) -> None:
        resp = (
            "skill_type: martial\nvalid_learn: true\n"
            "practice_skill: false\nvalid_enable: [force]\n"
        )
        llm = FakeLLMClient(resp)
        data = generate_skill(llm, "LPC", "longxiang-banruo")
        assert data["skill_type"] == "martial"
        assert data["practice_skill"] is False
        assert data["valid_enable"] == ["force"]
        assert data["skill_id"] == "longxiang-banruo"

    def test_generate_quest_parses_objectives(self) -> None:
        resp = (
            "name: 测试任务\ngiver: xueshan/npc/darba\ntrigger: 引见\n"
            "objectives:\n- kind: fight_win\n  npc_id: xueshan/npc/darba\n"
        )
        llm = FakeLLMClient(resp)
        data = generate_quest(llm, "LPC", "xueshan/quest/darba")
        assert data["giver"] == "xueshan/npc/darba"
        assert data["objectives"][0]["kind"] == "fight_win"
        assert data["id"] == "xueshan/quest/darba"

    def test_generate_room_parses_exits(self) -> None:
        resp = "short: s\nlong: l\nexits:\n  north: xueshan/frontyard\n"
        llm = FakeLLMClient(resp)
        data = generate_room(llm, "LPC", "xueshan/guangchang")
        assert data["exits"]["north"] == "xueshan/frontyard"
        assert data["id"] == "xueshan/guangchang"

    def test_generate_item_parses_aliases(self) -> None:
        resp = 'name: 经书\naliases: ["a", "b"]\n'
        llm = FakeLLMClient(resp)
        data = generate_item(llm, "LPC", "xueshan/obj/lx-jing")
        assert data["aliases"] == ["a", "b"]
        assert data["id"] == "xueshan/obj/lx-jing"

    def test_generate_npc_non_dict_raises(self) -> None:
        llm = FakeLLMClient("- a\n- b\n")
        with pytest.raises(ValueError, match="期望 dict"):
            generate_npc(llm, "LPC", "x/id")

    def test_generate_empty_response_raises(self) -> None:
        llm = FakeLLMClient("")
        with pytest.raises(ValueError, match="无可解析 YAML"):
            generate_npc(llm, "LPC", "x/id")


class TestPrompts:
    """prompt 模板含 07 映射关键规则（偏差陷阱 + map_skill 推断）。"""

    def test_npc_prompt_contains_bias_traps(self) -> None:
        msgs = build_npc_prompt("LPC", "x/id")
        system = msgs[0]["content"]
        assert "neili/max_neili" in system
        assert "map_skill" in system
        assert "weapon 类别" in system or "武器类别" in system

    def test_skill_prompt_contains_bool_stub_guidance(self) -> None:
        msgs = build_skill_prompt("LPC", "x")
        user = msgs[1]["content"]
        assert "valid_learn" in user
        assert "practice_skill" in user
        assert "knowledge" in user  # lamaism 不可练判定规则

    def test_quest_prompt_contains_objective_kinds(self) -> None:
        msgs = build_quest_prompt("LPC", "x")
        user = msgs[1]["content"]
        assert "fight_win" in user
        assert "give_item" in user
        assert "time_gate" in user

    def test_room_prompt_contains_dir_rule(self) -> None:
        msgs = build_room_prompt("LPC", "x")
        assert "__DIR__" in msgs[1]["content"]

    def test_item_prompt_contains_set_name_rule(self) -> None:
        msgs = build_item_prompt("LPC", "x")
        assert "set_name" in msgs[1]["content"]

    def test_prompts_satisfy_protocol(self) -> None:
        """FakeLLMClient 满足 LLMClient 协议（结构化类型，运行时无操作）。"""
        client: LLMClient = FakeLLMClient("id: x")
        assert client is not None


class TestGenerateRule:
    """rule 生成与修订 prompt。"""

    def test_generate_rule_sets_defaults(self) -> None:
        llm = FakeLLMClient("event: valid_leave\ncondition:\n  kind: always\n"
                            "action: deny\npriority: 10\nmessage: 不能走")
        data = generate_rule(llm, "LPC", "r1/block")
        assert data["id"] == "r1/block"
        assert data["event"] == "valid_leave"

    def test_build_rule_prompt_contains_predicate_schema(self) -> None:
        msgs = build_rule_prompt("LPC", "r1/block", "valid_leave")
        user = msgs[1]["content"]
        assert "EventRule" in user
        assert "Predicate" in user
        assert "spawn_items" in user


class TestReviseAsset:
    """根据 findings 修订 asset。"""

    def test_revise_asset_updates_current(self) -> None:
        llm = FakeLLMClient("id: xueshan/r1\nshort: 修正后\nlong: 修正\n"
                            "objects: {}\nitems: []\noutdoors: true\n"
                            "no_fight: false\ndoors: {}\nexits: {}\n")
        current = {
            "id": "xueshan/r1",
            "short": "旧",
            "long": "旧长文本",
        }
        data = revise_asset(llm, "room", "xueshan/r1", current,
                            ["exit 指向未知房间"])
        assert data["id"] == "xueshan/r1"
        assert data["short"] == "修正后"

    def test_build_revision_prompt_contains_findings(self) -> None:
        msgs = build_revision_prompt(
            "room", "xueshan/r1", "id: x\n", ["exit 错误"]
        )
        user = msgs[1]["content"]
        assert "exit 错误" in user
        assert "只输出纯 YAML" in user
