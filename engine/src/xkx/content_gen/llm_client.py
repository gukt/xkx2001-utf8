"""LLM 客户端（ADR-0036）：可插拔抽象 + 火山方舟 adapter。

火山方舟 OpenAI 兼容 ``/api/v3/chat/completions``，stdlib ``urllib.request``
（无新依赖，契合 04 §六 收敛原则 + ADR-0012 stdlib 优先先例）。配置经
``engine/.env``（``ARK_BASE_URL`` / ``ARK_API_KEY`` / ``ARK_MODEL``）。

.. note::
   ``load_dotenv`` 用 override 模式（项目 .env 对 content_gen 权威）：shell 可能
   有为其他工具设的 ``ARK_*``（如 coding 端点），content_gen 以 ``engine/.env``
   为准（用户 ADR-0036 决策）。
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
# 火山方舟 model ID 含日期后缀（deepseek-v4-flash 的实际 ID，ADR-0036 实施期确认）
DEFAULT_MODEL = "deepseek-v4-flash-260425"
DEFAULT_TIMEOUT = 180  # 秒
MAX_RETRIES = 3

# engine/.env 查找：content_gen 在 src/xkx/content_gen/，engine 根在 parents[3]
_ENV_CANDIDATES = [
    Path(__file__).resolve().parents[3] / ".env",  # engine/.env
    Path.cwd() / ".env",
]


def load_dotenv(path: Path | str | None = None, *, override: bool = True) -> Path | None:
    """极简 .env 解析器（KEY=VALUE，跳过注释）。

    不引入 python-dotenv 依赖（04 §六 收缩原则）。``override=True``（默认）：项目
    .env 覆盖 shell 已设的同名变量（content_gen 以 .env 为权威，ADR-0036）。

    返回实际加载的 .env 路径（未找到返回 None）。
    """
    candidates = [Path(path)] if path else _ENV_CANDIDATES
    for cand in candidates:
        if not cand.is_file():
            continue
        for line in cand.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and (override or key not in os.environ):
                os.environ[key] = value
        return cand
    return None


class LLMClient(Protocol):
    """LLM 客户端协议（创作期工具，不进 runtime 导入图）。"""

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """同步 chat completions，返回 assistant 文本。"""
        ...


class VolcanoArkClient:
    """火山方舟 OpenAI 兼容客户端（ADR-0036 决策 1）。

    端点 ``{base_url}/chat/completions``，Bearer 鉴权。429/5xx 指数退避重试。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        autoload_env: bool = True,
    ) -> None:
        if autoload_env:
            load_dotenv()
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        self.base_url = (
            base_url or os.environ.get("ARK_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self.model = model or os.environ.get("ARK_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.max_retries = max_retries
        if not self.api_key:
            raise ValueError(
                "ARK_API_KEY 未设置：检查 engine/.env（见 .env.example）或环境变量"
            )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """调 chat/completions，返回 assistant 文本。

        ``kwargs`` 透传给 API（如 ``response_format``）。
        """
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return _extract_content(data)
            except urllib.error.HTTPError as e:
                last_err = e
                body_text = ""
                with contextlib.suppress(Exception):
                    body_text = e.read().decode("utf-8", "replace")
                if e.code == 429 or e.code >= 500:
                    time.sleep(2**attempt)  # 1s, 2s, 4s
                    continue
                raise RuntimeError(f"火山方舟 API HTTP {e.code}: {body_text}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
                time.sleep(2**attempt)
                continue
        raise RuntimeError(
            f"火山方舟 API 重试 {self.max_retries} 次仍失败: {type(last_err).__name__}: {last_err}"
        )


def _extract_content(data: dict[str, Any]) -> str:
    """从 OpenAI 兼容响应提取 assistant 文本。"""
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"火山方舟 API 响应无 choices: {data}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if content is None:
        # 部分 provider 用 reasoning_content 兜底
        content = msg.get("reasoning_content") or ""
    if isinstance(content, list):
        # 某些响应 content 是 list[dict]，拼 text
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content
