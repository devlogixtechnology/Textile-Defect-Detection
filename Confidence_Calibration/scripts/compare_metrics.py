from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_metrics(path: str | Path) -> dict[str, str]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return next(csv.DictReader(f))


def as_float(metrics: dict[str, str], key: str) -> float:
    value = metrics.get(key, "")
    return float(value) if value not in ("", "None", None) else 0.0


def compare(baseline_path: str | Path, calibrated_path: str | Path) -> dict[str, float | bool]:
    baseline = read_metrics(baseline_path)
    calibrated = read_metrics(calibrated_path)
    baseline_fp = as_float(baseline, "false_alert_events")
    calibrated_fp = as_float(calibrated, "false_alert_events")
    missed = as_float(calibrated, "missed_events")
    if baseline_fp == 0:
        fp_reduction_pct = 0.0 if calibrated_fp == 0 else -100.0
    else:
        fp_reduction_pct = ((baseline_fp - calibrated_fp) / baseline_fp) * 100.0
    return {
        "baseline_false_alert_events": baseline_fp,
        "calibrated_false_alert_events": calibrated_fp,
        "false_alert_reduction_pct": fp_reduction_pct,
        "calibrated_missed_events": missed,
        "dod_pass": fp_reduction_pct >= 30.0 and missed == 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--calibrated", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = compare(args.baseline, args.calibrated)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result))
        writer.writeheader()
        writer.writerow(result)


if __name__ == "__main__":
    main()
