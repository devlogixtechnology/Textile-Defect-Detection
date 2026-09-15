import unittest

from SED_2_Alert_Escalation.scripts.models import ActionType, Severity
from SED_2_Alert_Escalation.tests.helpers import make_manager


class ActionTests(unittest.TestCase):
    def test_info_warning_critical_distinct_actions(self):
        manager = make_manager()
        info = manager.process_violation("cam_01", "smoke", timestamp=0.0)
        warning = manager.process_violation("cam_02", "no helmet", timestamp=0.0)
        critical = manager.process_violation("cam_03", "fire", timestamp=0.0, geofence_id="response_zone")

        self.assertEqual(info.severity, Severity.INFO)
        self.assertEqual(info.actions_triggered, [ActionType.LOG.value])

        self.assertEqual(warning.severity, Severity.WARNING)
        self.assertEqual(warning.actions_triggered, [ActionType.LOG.value, ActionType.DASHBOARD_FLASH.value])

        self.assertEqual(critical.severity, Severity.CRITICAL)
        self.assertEqual(
            critical.actions_triggered,
            [
                ActionType.LOG.value,
                ActionType.DASHBOARD_FLASH.value,
                ActionType.DASHBOARD_CRITICAL.value,
                ActionType.MOCK_IOT_SHUTDOWN.value,
            ],
        )
        self.assertEqual(manager.dispatcher.relay.status()["trigger_count"], 1)

    def test_critical_iot_trigger_is_idempotent_for_one_event(self):
        manager = make_manager()
        event = manager.process_violation("cam_01", "fire", timestamp=0.0)
        self.assertEqual(event.severity, Severity.WARNING)
        event = manager.process_violation("cam_01", "fire", timestamp=3.2)
        self.assertEqual(event.severity, Severity.CRITICAL)
        self.assertEqual(manager.dispatcher.relay.status()["trigger_count"], 1)
        manager.process_violation("cam_01", "fire", timestamp=4.0)
        manager.process_violation("cam_01", "fire", timestamp=5.0)
        self.assertEqual(manager.dispatcher.relay.status()["trigger_count"], 1)

    def test_mock_iot_reset(self):
        manager = make_manager()
        manager.process_violation("cam_01", "fire", timestamp=0.0, geofence_id="response_zone")
        self.assertEqual(manager.dispatcher.relay.status()["state"], "SHUTDOWN_TRIGGERED")
        manager.dispatcher.relay.reset()
        self.assertEqual(manager.dispatcher.relay.status()["state"], "NORMAL")
        self.assertEqual(manager.dispatcher.relay.status()["trigger_count"], 0)


if __name__ == "__main__":
    unittest.main()

