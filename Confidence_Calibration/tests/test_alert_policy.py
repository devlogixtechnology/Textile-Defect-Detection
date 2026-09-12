import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alert_policy import AlertPolicy, AlertPolicyConfig, AlertClassConfig


def policy_for_test() -> AlertPolicy:
    cfg = AlertPolicyConfig(
        default_confidence=0.25,
        alert_classes={"fire", "smoke"},
        classes={
            "fire": AlertClassConfig(confidence=0.25, window_size=5, required_frames=3, cooldown_frames=2, clear_frames=2),
            "smoke": AlertClassConfig(confidence=0.25, window_size=5, required_frames=3, cooldown_frames=2, clear_frames=2),
        },
    )
    return AlertPolicy(cfg)


class AlertPolicyTests(unittest.TestCase):
    def test_single_false_spike_does_not_trigger(self):
        policy = policy_for_test()
        alerts = []
        sequence = [0, 0, 1, 0, 0]
        for i, detected in enumerate(sequence):
            detections = [{"class_name": "fire", "confidence": 0.9}] if detected else []
            alerts.extend(policy.process_frame(detections, i)["alerts"])
        self.assertEqual(alerts, [])

    def test_persistent_violation_triggers_once(self):
        policy = policy_for_test()
        alerts = []
        sequence = [0, 1, 1, 1, 1]
        for i, detected in enumerate(sequence):
            detections = [{"class_name": "fire", "confidence": 0.9}] if detected else []
            alerts.extend(policy.process_frame(detections, i)["alerts"])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["class_name"], "fire")

    def test_intermittent_real_detection_triggers(self):
        policy = policy_for_test()
        alerts = []
        sequence = [1, 0, 1, 1, 0]
        for i, detected in enumerate(sequence):
            detections = [{"class_name": "fire", "confidence": 0.9}] if detected else []
            alerts.extend(policy.process_frame(detections, i)["alerts"])
        self.assertEqual(len(alerts), 1)

    def test_low_confidence_is_filtered(self):
        policy = policy_for_test()
        alerts = []
        for i in range(5):
            alerts.extend(policy.process_frame([{"class_name": "fire", "confidence": 0.1}], i)["alerts"])
        self.assertEqual(alerts, [])

    def test_classes_are_independent(self):
        policy = policy_for_test()
        alerts = []
        for i in range(3):
            detections = [{"class_name": "fire", "confidence": 0.9}]
            alerts.extend(policy.process_frame(detections, i)["alerts"])
        for i in range(3, 6):
            detections = [{"class_name": "smoke", "confidence": 0.9}]
            alerts.extend(policy.process_frame(detections, i)["alerts"])
        self.assertEqual([a["class_name"] for a in alerts], ["fire", "smoke"])

    def test_alert_clears_after_absence(self):
        policy = policy_for_test()
        alerts = []
        for i, detected in enumerate([1, 1, 1, 0, 0, 0, 1, 1, 1]):
            detections = [{"class_name": "fire", "confidence": 0.9}] if detected else []
            alerts.extend(policy.process_frame(detections, i)["alerts"])
        self.assertGreaterEqual(len(alerts), 2)


if __name__ == "__main__":
    unittest.main()

