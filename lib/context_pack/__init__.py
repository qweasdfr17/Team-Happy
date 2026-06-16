"""Project Context Pack — 剧本理解包。

从 project.json + scripts/episode_1.json 确定性提取，供多个 agent
共享同一份剧本理解。纯函数，不做 AI 总结。
"""

from lib.context_pack.builder import build_context_pack
from lib.context_pack.models import SCHEMA_VERSION, empty_context_pack

__all__ = [
    "SCHEMA_VERSION",
    "build_context_pack",
    "empty_context_pack",
]
