from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

try:
    from .alert_policy import AlertPolicy, load_policy_config, normalize_class_name
    from .benchmark_loader import TemporalEvent, load_annotations, load_clip_metadata
except ImportError:
    from alert_policy import AlertPolicy, load_policy_config, normalize_class_name
    from benchmark_loader import TemporalEvent, load_annotations, load_clip_metadata


def load_detection_rows(path: str | Path) -> list[dict]:
    def numeric(value: str | None, default: float = 0.0) -> float:
        return float(value) if value not in ("", None) else default

    with Path(path).open("r", encoding="utf-8", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            class_name = normalize_class_name(row.get("class", ""))
            rows.append(
                {
                    "clip": row["clip"],
                    "frame_index": int(row["frame_index"]),
                    "timestamp_sec": float(row["timestamp_sec"]),
                    "class_name": class_name,
                    "confidence": float(row["confidence"]) if row.get("confidence") else 0.0,
                    "coordinates": {
                        "x1": numeric(row.get("x1")),
                        "y1": numeric(row.get("y1")),
                        "x2": numeric(row.get("x2")),
                        "y2": numeric(row.get("y2")),
                    },
                    "is_detection": bool(class_name),
                }
            )
    return rows


def event_for_alert(alert: dict, events: list[TemporalEvent]) -> TemporalEvent | None:
    cls = normalize_class_name(alert["class_name"])
    t = float(alert["timestamp_sec"] or 0.0)
    for event in events:
        if normalize_class_name(event.class_name) == cls and event.start_sec <= t <= event.end_sec:
            return event
    return None


def evaluate_alerts(
    rows: list[dict],
    events: list[TemporalEvent],
    config_path: str | Path,
    annotation_path: str | Path | None = None,
) -> dict:
    config = load_policy_config(config_path)
    rows_by_clip = defaultdict(list)
    events_by_clip = defaultdict(list)
    for row in rows:
        rows_by_clip[row["clip"]].append(row)
    for event in events:
        events_by_clip[event.clip].append(event)

    alerts = []
    for clip, clip_rows in rows_by_clip.items():
        policy = AlertPolicy(config)
        frames = defaultdict(list)
        for row in sorted(clip_rows, key=lambda r: r["frame_index"]):
            frames[row["frame_index"]].append(row)
        for frame_index, detections in frames.items():
            timestamp = min(d["timestamp_sec"] for d in detections)
            real_detections = [d for d in detections if d.get("is_detection", True)]
            for alert in policy.process_frame(real_detections, frame_index, timestamp)["alerts"]:
                alert["clip"] = clip
                alerts.append(alert)

    detected_events = set()
    false_alerts = 0
    latencies = []
    false_alerts_by_class = defaultdict(int)
    latencies_by_class = defaultdict(list)
    for alert in alerts:
        match = event_for_alert(alert, events_by_clip.get(alert["clip"], []))
        if match is None:
            false_alerts += 1
            false_alerts_by_class[normalize_class_name(alert["class_name"])] += 1
        else:
            event_key = (match.clip, normalize_class_name(match.class_name), match.start_sec, match.end_sec)
            detected_events.add(event_key)
            latency = float(alert["timestamp_sec"] or 0.0) - match.start_sec
            latencies.append(latency)
            latencies_by_class[normalize_class_name(match.class_name)].append(latency)

    total_events = len(events)
    true_alerts = len(detected_events)
    missed = total_events - true_alerts
    precision = true_alerts / (true_alerts + false_alerts) if true_alerts + false_alerts else 0.0
    recall = true_alerts / total_events if total_events else 0.0
    total_duration_sec = None
    if annotation_path is not None:
        durations = [c.duration_sec for c in load_clip_metadata(annotation_path) if c.duration_sec is not None]
        if durations:
            total_duration_sec = sum(durations)
    false_alert_rate_per_min = None
    if total_duration_sec:
        false_alert_rate_per_min = false_alerts / (total_duration_sec / 60.0)
    classes = sorted({normalize_class_name(e.class_name) for e in events} | set(false_alerts_by_class))
    per_class = []
    for class_name in classes:
        class_events = [e for e in events if normalize_class_name(e.class_name) == class_name]
        class_detected = {key for key in detected_events if key[1] == class_name}
        class_true = len(class_detected)
        class_fp = false_alerts_by_class[class_name]
        class_total = len(class_events)
        per_class.append(
            {
                "class": class_name,
                "total_true_events": class_total,
                "true_events_detected": class_true,
                "missed_events": class_total - class_true,
                "false_alert_events": class_fp,
                "precision": class_true / (class_true + class_fp) if class_true + class_fp else 0.0,
                "recall": class_true / class_total if class_total else 0.0,
                "mean_latency_sec": sum(latencies_by_class[class_name]) / len(latencies_by_class[class_name])
                if latencies_by_class[class_name]
                else None,
            }
        )
    return {
        "total_true_events": total_events,
        "true_events_detected": true_alerts,
        "missed_events": missed,
        "false_alert_events": false_alerts,
        "false_alert_rate_per_min": false_alert_rate_per_min,
        "precision": precision,
        "recall": recall,
        "mean_latency_sec": sum(latencies) / len(latencies) if latencies else None,
        "alerts": alerts,
        "per_class": per_class,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detections", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-class-output")
    args = parser.parse_args()

    metrics = evaluate_alerts(
        load_detection_rows(args.detections),
        load_annotations(args.annotations),
        args.config,
        annotation_path=args.annotations,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[k for k in metrics if k not in {"alerts", "per_class"}])
        writer.writeheader()
        writer.writerow({k: v for k, v in metrics.items() if k not in {"alerts", "per_class"}})

    if args.per_class_output:
        per_class_out = Path(args.per_class_output)
        per_class_out.parent.mkdir(parents=True, exist_ok=True)
        with per_class_out.open("w", encoding="utf-8", newline="") as f:
            fieldnames = list(metrics["per_class"][0]) if metrics["per_class"] else ["class"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metrics["per_class"])


if __name__ == "__main__":
    main()
