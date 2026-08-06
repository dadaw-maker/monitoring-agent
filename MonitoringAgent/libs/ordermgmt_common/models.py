"""Shared data models for indicator computation, used by the agent and both MCP servers.

Kept dependency-free (stdlib + pydantic only) so it can be vendored into every
service image without pulling in service-specific requirements.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

IndicatorType = Literal["technique", "fonctionnel"]


class IndicatorStatus(str, Enum):
    """Traffic-light status of an indicator, derived from its threshold rule."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"  # data unavailable / not yet calibrated (see specs.md §7)


class IndicatorResult(BaseModel):
    """Result of computing one unitary indicator (COL-*, CAL-*, TRA-*, WMS-*, DIR-*, E2E-*)."""

    code: str = Field(..., description="Indicator code, e.g. 'COL-1'")
    label: str
    type: IndicatorType
    niveau: int = Field(..., ge=1, le=2)
    value: float | None = None
    unit: str = ""
    status: IndicatorStatus = IndicatorStatus.UNKNOWN
    detail: dict[str, Any] = Field(default_factory=dict)
    source_mode: str = "unknown"  # "stub" or "live" — which connector produced the raw data
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prometheus_status_value(self) -> int:
        return {
            IndicatorStatus.OK: 0,
            IndicatorStatus.WARNING: 1,
            IndicatorStatus.CRITICAL: 2,
            IndicatorStatus.UNKNOWN: 3,
        }[self.status]


class ChapeauResult(BaseModel):
    """Result of an indicateur chapeau (or the indicateur de tête), combining unitaires."""

    code: str  # e.g. "CHAPEAU-COLLECTE", "TETE"
    question: str
    status: IndicatorStatus = IndicatorStatus.UNKNOWN
    combined_from: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prometheus_status_value(self) -> int:
        return {
            IndicatorStatus.OK: 0,
            IndicatorStatus.WARNING: 1,
            IndicatorStatus.CRITICAL: 2,
            IndicatorStatus.UNKNOWN: 3,
        }[self.status]


def worst_status(*statuses: IndicatorStatus) -> IndicatorStatus:
    """Combine several statuses conservatively: CRITICAL > WARNING > UNKNOWN > OK."""
    order = [IndicatorStatus.CRITICAL, IndicatorStatus.WARNING, IndicatorStatus.UNKNOWN]
    for candidate in order:
        if candidate in statuses:
            return candidate
    return IndicatorStatus.OK
