from __future__ import annotations

import argparse
import csv
from pathlib import Path

from mlflow_utils import log_registry_run, optional_mlflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Optionally backfill CSV registry rows into a local MLflow store.")
    parser.add_argument("--experiments", default="Experiment_Tracking/experiments.csv")
    parser.add_argument("--tracking-dir", default="Experiment_Tracking/mlruns")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with Path(args.experiments).open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if args.dry_run or optional_mlflow() is None:
        print(f"Rows available for MLflow backfill: {len(rows)}")
        if optional_mlflow() is None:
            print("MLflow is not installed; CSV registries remain the persistent source of truth.")
        return

    for row in rows:
        mlflow_id = log_registry_run(row, args.tracking_dir)
        print(f"{row['run_id']} -> {mlflow_id}")


if __name__ == "__main__":
    main()
