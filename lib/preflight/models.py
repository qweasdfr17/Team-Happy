"""预检数据模型。"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    blocking = "blocking"
    warning = "warning"
    info = "info"


class PreflightIssue:
    """单条预检问题。"""

    __slots__ = ("severity", "code", "message", "location")

    def __init__(self, severity: Severity, code: str, message: str, location: str = ""):
        self.severity = severity
        self.code = code
        self.message = message
        self.location = location

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }


class PreflightReport:
    """预检报告：按严重级别分组的问题列表 + 汇总计数。"""

    __slots__ = ("blocking", "warnings", "info")

    def __init__(self):
        self.blocking: list[PreflightIssue] = []
        self.warnings: list[PreflightIssue] = []
        self.info: list[PreflightIssue] = []

    def add(self, issue: PreflightIssue) -> None:
        if issue.severity == Severity.blocking:
            self.blocking.append(issue)
        elif issue.severity == Severity.warning:
            self.warnings.append(issue)
        else:
            self.info.append(issue)

    @property
    def blocking_count(self) -> int:
        return len(self.blocking)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def info_count(self) -> int:
        return len(self.info)

    @property
    def total_count(self) -> int:
        return self.blocking_count + self.warning_count + self.info_count

    def to_dict(self) -> dict:
        return {
            "blocking": [i.to_dict() for i in self.blocking],
            "warnings": [i.to_dict() for i in self.warnings],
            "info": [i.to_dict() for i in self.info],
            "summary": {
                "blocking_count": self.blocking_count,
                "warning_count": self.warning_count,
                "info_count": self.info_count,
            },
        }
