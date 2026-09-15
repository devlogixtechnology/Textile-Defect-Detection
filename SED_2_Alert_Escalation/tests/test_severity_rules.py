import unittest
from pathlib import Path

from SED_2_Alert_Escalation.scripts.config import load_action_mapping, load_severity_rules
from SED_2_Alert_Escalation.scripts.models import ActionType, Severity
from SED_2_Alert_Escalation.scripts.severity_engine import SeverityEngine


ROOT = Path(__file__).resolve().parents[2]


class SeverityRuleTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_severity_rules(ROOT / "SED_2_Alert_Escalation" / "configs" / "severity_rules.yaml")
        self.engine = SeverityEngine(self.rules)

    def test_all_safety_hazards_have_rules(self):
        self.assertEqual(
            set(self.rules),
            {"fire", "smoke", "water leak", "chemical hazard", "no helmet"},
        )

    def test_initial_bucket_rules(self):
        cases = {
            "smoke": Severity.INFO,
            "water leak": Severity.INFO,
            "fire": Severity.WARNING,
            "chemical hazard": Severity.WARNING,
            "no helmet": Severity.WARNING,
        }
        for hazard, expected in cases.items():
            with self.subTest(hazard=hazard):
                self.assertEqual(self.engine.decide(hazard, duration=0.0).severity, expected)

    def test_geofence_override_can_raise_severity(self):
        decision = self.engine.decide("fire", duration=0.0, geofence_id="response_zone")
        self.assertEqual(decision.severity, Severity.CRITICAL)
        self.assertIn("geofence override", decision.reason)

    def test_action_mapping_is_distinct_by_tier(self):
        actions = load_action_mapping(ROOT / "SED_2_Alert_Escalation" / "configs" / "action_mapping.yaml")
        self.assertEqual(actions[Severity.INFO].actions(), [ActionType.LOG])
        self.assertEqual(actions[Severity.WARNING].actions(), [ActionType.LOG, ActionType.DASHBOARD_FLASH])
        self.assertEqual(
            actions[Severity.CRITICAL].actions(),
            [
                ActionType.LOG,
                ActionType.DASHBOARD_FLASH,
                ActionType.DASHBOARD_CRITICAL,
                ActionType.MOCK_IOT_SHUTDOWN,
            ],
        )


if __name__ == "__main__":
    unittest.main()

