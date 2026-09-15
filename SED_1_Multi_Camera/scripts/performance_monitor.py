from __future__ import annotations

import platform
import statistics
from dataclasses import asdict
from typing import Any

from .models import ARCHITECTURE_VERSION, CameraMetrics


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def summarize_metrics(
    metrics: dict[str, CameraMetrics],
    detector_version: str,
    alert_policy_version: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    all_latency = [lat for m in metrics.values() for lat in m.latencies]
    all_inference = [sec for m in metrics.values() for sec in m.inference_times]
    eligible = sum(m.eligible for m in metrics.values())
    processed = sum(m.processed for m in metrics.values())
    overload = sum(m.overload_drops for m in metrics.values())
    started = min((m.started_at for m in metrics.values() if m.started_at is not None), default=None)
    ended = max((m.ended_at for m in metrics.values() if m.ended_at is not None), default=None)
    elapsed = max(0.000001, (ended or 0.0) - (started or 0.0)) if started is not None and ended is not None else 0.0
    per_camera = {}
    for camera_id, metric in metrics.items():
        per_camera[camera_id] = {
            "captured": metric.captured,
            "eligible": metric.eligible,
            "submitted": metric.submitted,
            "processed": metric.processed,
            "configured_skips": metric.configured_skips,
            "unexpected_drops": metric.overload_drops,
            "decode_failures": metric.decode_failures,
            "drop_rate_pct": metric.unexpected_drop_rate,
            "processed_fps": metric.processed_fps,
            "avg_latency_ms": statistics.fmean(metric.latencies) * 1000.0 if metric.latencies else 0.0,
            "p95_latency_ms": percentile(metric.latencies, 95) * 1000.0,
            "avg_queue_depth": statistics.fmean(metric.queue_depth_samples) if metric.queue_depth_samples else 0.0,
            "status": metric.status,
            "last_error": metric.last_error,
        }
    return {
        "architecture_version": ARCHITECTURE_VERSION,
        "detector_model_version": detector_version,
        "alert_policy_version": alert_policy_version,
        "benchmark_config": config,
        "environment": environment_metadata(),
        "summary": {
            "streams": len(metrics),
            "duration_seconds": elapsed,
            "aggregate_fps": processed / elapsed if elapsed > 0 else 0.0,
            "avg_fps_per_camera": (processed / elapsed / len(metrics)) if elapsed > 0 and metrics else 0.0,
            "avg_inference_latency_ms": statistics.fmean(all_inference) * 1000.0 if all_inference else 0.0,
            "avg_end_to_end_latency_ms": statistics.fmean(all_latency) * 1000.0 if all_latency else 0.0,
            "p95_end_to_end_latency_ms": percentile(all_latency, 95) * 1000.0,
            "eligible_frames": eligible,
            "processed_frames": processed,
            "unexpected_drops": overload,
            "unexpected_drop_rate_pct": (overload / eligible * 100.0) if eligible else 0.0,
        },
        "per_camera": per_camera,
    }


def environment_metadata() -> dict[str, Any]:
    meta: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "torch": "not installed",
        "ultralytics": "not installed",
        "cuda_available": False,
        "gpu": "not available",
        "cuda_version": "not available",
    }
    try:
        import torch  # type: ignore

        meta["torch"] = getattr(torch, "__version__", "unknown")
        meta["cuda_available"] = bool(torch.cuda.is_available())
        meta["cuda_version"] = getattr(torch.version, "cuda", None) or "not available"
        if torch.cuda.is_available():
            meta["gpu"] = torch.cuda.get_device_name(0)
            meta["gpu_memory_allocated_mb"] = torch.cuda.memory_allocated(0) / (1024 * 1024)
            meta["gpu_memory_reserved_mb"] = torch.cuda.memory_reserved(0) / (1024 * 1024)
    except Exception:
        pass
    try:
        import ultralytics  # type: ignore

        meta["ultralytics"] = getattr(ultralytics, "__version__", "unknown")
    except Exception:
        pass
    return meta


def metrics_to_dict(metrics: CameraMetrics) -> dict[str, Any]:
    return asdict(metrics)


