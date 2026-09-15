import queue
import threading
import time
import unittest

from SED_1_Multi_Camera.scripts.camera_source import SyntheticCameraSource
from SED_1_Multi_Camera.scripts.stream_manager import StreamWorker
from SED_1_Multi_Camera.scripts.models import CameraConfig, CameraMetrics


class FrameDropTests(unittest.TestCase):
    def test_queue_overflow_drops_old_frames(self):
        cfg = CameraConfig(camera_id="camera_01", name="A", source="synthetic", sampling_fps=None)
        frame_queue = queue.Queue(maxsize=1)
        metrics = CameraMetrics()
        stop = threading.Event()
        worker = StreamWorker(
            cfg,
            frame_queue,
            metrics,
            stop,
            source_factory=lambda _cfg: SyntheticCameraSource(source_fps=200.0, max_frames=8),
        )
        worker.start()
        worker.join(timeout=2.0)
        self.assertGreater(metrics.overload_drops, 0)
        self.assertEqual(frame_queue.qsize(), 1)

    def test_stream_failure_is_recorded_without_exception(self):
        cfg = CameraConfig(camera_id="camera_01", name="A", source="synthetic")
        frame_queue = queue.Queue(maxsize=1)
        metrics = CameraMetrics()
        stop = threading.Event()
        worker = StreamWorker(
            cfg,
            frame_queue,
            metrics,
            stop,
            source_factory=lambda _cfg: SyntheticCameraSource(source_fps=100.0, fail_after=0),
        )
        worker.start()
        worker.join(timeout=2.0)
        self.assertEqual(metrics.status, "ended")
        self.assertEqual(metrics.decode_failures, 1)


if __name__ == "__main__":
    unittest.main()


