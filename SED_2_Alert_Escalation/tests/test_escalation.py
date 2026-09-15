import tempfile
import unittest
from pathlib import Path

from SED_2_Alert_Escalation.scripts.models import EventState, Severity
from SED_2_Alert_Escalation.tests.helpers import make_manager


class EscalationTests(unittest.TestCase):
    def test_info_to_warning_after_threshold(self):
        manager = make_manager()
        event = manager.process_violation("cam_01", "smoke", timestamp=100.0)
        self.assertEqual(event.severity, Severity.INFO)
        event = manager.process_violation("cam_01", "smoke", timestamp=101.0)
        self.assertEqual(event.severity, Severity.INFO)
        event = manager.process_violation("cam_01", "smoke", timestamp=102.1)
        self.assertEqual(event.severity, Severity.WARNING)
        self.assertIn("warning threshold", event.escalation_reason)

    def test_warning_to_critical_after_threshold(self):
        manager = make_manager()
        event = manager.process_violation("cam_01", "chemical hazard", timestamp=10.0)
        self.assertEqual(event.severity, Severity.WARNING)
        event = manager.process_violation("cam_01", "chemical hazard", timestamp=13.1)
        self.assertEqual(event.severity, Severity.CRITICAL)
        self.assertIn("critical threshold", event.escalation_reason)

    def test_no_premature_escalation(self):
        manager = make_manager()
        event = manager.process_violation("cam_01", "smoke", timestamp=0.0)
        event = manager.process_violation("cam_01", "smoke", timestamp=1.9)
        self.assertEqual(event.severity, Severity.INFO)

    def test_resolution_and_recurrence_gets_new_event_id(self):
        manager = make_manager()
        event = manager.process_violation("cam_01", "smoke", timestamp=0.0)
        first_id = event.event_id
        resolved = manager.mark_absent("cam_01", "smoke", timestamp=5.1)
        self.assertEqual(resolved.state, EventState.RESOLVED)
        new_event = manager.process_violation("cam_01", "smoke", timestamp=6.0)
        self.assertNotEqual(first_id, new_event.event_id)

    def test_jsonl_log_records_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "events.jsonl"
            manager = make_manager(log_path=log_path)
            manager.process_violation("cam_01", "smoke", timestamp=0.0)
            self.assertTrue(log_path.exists())
            self.assertIn("INACTIVE".lower(), log_path.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()

