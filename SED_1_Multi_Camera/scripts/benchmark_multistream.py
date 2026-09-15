from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
CME2_SCRIPTS = PROJECT_ROOT / "Confidence_Calibration" / "scripts"
if str(CME2_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CME2_SCRIPTS))

from SED_1_Multi_Camera.scripts.config import load_benchmark_config, load_camera_configs
from SED_1_Multi_Camera.scripts.detector import NullDetector, SharedYOLODetector
from SED_1_Multi_Camera.scripts.performance_monitor import summarize_metrics
from SED_1_Multi_Camera.scripts.stream_manager import MultiCameraStreamManager

try:
    from alert_policy import AlertPolicy, load_policy_config
except Exception:
    AlertPolicy = None
    load_policy_config = None


def make_alert_policy(policy_path: Path):
    if AlertPolicy is None or load_policy_config is None:
        raise RuntimeError("CME-2 alert_policy.py is required for benchmark alert processing.")
    return AlertPolicy(load_policy_config(policy_path))


def run_benchmark(args: argparse.Namespace) -> dict:
    benchmark_cfg = load_benchmark_config(args.benchmark_config)
    cameras = load_camera_configs(args.camera_config, limit=args.streams)
    if len(cameras) < args.streams:
        raise RuntimeError(f"Requested {args.streams} streams but only {len(cameras)} enabled cameras are configured.")
    detector = (
        NullDetector()
        if args.detector == "null"
        else SharedYOLODetector(args.weights, device=args.device, imgsz=args.imgsz)
    )
    policy_path = PROJECT_ROOT / "Confidence_Calibration" / "configs" / "calibrated_thresholds.yaml"
    if args.warmup_seconds > 0:
        warmup_manager = MultiCameraStreamManager(
            cameras,
            detector,
            alert_policy_factory=lambda: make_alert_policy(policy_path),
            queue_size=args.queue_size,
            micro_batch=not args.no_batch,
        )
        warmup_manager.start()
        time.sleep(args.warmup_seconds)
        warmup_manager.stop()
    manager = MultiCameraStreamManager(
        cameras,
        detector,
        alert_policy_factory=lambda: make_alert_policy(policy_path),
        queue_size=args.queue_size,
        micro_batch=not args.no_batch,
    )
    manager.start()
    time.sleep(args.duration_seconds)
    manager.stop()
    cfg = {
        **benchmark_cfg.get("benchmark", {}),
        "streams": args.streams,
        "duration_seconds": args.duration_seconds,
        "warmup_seconds": args.warmup_seconds,
        "imgsz": args.imgsz,
        "device": args.device,
        "queue_size": args.queue_size,
        "micro_batch": not args.no_batch,
        "detector": args.detector,
        "weights": str(args.weights),
    }
    return summarize_metrics(
        manager.metrics,
        detector_version="cme1-expanded-12class-v1",
        alert_policy_version="cme2-alert-calibrated-v1",
        config=cfg,
    )


def write_outputs(result: dict, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    streams = result["summary"]["streams"]
    json_path = reports_dir / f"benchmark_{streams}_stream{'s' if streams != 1 else ''}.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary_path = reports_dir / "benchmark_summary.csv"
    rows = []
    if summary_path.exists():
        with summary_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        rows = [row for row in rows if int(row["streams"]) != streams]
    summary = result["summary"]
    rows.append(
        {
            "streams": streams,
            "aggregate_fps": f"{summary['aggregate_fps']:.3f}",
            "avg_fps_per_camera": f"{summary['avg_fps_per_camera']:.3f}",
            "avg_latency_ms": f"{summary['avg_end_to_end_latency_ms']:.3f}",
            "p95_latency_ms": f"{summary['p95_end_to_end_latency_ms']:.3f}",
            "drop_rate_pct": f"{summary['unexpected_drop_rate_pct']:.3f}",
            "eligible_frames": summary["eligible_frames"],
            "processed_frames": summary["processed_frames"],
            "unexpected_drops": summary["unexpected_drops"],
        }
    )
    rows.sort(key=lambda row: int(row["streams"]))
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark SED-1 concurrent camera streams.")
    parser.add_argument("--streams", type=int, choices=[1, 2, 3, 4], required=True)
    parser.add_argument("--camera-config", default=PROJECT_ROOT / "SED_1_Multi_Camera" / "configs" / "cameras.yaml")
    parser.add_argument("--benchmark-config", default=PROJECT_ROOT / "SED_1_Multi_Camera" / "configs" / "benchmark.yaml")
    parser.add_argument("--weights", default=PROJECT_ROOT / "Backend" / "best.pt")
    parser.add_argument("--device", default=None)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--queue-size", type=int, default=2)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--warmup-seconds", type=float, default=5.0)
    parser.add_argument("--no-batch", action="store_true", help="Disable one-frame-per-camera micro-batching.")
    parser.add_argument("--detector", choices=["yolo", "null"], default="yolo")
    parser.add_argument("--reports-dir", default=PROJECT_ROOT / "SED_1_Multi_Camera" / "reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_benchmark(args)
    write_outputs(result, Path(args.reports_dir))
    print(json.dumps(result["summary"], indent=2))
    if args.detector == "null":
        print("WARNING: null detector validates architecture only and is not a SED-1 DoD benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


