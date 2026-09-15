import time
import unittest

from SED_1_Multi_Camera.scripts.camera_source import SyntheticCameraSource
from SED_1_Multi_Camera.scripts.stream_manager import MultiCameraStreamManager
from SED_1_Multi_Camera.scripts.models import CameraConfig, GeofenceConfig


class FakeDetector:
    def predict_batch(self, frames):
        detections = []
        for _frame in frames:
            detections.append(
                [
                    {
                        "class_name": "fire",
                        "confidence": 0.9,
                        "coordinates": {"x1": 20, "y1": 20, "x2": 80, "y2": 80},
                    }
                ]
            )
        return detections, 0.001


class FakePolicy:
    def __init__(self):
        self.seen = 0

    def process_frame(self, detections, frame_index, timestamp_sec=None):
        self.seen += 1
        alerts = []
        if self.seen == 2 and detections:
            alerts.append({"class_name": detections[0]["class_name"], "state": "confirmed", "frame_index": frame_index})
        return {"calibrated_detections": detections, "alerts": alerts}


def camera(camera_id):
    return CameraConfig(
        camera_id=camera_id,
        name=camera_id,
        source="synthetic",
        sampling_fps=20.0,
        monitored_classes={"fire"},
        geofences=[
            GeofenceConfig(
                id="whole_frame",
                polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
                classes={"fire"},
            )
        ],
    )


class StreamIsolationTests(unittest.TestCase):
    def test_results_and_alert_state_are_per_camera(self):
        manager = MultiCameraStreamManager(
            [camera("camera_01"), camera("camera_02")],
            FakeDetector(),
            alert_policy_factory=FakePolicy,
            queue_size=2,
            source_factory=lambda _cfg: SyntheticCameraSource(source_fps=30.0, max_frames=4),
        )
        manager.start()
        time.sleep(0.5)
        manager.stop()
        self.assertIn("camera_01", manager.latest_results)
        self.assertIn("camera_02", manager.latest_results)
        self.assertEqual(manager.latest_results["camera_01"].camera_id, "camera_01")
        self.assertEqual(manager.latest_results["camera_02"].camera_id, "camera_02")
        alert_cameras = {alert["camera_id"] for alert in manager.active_alerts}
        self.assertEqual(alert_cameras, {"camera_01", "camera_02"})

    def test_shutdown_terminates_workers(self):
        manager = MultiCameraStreamManager(
            [camera("camera_01")],
            FakeDetector(),
            queue_size=1,
            source_factory=lambda _cfg: SyntheticCameraSource(source_fps=20.0),
        )
        manager.start()
        time.sleep(0.1)
        manager.stop(timeout=1.0)
        self.assertTrue(all(not worker.thread.is_alive() for worker in manager.workers))


if __name__ == "__main__":
    unittest.main()


