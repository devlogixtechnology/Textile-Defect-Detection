from __future__ import annotations

import itertools
import threading
import time
from typing import Any

from .action_dispatcher import ActionDispatcher
from .event_store import EventStore
from .models import AlertEvent, EventState, HazardRule, Severity
from .severity_engine import SeverityEngine


class EscalationManager:
    def __init__(
        self,
        severity_engine: SeverityEngine,
        dispatcher: ActionDispatcher,
        event_store: EventStore,
        rules: dict[str, HazardRule],
    ):
        self.severity_engine = severity_engine
        self.dispatcher = dispatcher
        self.event_store = event_store
        self.rules = rules
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._active_by_key: dict[tuple[str, str, str | None], AlertEvent] = {}

    def process_violation(
        self,
        camera_id: str,
        hazard_class: str,
        timestamp: float | None = None,
        confidence: float | None = None,
        geofence_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AlertEvent:
        timestamp = time.time() if timestamp is None else float(timestamp)
        hazard = hazard_class.strip().lower().replace("_", " ").replace("-", " ")
        key = (camera_id, hazard, geofence_id)
        with self._lock:
            event = self._active_by_key.get(key)
            if event is None or event.state == EventState.RESOLVED:
                event = AlertEvent(
                    event_id=f"SED2-{next(self._counter):06d}",
                    camera_id=camera_id,
                    hazard_class=hazard,
                    severity=Severity.INFO,
                    state=EventState.INACTIVE,
                    first_seen=timestamp,
                    last_seen=timestamp,
                    confidence=confidence,
                    geofence_id=geofence_id,
                    metadata=dict(metadata or {}),
                )
                self._active_by_key[key] = event

            event.last_seen = timestamp
            event.duration = max(0.0, event.last_seen - event.first_seen)
            event.confidence = confidence if confidence is not None else event.confidence
            event.geofence_id = geofence_id
            event.metadata.update(metadata or {})

            decision = self.severity_engine.decide(hazard, event.duration, geofence_id=geofence_id)
            if event.state == EventState.INACTIVE or decision.severity.rank > event.severity.rank:
                previous_state = event.state
                previous_severity = event.severity if event.state != EventState.INACTIVE else None
                event.severity = decision.severity
                event.state = EventState(decision.severity.value)
                event.escalation_reason = decision.reason
                event.transition_count += 1
                self.event_store.record_transition(event, previous_state.value, decision.reason)
                self.dispatcher.dispatch(event, previous_severity, decision.reason)
            else:
                self.event_store.upsert_event(event)
            return event

    def mark_absent(self, camera_id: str, hazard_class: str, timestamp: float | None = None, geofence_id: str | None = None) -> AlertEvent | None:
        timestamp = time.time() if timestamp is None else float(timestamp)
        hazard = hazard_class.strip().lower().replace("_", " ").replace("-", " ")
        key = (camera_id, hazard, geofence_id)
        with self._lock:
            event = self._active_by_key.get(key)
            if event is None or event.state == EventState.RESOLVED:
                return event
            rule = self.rules.get(hazard)
            clear_after = rule.clear_after_seconds if rule else 5.0
            absent_for = max(0.0, timestamp - event.last_seen)
            if absent_for >= clear_after:
                previous_state = event.state
                event.state = EventState.RESOLVED
                event.duration = max(0.0, event.last_seen - event.first_seen)
                event.escalation_reason = f"{hazard} absent for {absent_for:.2f}s; clear threshold is {clear_after:.2f}s."
                event.transition_count += 1
                self.event_store.record_transition(event, previous_state.value, event.escalation_reason)
                self.event_store.upsert_event(event)
            return event

    def process_frame(
        self,
        camera_id: str,
        active_violations: list[dict[str, Any]],
        timestamp: float | None = None,
    ) -> list[AlertEvent]:
        timestamp = time.time() if timestamp is None else float(timestamp)
        seen_keys: set[tuple[str, str, str | None]] = set()
        events = []
        for violation in active_violations:
            hazard = str(violation.get("class_name", violation.get("hazard_class", "")))
            geofence_id = violation.get("geofence_id")
            event = self.process_violation(
                camera_id=camera_id,
                hazard_class=hazard,
                timestamp=timestamp,
                confidence=violation.get("confidence"),
                geofence_id=geofence_id,
                metadata={"source": violation.get("source", "cme2_confirmed")},
            )
            seen_keys.add((camera_id, event.hazard_class, geofence_id))
            events.append(event)
        with self._lock:
            keys = list(self._active_by_key)
        for key in keys:
            if key[0] == camera_id and key not in seen_keys:
                self.mark_absent(key[0], key[1], timestamp=timestamp, geofence_id=key[2])
        return events

    def active_events(self) -> list[dict[str, Any]]:
        return self.event_store.active_events()

    def all_events(self) -> list[dict[str, Any]]:
        return self.event_store.all_events()

    def camera_overall_severity(self) -> dict[str, str]:
        overall: dict[str, Severity] = {}
        for event in self.event_store.active_events():
            severity = Severity.from_value(event["severity"])
            camera_id = event["camera_id"]
            if camera_id not in overall or severity.rank > overall[camera_id].rank:
                overall[camera_id] = severity
        return {camera_id: severity.value for camera_id, severity in overall.items()}

