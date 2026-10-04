from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum


class GateStatus(StrEnum):
    PASS = "PASS"  # nosec B105 - статус проверки, не пароль
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass(frozen=True)
class GateReport:
    stage: str
    status: GateStatus
    checks: dict[str, bool]
    messages: list[str]


class GateFailed(RuntimeError):
    def __init__(self, report: GateReport):
        self.report = report
        super().__init__(f'{report.stage} quality gate failed: {"; ".join(report.messages)}')


def evaluate(stage: str, checks: dict[str, bool], warnings: list[str] | None = None) -> GateReport:
    failed = [name for name, passed in checks.items() if not passed]
    messages = [*(warnings or []), *[f"{name}: failed" for name in failed]]
    status = GateStatus.FAIL if failed else GateStatus.WARNING if warnings else GateStatus.PASS
    return GateReport(stage, status, checks, messages)


def require(report: GateReport) -> GateReport:
    if report.status is GateStatus.FAIL:
        raise GateFailed(report)
    return report
