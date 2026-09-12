from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from pathlib import Path

import yaml

try:
    from .benchmark_alerts import evaluate_alerts, load_detection_rows
    from .benchmark_loader import load_annotations
except ImportError:
    from benchmark_alerts import evaluate_alerts, load_detection_rows
    from benchmark_loader import load_annotations


TEMPORAL_CANDIDATES = [
    (2, 3),
    (3, 5),
    (4, 6),
    (4, 7),
    (5, 8),
]


def sweep_temporal(
    detections_path: str | Path,
    annotations_path: str | Path,
    base_config_path: str | Path,
    output: str | Path,
) -> None:
    rows = load_detection_rows(detections_path)
    events = load_annotations(annotations_path)
    base = yaml.safe_load(Path(base_config_path).read_text(encoding="utf-8"))
    out_rows = []

    for required_frames, window_size in TEMPORAL_CANDIDATES:
        cfg = deepcopy(base)
        for class_name in cfg.get("alert_classes", []):
            cfg.setdefault("classes", {}).setdefault(class_name, {})
            cfg["classes"][class_name]["required_frames"] = required_frames
            cfg["classes"][class_name]["window_size"] = window_size
        tmp = Path(output).with_suffix(f".{required_frames}_of_{window_size}.tmp.yaml")
        tmp.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        metrics = evaluate_alerts(rows, events, tmp, annotation_path=annotations_path)
        tmp.unlink(missing_ok=True)
        out_rows.append(
            {
                "required_frames": required_frames,
                "window_size": window_size,
                "true_events_detected": metrics["true_events_detected"],
                "missed_events": metrics["missed_events"],
                "false_alert_events": metrics["false_alert_events"],
                "false_alert_rate_per_min": metrics["false_alert_rate_per_min"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "mean_latency_sec": metrics["mean_latency_sec"],
            }
        )

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detections", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sweep_temporal(args.detections, args.annotations, args.base_config, args.output)


if __name__ == "__main__":
    main()
