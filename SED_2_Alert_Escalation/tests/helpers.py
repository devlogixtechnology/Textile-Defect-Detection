from pathlib import Path

from SED_2_Alert_Escalation.scripts.action_dispatcher import ActionDispatcher
from SED_2_Alert_Escalation.scripts.config import load_action_mapping, load_severity_rules
from SED_2_Alert_Escalation.scripts.escalation_state import EscalationManager
from SED_2_Alert_Escalation.scripts.event_store import EventStore
from SED_2_Alert_Escalation.scripts.mock_iot_relay import MockIoTRelay
from SED_2_Alert_Escalation.scripts.severity_engine import SeverityEngine


ROOT = Path(__file__).resolve().parents[2]


def make_manager(log_path=None):
    rules = load_severity_rules(ROOT / "SED_2_Alert_Escalation" / "configs" / "severity_rules.yaml")
    actions = load_action_mapping(ROOT / "SED_2_Alert_Escalation" / "configs" / "action_mapping.yaml")
    store = EventStore(log_path=log_path)
    relay = MockIoTRelay()
    dispatcher = ActionDispatcher(actions, store, relay)
    return EscalationManager(SeverityEngine(rules), dispatcher, store, rules)

