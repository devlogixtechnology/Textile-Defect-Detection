from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
CME2_SCRIPTS = PROJECT_ROOT / "Confidence_Calibration" / "scripts"
if str(CME2_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CME2_SCRIPTS))

from SED_1_Multi_Camera.scripts.config import load_camera_configs
from SED_1_Multi_Camera.scripts.detector import NullDetector, SharedYOLODetector
from SED_1_Multi_Camera.scripts.models import ARCHITECTURE_VERSION
from SED_1_Multi_Camera.scripts.stream_manager import MultiCameraStreamManager
from SED_2_Alert_Escalation.scripts.factory import create_default_escalation_manager
from SED_2_Alert_Escalation.scripts.models import SEVERITY_POLICY_VERSION
from SED_3_Stress_Testing.scripts.analysis import (
    STRESS_VERSION,
    detect_memory_growth,
    summarize_values,
    windowed_summary,
)
from SED_3_Stress_Testing.scripts.resource_monitor import ResourceMonitor

try:
    from alert_policy import AlertPolicy, load_policy_config
except Exception as exc:  # pragma: no cover
    AlertPolicy = None
    load_policy_config = None
    ALERT_IMPORT_ERROR = exc
else:
    ALERT_IMPORT_ERROR = None


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required for SED-3 stress config loading.") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _as_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _latency_stats(manager: MultiCameraStreamManager) -> tuple[list[float], list[float]]:
    inference = [sec * 1000.0 for metric in manager.metrics.values() for sec in metric.inference_times]
    e2e = [sec * 1000.0 for metric in manager.metrics.values() for sec in metric.latencies]
    return inference, e2e


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _metric_snapshot(
    manager: MultiCameraStreamManager,
    resource_monitor: ResourceMonitor,
    started_at: float,
    previous_processed: dict[str, int],
    previous_elapsed: float,
) -> tuple[dict[str, Any], dict[str, int], float]:
    elapsed = time.perf_counter() - started_at
    row: dict[str, Any] = {"elapsed_seconds": elapsed, "timestamp": time.time()}
    total_processed = 0
    total_delta = 0
    total_queue = 0
    total_drops = 0
    total_eligible = 0
    for camera_id, metric in manager.metrics.items():
        processed = metric.processed
        total_processed += processed
        delta = processed - previous_processed.get(camera_id, 0)
        total_delta += delta
        interval = max(0.000001, elapsed - previous_elapsed)
        row[f"{camera_id}_fps_window"] = delta / interval
        row[f"{camera_id}_processed"] = processed
        row[f"{camera_id}_eligible"] = metric.eligible
        row[f"{camera_id}_drop_pct"] = metric.unexpected_drop_rate
        queue_depth = manager.queues[camera_id].qsize()
        row[f"{camera_id}_queue_depth"] = queue_depth
        total_queue += queue_depth
        total_drops += metric.overload_drops
        total_eligible += metric.eligible
    interval = max(0.000001, elapsed - previous_elapsed)
    row["aggregate_fps_window"] = total_delta / interval
    row["aggregate_processed"] = total_processed
    row["queue_depth_total"] = total_queue
    row["unexpected_drops"] = total_drops
    row["eligible_frames"] = total_eligible
    row["drop_pct"] = (total_drops / total_eligible * 100.0) if total_eligible else 0.0
    _inf, e2e = _latency_stats(manager)
    recent_e2e = e2e[-100:]
    row["mean_latency_ms_recent"] = sum(recent_e2e) / len(recent_e2e) if recent_e2e else 0.0
    row["p95_latency_ms_recent"] = sorted(recent_e2e)[int(0.95 * (len(recent_e2e) - 1))] if len(recent_e2e) > 1 else (recent_e2e[0] if recent_e2e else 0.0)
    row["active_streams"] = sum(1 for metric in manager.metrics.values() if metric.status in {"running", "ended", "stopped"})
    row["scheduler_alive"] = manager.scheduler_thread.is_alive()
    if resource_monitor.samples:
        row.update(resource_monitor.samples[-1].to_dict())
    return row, {cid: metric.processed for cid, metric in manager.metrics.items()}, elapsed


