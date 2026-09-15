from __future__ import annotations

import time

from .event_store import EventStore
from .mock_iot_relay import MockIoTRelay
from .models import ActionRecord, ActionRule, ActionType, AlertEvent, Severity


class ActionDispatcher:
    def __init__(self, action_mapping: dict[Severity, ActionRule], event_store: EventStore, relay: MockIoTRelay):
        self.action_mapping = action_mapping
        self.event_store = event_store
        self.relay = relay

    def dispatch(
        self,
        event: AlertEvent,
        previous_severity: Severity | None,
        reason: str,
    ) -> list[ActionType]:
        rule = self.action_mapping[event.severity]
        actions = rule.actions()
        triggered: list[ActionType] = []
        for action in actions:
            if action == ActionType.MOCK_IOT_SHUTDOWN and event.metadata.get("iot_shutdown_triggered"):
                continue
            if action == ActionType.MOCK_IOT_SHUTDOWN:
                self.relay.trigger_shutdown(event, reason)
                event.metadata["iot_shutdown_triggered"] = True
            record = ActionRecord(
                timestamp=time.time(),
                event_id=event.event_id,
                camera_id=event.camera_id,
                hazard_class=event.hazard_class,
                severity=event.severity,
                previous_severity=previous_severity,
                geofence_id=event.geofence_id,
                confidence=event.confidence,
                duration=event.duration,
                action=action,
                reason=reason,
            )
            self.event_store.record_action(record)
            if action.value not in event.actions_triggered:
                event.actions_triggered.append(action.value)
            triggered.append(action)
        self.event_store.upsert_event(event)
        return triggered

