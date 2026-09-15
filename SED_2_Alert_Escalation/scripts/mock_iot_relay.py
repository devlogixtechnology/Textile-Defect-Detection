from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class RelayTrigger:
    timestamp: float
    event_id: str
    camera_id: str
    hazard_class: str
    reason: str


class MockIoTRelay:
    NORMAL = "NORMAL"
    SHUTDOWN_TRIGGERED = "SHUTDOWN_TRIGGERED"

    def __init__(self):
        self._lock = threading.Lock()
        self.state = self.NORMAL
        self.triggers: list[RelayTrigger] = []

    def trigger_shutdown(self, event: Any, reason: str) -> RelayTrigger:
        with self._lock:
            trigger = RelayTrigger(
                timestamp=time.time(),
                event_id=event.event_id,
                camera_id=event.camera_id,
                hazard_class=event.hazard_class,
                reason=reason,
            )
            self.state = self.SHUTDOWN_TRIGGERED
            self.triggers.append(trigger)
            return trigger

    def reset(self) -> None:
        with self._lock:
            self.state = self.NORMAL
            self.triggers.clear()

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = self.triggers[-1] if self.triggers else None
            return {
                "state": self.state,
                "trigger_count": len(self.triggers),
                "last_trigger": last.__dict__ if last else None,
            }

