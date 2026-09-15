from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .models import ActionRecord, AlertEvent


class EventStore:
    def __init__(self, log_path: str | Path | None = None):
        self._lock = threading.Lock()
        self.events: dict[str, AlertEvent] = {}
        self.history: list[dict[str, Any]] = []
        self.action_records: list[ActionRecord] = []
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def upsert_event(self, event: AlertEvent) -> None:
        with self._lock:
            self.events[event.event_id] = event

    def record_transition(self, event: AlertEvent, previous_state: str, reason: str) -> None:
        entry = {
            "timestamp": event.last_seen,
            "event_id": event.event_id,
            "camera_id": event.camera_id,
            "hazard_class": event.hazard_class,
            "transition": f"{previous_state}->{event.state.value}",
            "severity": event.severity.value,
            "geofence_id": event.geofence_id,
            "duration": event.duration,
            "reason": reason,
        }
        with self._lock:
            self.history.append(entry)
            if self.log_path:
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, sort_keys=True) + "\n")

    def record_action(self, record: ActionRecord) -> None:
        entry = {"type": "action", **record.to_dict()}
        with self._lock:
            self.action_records.append(record)
            self.history.append(entry)
            if self.log_path:
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, sort_keys=True) + "\n")

    def active_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                event.to_dict()
                for event in self.events.values()
                if event.state.value in {"info", "warning", "critical"}
            ]

    def all_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [event.to_dict() for event in self.events.values()]