def run_stress(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    cfg = _load_yaml(config_path)["stress_test"]
    duration = float(args.duration_seconds if args.duration_seconds is not None else cfg["duration_seconds"])
    warmup_seconds = float(args.warmup_seconds if args.warmup_seconds is not None else cfg.get("warmup_seconds", 0.0))
    sample_interval = float(args.sample_interval if args.sample_interval is not None else cfg["resource_sample_interval_seconds"])
    streams = int(args.streams if args.streams is not None else cfg["streams"])
    queue_size = int(args.queue_size if args.queue_size is not None else cfg.get("queue_size", 2))
    imgsz = int(args.imgsz if args.imgsz is not None else cfg["inference"]["imgsz"])
    device = args.device if args.device is not None else cfg["inference"].get("device")
    reports_dir = _as_path(args.output_dir or cfg["outputs"]["directory"])
    reports_dir.mkdir(parents=True, exist_ok=True)

    if AlertPolicy is None or load_policy_config is None:
        raise RuntimeError(f"CME-2 alert policy is unavailable: {ALERT_IMPORT_ERROR}")

    cameras = load_camera_configs(_as_path(cfg["configs"]["cameras"]), limit=streams)
    detector = NullDetector() if args.detector == "null" else SharedYOLODetector(_as_path(cfg["inference"]["weights"]), device=device, imgsz=imgsz)
    escalation_manager = create_default_escalation_manager(PROJECT_ROOT, log_path=None)
    policy_path = _as_path(cfg["configs"]["cme2_alert_policy"])
    manager = MultiCameraStreamManager(
        cameras,
        detector,
        alert_policy_factory=lambda: AlertPolicy(load_policy_config(policy_path)),
        escalation_manager=escalation_manager,
        queue_size=queue_size,
        micro_batch=bool(cfg.get("micro_batch", True)),
    )
    monitor = ResourceMonitor(interval_seconds=sample_interval, enable_gpu=bool(cfg["monitoring"].get("gpu", True)))
    timeseries: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    status = "completed"
    failure_reason = None
    started_at = time.perf_counter()
    previous_processed: dict[str, int] = {}
    previous_elapsed = 0.0
    try:
        monitor.start()
        manager.start()
        next_sample = time.perf_counter()
        deadline = started_at + duration
        while time.perf_counter() < deadline:
            now = time.perf_counter()
            if now >= next_sample:
                row, previous_processed, previous_elapsed = _metric_snapshot(
                    manager, monitor, started_at, previous_processed, previous_elapsed
                )
                row["warmup"] = row["elapsed_seconds"] < warmup_seconds
                timeseries.append(row)
                next_sample = now + sample_interval
                if not manager.scheduler_thread.is_alive():
                    status = "failed"
                    failure_reason = "scheduler thread stopped unexpectedly"
                    break
            time.sleep(min(0.1, sample_interval / 5.0))
    except Exception as exc:
        status = "failed"
        failure_reason = str(exc)
        exceptions.append(
            {
                "timestamp": time.time(),
                "component": "run_stress",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        manager.stop()
        monitor.stop()
        row, previous_processed, previous_elapsed = _metric_snapshot(manager, monitor, started_at, previous_processed, previous_elapsed)
        row["warmup"] = row["elapsed_seconds"] < warmup_seconds
        timeseries.append(row)

    completed_duration = time.perf_counter() - started_at
    outputs = cfg["outputs"]
    timeseries_path = reports_dir / outputs["timeseries_csv"]
    _write_csv(timeseries_path, timeseries)
    inference_ms, e2e_ms = _latency_stats(manager)
    resource_rows = [sample.to_dict() for sample in monitor.samples]
    ram_values = [float(row["process_rss_mb"]) for row in resource_rows if row.get("process_rss_mb") is not None]
    cpu_values = [float(row["cpu_percent"]) for row in resource_rows if row.get("cpu_percent") is not None]
    process_cpu_values = [float(row["process_cpu_percent"]) for row in resource_rows if row.get("process_cpu_percent") is not None]
    gpu_util_values = [float(row["gpu_util_percent"]) for row in resource_rows if row.get("gpu_util_percent") is not None]
    gpu_memory_values = [
        float(row["gpu_memory_used_mb"])
        for row in resource_rows
        if row.get("gpu_memory_used_mb") is not None
    ]
    thread_values = [int(row["thread_count"]) for row in resource_rows if row.get("thread_count") is not None]
    total_eligible = sum(metric.eligible for metric in manager.metrics.values())
    total_processed = sum(metric.processed for metric in manager.metrics.values())
    total_drops = sum(metric.overload_drops for metric in manager.metrics.values())
    per_camera = {}
    for camera_id, metric in manager.metrics.items():
        elapsed = max(0.000001, completed_duration)
        per_camera[camera_id] = {
            "processed": metric.processed,
            "eligible": metric.eligible,
            "captured": metric.captured,
            "configured_skips": metric.configured_skips,
            "unexpected_drops": metric.overload_drops,
            "drop_pct": metric.unexpected_drop_rate,
            "mean_fps": metric.processed / elapsed,
            "decode_failures": metric.decode_failures,
            "status": metric.status,
            "last_error": metric.last_error,
        }
    ram_growth = detect_memory_growth(timeseries, "process_rss_mb", warmup_seconds=warmup_seconds)
    gpu_growth = detect_memory_growth(timeseries, "gpu_memory_used_mb", warmup_seconds=warmup_seconds) if gpu_memory_values else {
        "leak_detected": False,
        "reason": "GPU telemetry unavailable",
        "slope_mb_per_min": 0.0,
    }
    queue_depths = [float(row["queue_depth_total"]) for row in timeseries if "queue_depth_total" in row]
    summary: dict[str, Any] = {
        "stress_version": STRESS_VERSION,
        "status": status,
        "failure_reason": failure_reason,
        "duration_seconds_configured": duration,
        "duration_seconds_measured": completed_duration,
        "warmup_seconds": warmup_seconds,
        "stream_count": streams,
        "detector_model_version": "cme1-expanded-12class-v1",
        "alert_policy_version": "cme2-alert-calibrated-v1",
        "multicamera_version": ARCHITECTURE_VERSION,
        "severity_policy_version": SEVERITY_POLICY_VERSION,
        "device": device,
        "imgsz": imgsz,
        "queue_size": queue_size,
        "detector": args.detector,
        "frames_processed": total_processed,
        "eligible_frames": total_eligible,
        "unexpected_drops": total_drops,
        "frame_drop_pct": (total_drops / total_eligible * 100.0) if total_eligible else 0.0,
        "aggregate_fps": total_processed / max(0.000001, completed_duration),
        "per_camera": per_camera,
        "inference_latency_ms": summarize_values(inference_ms),
        "end_to_end_latency_ms": summarize_values(e2e_ms),
        "cpu": {
            "mean_percent": sum(cpu_values) / len(cpu_values) if cpu_values else None,
            "peak_percent": max(cpu_values) if cpu_values else None,
            "process_mean_percent": sum(process_cpu_values) / len(process_cpu_values) if process_cpu_values else None,
            "process_peak_percent": max(process_cpu_values) if process_cpu_values else None,
        },
        "ram": {
            "start_mb": ram_values[0] if ram_values else None,
            "mean_mb": sum(ram_values) / len(ram_values) if ram_values else None,
            "peak_mb": max(ram_values) if ram_values else None,
            "end_mb": ram_values[-1] if ram_values else None,
        },
        "gpu": {
            "available": bool(gpu_memory_values or gpu_util_values),
            "utilization_mean_percent": sum(gpu_util_values) / len(gpu_util_values) if gpu_util_values else None,
            "utilization_peak_percent": max(gpu_util_values) if gpu_util_values else None,
            "memory_start_mb": gpu_memory_values[0] if gpu_memory_values else None,
            "memory_mean_mb": sum(gpu_memory_values) / len(gpu_memory_values) if gpu_memory_values else None,
            "memory_peak_mb": max(gpu_memory_values) if gpu_memory_values else None,
            "memory_end_mb": gpu_memory_values[-1] if gpu_memory_values else None,
        },
        "stability": {
            "exceptions": exceptions,
            "monitor_exceptions": monitor.exceptions,
            "worker_crashes": [
                {"camera_id": camera_id, "error": metric.last_error}
                for camera_id, metric in manager.metrics.items()
                if metric.last_error
            ],
            "scheduler_alive_at_shutdown_sample": timeseries[-1].get("scheduler_alive") if timeseries else None,
            "thread_count_start": thread_values[0] if thread_values else None,
            "thread_count_peak": max(thread_values) if thread_values else None,
            "thread_count_end": thread_values[-1] if thread_values else None,
            "queue_depth_mean": sum(queue_depths) / len(queue_depths) if queue_depths else 0.0,
            "queue_depth_peak": max(queue_depths) if queue_depths else 0.0,
            "ram_growth": ram_growth,
            "gpu_memory_growth": gpu_growth,
            "memory_leak_detected": bool(ram_growth["leak_detected"] or gpu_growth["leak_detected"]),
        },
        "windows": windowed_summary(
            timeseries,
            window_seconds=float(args.window_seconds),
            max_elapsed_seconds=duration,
        ),
        "outputs": {
            "timeseries_csv": str(timeseries_path),
            "summary_json": str(reports_dir / outputs["summary_json"]),
        },
    }
    summary_path = reports_dir / outputs["summary_json"]
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    latency_rows = [
        {"metric": key, "inference_latency_ms": value, "end_to_end_latency_ms": summary["end_to_end_latency_ms"][key]}
        for key, value in summary["inference_latency_ms"].items()
    ]
    _write_csv(reports_dir / outputs["latency_summary_csv"], latency_rows)
    resource_rows_summary = [
        {"resource": "Process RAM MB", **summary["ram"]},
        {"resource": "CPU Utilization Percent", "start_mb": None, "mean_mb": summary["cpu"]["mean_percent"], "peak_mb": summary["cpu"]["peak_percent"], "end_mb": None},
        {"resource": "GPU Memory MB", "start_mb": summary["gpu"]["memory_start_mb"], "mean_mb": summary["gpu"]["memory_mean_mb"], "peak_mb": summary["gpu"]["memory_peak_mb"], "end_mb": summary["gpu"]["memory_end_mb"]},
    ]
    _write_csv(reports_dir / outputs["resource_summary_csv"], resource_rows_summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SED-3 integrated stress test.")
    parser.add_argument("--config", default=PROJECT_ROOT / "SED_3_Stress_Testing" / "configs" / "stress_test.yaml")
    parser.add_argument("--duration-seconds", type=float, default=None)
    parser.add_argument("--warmup-seconds", type=float, default=None)
    parser.add_argument("--sample-interval", type=float, default=None)
    parser.add_argument("--streams", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--queue-size", type=int, default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--detector", choices=["yolo", "null"], default="yolo")
    parser.add_argument("--window-seconds", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    summary = run_stress(parse_args())
    print(json.dumps({
        "status": summary["status"],
        "duration_seconds_measured": summary["duration_seconds_measured"],
        "frames_processed": summary["frames_processed"],
        "aggregate_fps": summary["aggregate_fps"],
        "frame_drop_pct": summary["frame_drop_pct"],
        "memory_leak_detected": summary["stability"]["memory_leak_detected"],
    }, indent=2))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
