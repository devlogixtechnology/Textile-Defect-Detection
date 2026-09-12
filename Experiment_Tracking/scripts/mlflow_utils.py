from __future__ import annotations

from pathlib import Path
from typing import Mapping


def optional_mlflow():
    try:
        import mlflow  # type: ignore
    except ImportError:
        return None
    return mlflow


def configure_tracking(tracking_dir: str | Path = "Experiment_Tracking/mlruns", experiment_name: str = "Vision-Driven-Industrial-Safety"):
    mlflow = optional_mlflow()
    if mlflow is None:
        raise RuntimeError("MLflow is not installed. Install Experiment_Tracking/requirements-mlflow.txt first.")
    tracking_path = Path(tracking_dir)
    tracking_path.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_path.resolve().as_uri())
    mlflow.set_experiment(experiment_name)
    return mlflow


def log_registry_run(row: Mapping[str, str], tracking_dir: str | Path = "Experiment_Tracking/mlruns") -> str:
    mlflow = configure_tracking(tracking_dir)
    with mlflow.start_run(run_name=row["run_name"]) as run:
        for key in ("sprint", "task", "stage", "experiment_type", "tracking_origin", "status"):
            if row.get(key):
                mlflow.set_tag(key, row[key])
        for key, value in row.items():
            if key in {"precision", "recall", "map50", "map50_95", "false_alerts", "missed_violations", "fp_reduction_pct", "mean_alert_latency"}:
                try:
                    mlflow.log_metric(key, float(value))
                    continue
                except (TypeError, ValueError):
                    pass
            if value not in ("", "not applicable"):
                mlflow.log_param(key, value[:250])
        return run.info.run_id
