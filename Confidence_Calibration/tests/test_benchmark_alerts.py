import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_alerts import evaluate_alerts, load_detection_rows
from benchmark_loader import load_annotations


class BenchmarkAlertTests(unittest.TestCase):
    def test_empty_frames_prevent_single_spike_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detections = tmp_path / "detections.csv"
            annotations = tmp_path / "annotations.json"
            config = tmp_path / "config.yaml"

            with detections.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["clip", "frame_index", "timestamp_sec", "class", "confidence", "x1", "y1", "x2", "y2"],
                )
                writer.writeheader()
                for i, detected in enumerate([False, False, True, False, False]):
                    writer.writerow(
                        {
                            "clip": "clip.mp4",
                            "frame_index": i,
                            "timestamp_sec": float(i),
                            "class": "fire" if detected else "",
                            "confidence": 0.95 if detected else "",
                            "x1": 0,
                            "y1": 0,
                            "x2": 10,
                            "y2": 10,
                        }
                    )

            annotations.write_text(
                '{"clips":[{"clip":"clip.mp4","duration_sec":5,"events":[]}]}',
                encoding="utf-8",
            )
            config.write_text(
                "\n".join(
                    [
                        "default_confidence: 0.25",
                        "process_fps: 1.0",
                        "alert_classes:",
                        "  - fire",
                        "classes:",
                        "  fire:",
                        "    confidence: 0.25",
                        "    window_size: 5",
                        "    required_frames: 3",
                        "    cooldown_frames: 0",
                        "    clear_frames: 1",
                    ]
                ),
                encoding="utf-8",
            )

            metrics = evaluate_alerts(load_detection_rows(detections), load_annotations(annotations), config, annotations)
            self.assertEqual(metrics["false_alert_events"], 0)


if __name__ == "__main__":
    unittest.main()
