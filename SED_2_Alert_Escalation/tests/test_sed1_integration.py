import time
import unittest

from SED_1_Multi_Camera.scripts.camera_source import SyntheticCameraSource
from SED_1_Multi_Camera.scripts.stream_manager import MultiCameraStreamManager
from SED_1_Multi_Camera.scripts.models import CameraConfig, GeofenceConfig
from SED_2_Alert_Escalation.tests.helpers import make_manager


class FakeDetector:
    def predict_batch(self, frames):
        return [
            [
                {
                    "class_name": "smoke",
                    "confidence": 0.9,
                    "coordinates": {"x1": 20, "y1": 20, "x2": 80, "y2": 80},
                }
            ]
            for _frame in frames
        ], 0.001


class FakeCME2Manager:
    def __init__(self):
        self.active = {"smoke": True}


class FakeCME2Policy:
    def __init__(self):
        self.manager = FakeCME2Manager()

    def process_frame(self, detections, frame_index, timestamp_sec=None):
        return {"calibrated_detections": detections, "alerts": []}


class SED1IntegrationTests(unittest.TestCase):
    def test_stream_manager_routes_confirmed_violation_to_sed2(self):
        camera = CameraConfig(
            camera_id="cam_01",
            name="Smoke Test",
            source="synthetic",
            sampling_fps=20.0,
            monitored_classes={"smoke"},
            geofences=[
                GeofenceConfig(
                    id="whole_frame",
                    polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
                    classes={"smoke"},
                )
            ],
        )
        manager = MultiCameraStreamManager(
            [camera],
            FakeDetector(),
            alert_policy_factory=FakeCME2Policy,
            escalation_manager=make_manager(),
            queue_size=2,
            source_factory=lambda _cfg: SyntheticCameraSource(source_fps=20.0, max_frames=3),
        )
        manager.start()
        time.sleep(0.4)
        manager.stop()
        self.assertIn("cam_01", manager.latest_results)
        self.assertTrue(manager.latest_results["cam_01"].escalations)
        self.assertEqual(manager.latest_results["cam_01"].escalations[-1]["severity"], "info")


if __name__ == "__main__":
    unittest.main()

