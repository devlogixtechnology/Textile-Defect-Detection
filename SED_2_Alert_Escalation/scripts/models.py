from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


SEVERITY_POLICY_VERSION = "SED2-alert-escalation-v1"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {Severity.INFO: 1, Severity.WARNING: 2, Severity.CRITICAL: 3}[self]

    @classmethod
    def from_value(cls, value: str) -> "Severity":
        normalized = value.strip().lower()
        for severity in cls:
            if severity.value == normalized:
                return severity
        raise ValueError(f"Invalid severity: {value}")


class EventState(str, Enum):
    INACTIVE = "inactive"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    RESOLVED = "resolved"

    @property
    def severity(self) -> Severity | None:
        if self in {EventState.INFO, EventState.WARNING, EventState.CRITICAL}:
            return Severity.from_value(self.value)
        return None


class ActionType(str, Enum):
    LOG = "log"
    DASHBOARD_FLASH = "dashboard_flash"
    DASHBOARD_CRITICAL = "dashboard_critical"
    MOCK_IOT_SHUTDOWN = "mock_iot_shutdown"


@dataclass(frozen=True)
class HazardRule:
    hazard_class: str
    initial_severity: Severity
    warning_after_seconds: float | None = None
    critical_after_seconds: float | None = None
    clear_after_seconds: float = 5.0
    geofence_overrides: dict[str, Severity] = field(default_factory=dict)
    category: str = "safety"


@dataclass(frozen=True)
class ActionRule:
    log: bool
    dashboard_flash: bool
    dashboard_critical: bool
    mock_iot_shutdown: bool

    def actions(self) -> list[ActionType]:
        actions: list[ActionType] = []
        if self.log:
            actions.append(ActionType.LOG)
        if self.dashboard_flash:
            actions.append(ActionType.DASHBOARD_FLASH)
        if self.dashboard_critical:
            actions.append(ActionType.DASHBOARD_CRITICAL)
        if self.mock_iot_shutdown:
            actions.append(ActionType.MOCK_IOT_SHUTDOWN)
        return actions


@dataclass
class SeverityDecision:
    severity: Severity
    reason: str


@dataclass
class AlertEvent:
    event_id: str
    camera_id: str
    hazard_class: str
    severity: Severity
    state: EventState
    first_seen: float
    last_seen: float
    confidence: float | None = None
    geofence_id: str | None = None
    duration: float = 0.0
    escalation_reason: str = ""
    actions_triggered: list[str] = field(default_factory=list)
    transition_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "hazard_class": self.hazard_class,
            "severity": self.severity.value,
            "state": self.state.value,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "duration": self.duration,
            "confidence": self.confidence,
            "geofence_id": self.geofence_id,
            "escalation_reason": self.escalation_reason,
            "actions_triggered": list(self.actions_triggered),
            "transition_count": self.transition_count,
            "metadata": dict(self.metadata),
        }


@dataclass
class ActionRecord:
    timestamp: float
    event_id: str
    camera_id: str
    hazard_class: str
    severity: Severity
    previous_severity: Severity | None
    geofence_id: str | None
    confidence: float | None
    duration: float
    action: ActionType
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "hazard_class": self.hazard_class,
            "severity": self.severity.value,
            "previous_severity": self.previous_severity.value if self.previous_severity else None,
            "geofence_id": self.geofence_id,
            "confidence": self.confidence,
            "duration": self.duration,
            "action": self.action.value,
            "reason": self.reason,
        }

