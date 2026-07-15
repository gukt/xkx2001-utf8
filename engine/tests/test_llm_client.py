"""LLM 客户端测试（ADR-0036）：mock urllib，无真实 API 调用。"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from xkx.content_gen import llm_client
from xkx.content_gen.llm_client import (
    ClaudeClient,
    VolcanoArkClient,
    _extract_content,
    create_llm_client,
    load_dotenv,
)


class _FakeResp:
    """模拟 urllib urlopen 返回的 context manager 响应。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self) -> bytes:
        return self._payload


def _ok_response(content: str) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"role": "assistant", "content": content}}]}
    ).encode("utf-8")


def _claude_response(content: str) -> bytes:
    return json.dumps(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": content}],
            "model": "claude-test",
        }
    ).encode("utf-8")


class TestLoadDotenv:
    """load_dotenv 极简解析器 + override 模式。"""

    def test_loads_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env = tmp_path / ".env"
        env.write_text(
            "# comment\nARK_BASE_URL=https://example.com/api/v3\n"
            "ARK_API_KEY=testkey\nARK_MODEL=test-model\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("ARK_BASE_URL", raising=False)
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        loaded = load_dotenv(env)
        assert loaded == env
        import os

        assert os.environ["ARK_BASE_URL"] == "https://example.com/api/v3"
        assert os.environ["ARK_API_KEY"] == "testkey"
        assert os.environ["ARK_MODEL"] == "test-model"

    def test_override_replaces_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """override=True（默认）：.env 覆盖 shell 已设变量（content_gen 以 .env 为权威）。"""
        env = tmp_path / ".env"
        env.write_text("ARK_BASE_URL=https://from-env/api/v3\n", encoding="utf-8")
        monkeypatch.setenv("ARK_BASE_URL", "https://from-shell/coding")
        load_dotenv(env, override=True)
        import os

        assert os.environ["ARK_BASE_URL"] == "https://from-env/api/v3"

    def test_no_override_keeps_shell(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env = tmp_path / ".env"
        env.write_text("ARK_BASE_URL=https://from-env/api/v3\n", encoding="utf-8")
        monkeypatch.setenv("ARK_BASE_URL", "https://from-shell/coding")
        load_dotenv(env, override=False)
        import os

        assert os.environ["ARK_BASE_URL"] == "https://from-shell/coding"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_dotenv(tmp_path / "nonexistent.env") is None


class TestVolcanoArkClient:
    """VolcanoArkClient 请求构建 + 响应解析 + 重试。"""

    def test_init_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARK_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ARK_API_KEY"):
            VolcanoArkClient(autoload_env=False, api_key="")

    def test_init_reads_explicit_params(self) -> None:
        c = VolcanoArkClient(
            autoload_env=False, api_key="k", base_url="https://x/api/v3", model="m"
        )
        assert c.api_key == "k"
        assert c.base_url == "https://x/api/v3"
        assert c.model == "m"

    def test_chat_builds_request_and_parses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = VolcanoArkClient(
            autoload_env=False, api_key="k", base_url="https://x/api/v3", model="m"
        )
        captured: dict = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeResp(_ok_response("hello yaml"))

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        result = c.chat([{"role": "user", "content": "hi"}], temperature=0.1)
        assert result == "hello yaml"
        assert captured["url"] == "https://x/api/v3/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer k"
        assert captured["body"]["model"] == "m"
        assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]
        assert captured["body"]["temperature"] == 0.1

    def test_chat_retries_on_429_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = VolcanoArkClient(
            autoload_env=False, api_key="k", base_url="https://x/api/v3", model="m"
        )
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, io.BytesIO(b"{}"))
            return _FakeResp(_ok_response("ok"))

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
        assert c.chat([{"role": "user", "content": "hi"}]) == "ok"
        assert calls["n"] == 3

    def test_chat_retries_on_5xx_then_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = VolcanoArkClient(
            autoload_env=False,
            api_key="k",
            base_url="https://x/api/v3",
            model="m",
            max_retries=2,
        )

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 503, "Down", {}, io.BytesIO(b"err"))

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
        with pytest.raises(RuntimeError, match="重试 2 次仍失败"):
            c.chat([{"role": "user", "content": "hi"}])

    def test_chat_4xx_non_retryable_raises_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        c = VolcanoArkClient(
            autoload_env=False, api_key="k", base_url="https://x/api/v3", model="m"
        )
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", {}, io.BytesIO(b'{"error":"no model"}')
            )

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(RuntimeError, match="HTTP 404"):
            c.chat([{"role": "user", "content": "hi"}])
        assert calls["n"] == 1  # 不重试


class TestExtractContent:
    """_extract_content 兼容多种响应形状。"""

    def test_standard_message_content(self) -> None:
        data = {"choices": [{"message": {"content": "text"}}]}
        assert _extract_content(data) == "text"

    def test_content_as_list(self) -> None:
        data = {"choices": [{"message": {"content": [{"text": "a"}, {"text": "b"}]}}]}
        assert _extract_content(data) == "ab"

    def test_missing_choices_raises(self) -> None:
        with pytest.raises(RuntimeError, match="无 choices"):
            _extract_content({})


class TestClaudeClient:
    """ClaudeClient Anthropic Messages API 请求构建 + 响应解析 + 重试。"""

    def test_init_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ClaudeClient(autoload_env=False, api_key="")

    def test_chat_extracts_system_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = ClaudeClient(
            autoload_env=False,
            api_key="k",
            base_url="https://anthropic.example.com",
            model="claude-test",
        )
        captured: dict = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            # urllib Request.headers 是大小写不敏感 Message；统一转小写断言
            captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeResp(_claude_response("hello"))

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        result = c.chat(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hi"},
            ],
            temperature=0.1,
        )
        assert result == "hello"
        assert captured["url"] == "https://anthropic.example.com/v1/messages"
        assert captured["headers"]["x-api-key"] == "k"
        assert captured["headers"]["anthropic-version"] == "2023-06-01"
        assert captured["body"]["system"] == "sys"
        assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]
        assert captured["body"]["temperature"] == 0.1
        assert captured["body"]["max_tokens"] == 1024

    def test_chat_retries_on_429_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = ClaudeClient(
            autoload_env=False, api_key="k", base_url="https://x", model="m"
        )
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, io.BytesIO(b"{}"))
            return _FakeResp(_claude_response("ok"))

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
        assert c.chat([{"role": "user", "content": "hi"}]) == "ok"
        assert calls["n"] == 3

    def test_chat_4xx_non_retryable_raises_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        c = ClaudeClient(autoload_env=False, api_key="k", base_url="https://x", model="m")
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"bad"}')
            )

        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(RuntimeError, match="HTTP 400"):
            c.chat([{"role": "user", "content": "hi"}])
        assert calls["n"] == 1


class TestCreateLLMClient:
    """create_llm_client 工厂按 provider 分发。"""

    def test_create_volcano(self) -> None:
        client = create_llm_client("volcano", api_key="k", autoload_env=False)
        assert isinstance(client, VolcanoArkClient)

    def test_create_claude(self) -> None:
        client = create_llm_client("claude", api_key="k", autoload_env=False)
        assert isinstance(client, ClaudeClient)

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="未知 LLM provider"):
            create_llm_client("unknown")
