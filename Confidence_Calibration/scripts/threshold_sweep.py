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


THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]


def sweep(detections_path: str | Path, annotations_path: str | Path, baseline_config: str | Path, output: str | Path) -> None:
    rows = load_detection_rows(detections_path)
    events = load_annotations(annotations_path)
    base = yaml.safe_load(Path(baseline_config).read_text(encoding="utf-8"))
    alert_classes = base.get("alert_classes", [])
    out_rows = []

    for class_name in alert_classes:
        for threshold in THRESHOLDS:
            cfg = deepcopy(base)
            cfg.setdefault("classes", {})
            cfg["classes"].setdefault(class_name, {})
            cfg["classes"][class_name]["confidence"] = threshold
            tmp = Path(output).with_suffix(f".{class_name.replace(' ', '_')}.{threshold:.2f}.tmp.yaml")
            tmp.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            metrics = evaluate_alerts(rows, events, tmp, annotation_path=annotations_path)
            tmp.unlink(missing_ok=True)
            out_rows.append(
                {
                    "class": class_name,
                    "threshold": threshold,
                    "true_events_detected": metrics["true_events_detected"],
                    "missed_events": metrics["missed_events"],
                    "false_alert_events": metrics["false_alert_events"],
                    "false_alert_rate_per_min": metrics["false_alert_rate_per_min"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
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
    parser.add_argument("--baseline-config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sweep(args.detections, args.annotations, args.baseline_config, args.output)


if __name__ == "__main__":
    main()
