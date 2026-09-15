from __future__ import annotations

import math
import statistics
from typing import Any


STRESS_VERSION = "SED3-stress-v1"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[index]


def summarize_values(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": statistics.fmean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "min": min(values),
        "max": max(values),
    }


def linear_slope(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom


def detect_memory_growth(samples: list[dict[str, Any]], field: str, warmup_seconds: float = 0.0) -> dict[str, Any]:
    usable = [
        row for row in samples
        if float(row.get("elapsed_seconds", 0.0)) >= warmup_seconds and row.get(field) not in (None, "", "NA")
    ]
    if len(usable) < 4:
        return {"leak_detected": False, "reason": "insufficient samples", "slope_mb_per_min": 0.0}
    xs = [float(row["elapsed_seconds"]) / 60.0 for row in usable]
    ys = [float(row[field]) for row in usable]
    slope = linear_slope(xs, ys)
    span = max(ys) - min(ys)
    first_window = ys[: max(1, len(ys) // 4)]
    last_window = ys[-max(1, len(ys) // 4):]
    window_growth = statistics.fmean(last_window) - statistics.fmean(first_window)
    # A modest positive slope can be normal cache behavior. Flag only sustained,
    # material growth relative to both total span and window means.
    leak = slope > 5.0 and window_growth > max(50.0, 0.10 * max(1.0, statistics.fmean(first_window)))
    reason = (
        f"slope={slope:.3f} MB/min, final-window growth={window_growth:.3f} MB, "
        f"span={span:.3f} MB"
    )
    return {"leak_detected": leak, "reason": reason, "slope_mb_per_min": slope}


def windowed_summary(
    samples: list[dict[str, Any]],
    window_seconds: float = 300.0,
    max_elapsed_seconds: float | None = None,
) -> list[dict[str, Any]]:
    if not samples:
        return []
    max_elapsed = max_elapsed_seconds if max_elapsed_seconds is not None else max(
        float(row.get("elapsed_seconds", 0.0)) for row in samples
    )
    windows = []
    start = 0.0
    while start < max_elapsed + 1e-9:
        end = start + window_seconds
        rows = [
            row for row in samples
            if start <= float(row.get("elapsed_seconds", 0.0)) < min(end, max_elapsed + 1e-9)
        ]
        if rows:
            fps = [float(row.get("aggregate_fps_window", 0.0)) for row in rows]
            latency = [float(row.get("mean_latency_ms_recent", 0.0)) for row in rows if float(row.get("mean_latency_ms_recent", 0.0)) > 0]
            p95_latency = [float(row.get("p95_latency_ms_recent", 0.0)) for row in rows if float(row.get("p95_latency_ms_recent", 0.0)) > 0]
            ram = [float(row.get("process_rss_mb", 0.0)) for row in rows if float(row.get("process_rss_mb", 0.0)) > 0]
            gpu_mem = [
                float(row.get("gpu_memory_used_mb", 0.0))
                for row in rows
                if row.get("gpu_memory_used_mb") not in (None, "", "NA")
            ]
            windows.append(
                {
                    "window": f"{int(start // 60)}-{int(end // 60)} min",
                    "mean_fps": statistics.fmean(fps) if fps else 0.0,
                    "mean_latency_ms": statistics.fmean(latency) if latency else 0.0,
                    "p95_latency_ms": max(p95_latency) if p95_latency else 0.0,
                    "mean_ram_mb": statistics.fmean(ram) if ram else 0.0,
                    "mean_gpu_memory_mb": statistics.fmean(gpu_mem) if gpu_mem else None,
                }
            )
        start = end
    return windows
