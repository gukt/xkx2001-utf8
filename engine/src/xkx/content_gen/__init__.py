"""内容生产管线（ADR-0036）：独立 LLM 从 LPC 规格源生成层0 DSL 初稿。

创作期工具，不进 runtime 导入图（runtime 不 import 本包）。仅依赖 stdlib +
已有 pyyaml，无新运行时依赖（04 §六 收敛原则）。

组件：
- ``llm_client``：LLMClient 抽象 + VolcanoArkClient（火山方舟 OpenAI 兼容 /api/v3）。
- ``prompts``：LPC -> DSL prompt 模板（grounded in 07-agent-schema-mapping）。
- ``generate``：编排（build prompt -> call LLM -> 解析 YAML -> 校验）。

kill criteria 5 修订量度量复用 ``tools/measure_revision.py``（本地 semantic_ratio，
Langfuse 后置）。
"""

from xkx.content_gen.generate import (
    generate_item,
    generate_npc,
    generate_quest,
    generate_room,
    generate_skill,
)
from xkx.content_gen.llm_client import LLMClient, VolcanoArkClient, load_dotenv

__all__ = [
    "LLMClient",
    "VolcanoArkClient",
    "load_dotenv",
    "generate_npc",
    "generate_skill",
    "generate_quest",
    "generate_room",
    "generate_item",
]
