from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, Field


class GateSeverity(StrEnum):
    INFO = "info"
    WARN = "warn"
    BLOCKER = "blocker"


class GateIssue(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    message: str = Field(..., min_length=2, max_length=500)
    severity: GateSeverity
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class GateResult(BaseModel):
    passed: bool
    issues: list[GateIssue] = Field(default_factory=list)

    @property
    def blockers(self) -> list[GateIssue]:
        return [item for item in self.issues if item.severity == GateSeverity.BLOCKER]

