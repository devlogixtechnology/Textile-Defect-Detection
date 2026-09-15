from __future__ import annotations

from .models import HazardRule, Severity, SeverityDecision


class SeverityEngine:
    def __init__(self, rules: dict[str, HazardRule]):
        self.rules = rules

    def decide(self, hazard_class: str, duration: float, geofence_id: str | None = None) -> SeverityDecision:
        hazard = hazard_class.strip().lower().replace("_", " ").replace("-", " ")
        if hazard not in self.rules:
            return SeverityDecision(Severity.INFO, f"No configured hazard rule for {hazard}; defaulting to info.")
        rule = self.rules[hazard]
        severity = rule.initial_severity
        reason = f"{hazard} confirmed; initial severity {severity.value}."

        if geofence_id and geofence_id in rule.geofence_overrides:
            override = rule.geofence_overrides[geofence_id]
            if override.rank > severity.rank:
                severity = override
                reason = f"{hazard} matched geofence override {geofence_id} -> {severity.value}."

        if rule.warning_after_seconds is not None and duration >= rule.warning_after_seconds:
            if Severity.WARNING.rank > severity.rank:
                severity = Severity.WARNING
                reason = (
                    f"{hazard} persisted for {duration:.2f}s; "
                    f"warning threshold is {rule.warning_after_seconds:.2f}s."
                )

        if rule.critical_after_seconds is not None and duration >= rule.critical_after_seconds:
            if Severity.CRITICAL.rank > severity.rank:
                severity = Severity.CRITICAL
                reason = (
                    f"{hazard} persisted for {duration:.2f}s; "
                    f"critical threshold is {rule.critical_after_seconds:.2f}s."
                )

        return SeverityDecision(severity=severity, reason=reason)

