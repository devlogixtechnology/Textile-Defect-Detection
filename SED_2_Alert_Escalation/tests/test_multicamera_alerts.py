import unittest

from SED_2_Alert_Escalation.scripts.models import Severity
from SED_2_Alert_Escalation.tests.helpers import make_manager


class MultiCameraAlertTests(unittest.TestCase):
    def test_three_tiers_can_coexist_across_cameras(self):
        manager = make_manager()
        cam1 = manager.process_violation("cam_01", "smoke", timestamp=0.0)
        cam2 = manager.process_violation("cam_02", "no helmet", timestamp=0.0)
        cam3 = manager.process_violation("cam_03", "fire", timestamp=0.0, geofence_id="response_zone")

        self.assertEqual(cam1.severity, Severity.INFO)
        self.assertEqual(cam2.severity, Severity.WARNING)
        self.assertEqual(cam3.severity, Severity.CRITICAL)

        overall = manager.camera_overall_severity()
        self.assertEqual(overall["cam_01"], "info")
        self.assertEqual(overall["cam_02"], "warning")
        self.assertEqual(overall["cam_03"], "critical")

    def test_process_frame_preserves_camera_isolation(self):
        manager = make_manager()
        manager.process_frame("cam_01", [{"class_name": "smoke", "confidence": 0.8}], timestamp=0.0)
        manager.process_frame("cam_02", [{"class_name": "no helmet", "confidence": 0.8}], timestamp=0.0)
        manager.process_frame(
            "cam_03",
            [{"class_name": "chemical hazard", "confidence": 0.8, "geofence_id": "leak_zone"}],
            timestamp=0.0,
        )
        events = {event["camera_id"]: event["severity"] for event in manager.active_events()}
        self.assertEqual(events["cam_01"], "info")
        self.assertEqual(events["cam_02"], "warning")
        self.assertEqual(events["cam_03"], "critical")


if __name__ == "__main__":
    unittest.main()

