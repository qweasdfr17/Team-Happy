"""生视频前资产引用预检（preflight checks）。

不阻塞生成，只产出结构化的预检报告供前端展示与人工决策。
"""

from lib.preflight.models import PreflightIssue, PreflightReport, Severity
from lib.preflight.checks import run_preflight

__all__ = [
    "PreflightIssue",
    "PreflightReport",
    "Severity",
    "run_preflight",
]
