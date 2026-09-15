from __future__ import annotations

from pathlib import Path

from .action_dispatcher import ActionDispatcher
from .config import load_action_mapping, load_severity_rules
from .escalation_state import EscalationManager
from .event_store import EventStore
from .mock_iot_relay import MockIoTRelay
from .severity_engine import SeverityEngine


def create_default_escalation_manager(
    project_root: str | Path,
    log_path: str | Path | None = None,
) -> EscalationManager:
    root = Path(project_root)
    rules = load_severity_rules(root / "SED_2_Alert_Escalation" / "configs" / "severity_rules.yaml")
    actions = load_action_mapping(root / "SED_2_Alert_Escalation" / "configs" / "action_mapping.yaml")
    event_store = EventStore(log_path=log_path)
    relay = MockIoTRelay()
    dispatcher = ActionDispatcher(actions, event_store, relay)
    return EscalationManager(SeverityEngine(rules), dispatcher, event_store, rules)

