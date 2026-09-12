from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


VALID_SPRINTS = {"Pre-Sprint-4", "Sprint 4"}
VALID_TASKS = {"Baseline", "CME-1", "CME-2", "CME-3"}
MODEL_EXPERIMENT_TYPES = {"model_training"}
CALIBRATION_EXPERIMENT_TYPES = {"calibration"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def is_missing(value: str | None) -> bool:
    return value in (None, "", "unknown", "not recorded", "missing")


def check_unique(rows: list[dict[str, str]], field: str, errors: list[str], path: Path) -> None:
    seen: set[str] = set()
    for row in rows:
        value = row.get(field, "")
        if value in seen:
            errors.append(f"{path}: duplicate {field}: {value}")
        seen.add(value)


def check_file_reference(root: Path, value: str, errors: list[str], context: str) -> None:
    if is_missing(value) or value.startswith("Google Drive") or value.startswith("Drive "):
        return
    first = value.split(";", 1)[0].strip()
    if first.startswith("/content") or first.startswith("/home/"):
        return
    if not (root / first).exists():
        errors.append(f"{context}: referenced file does not exist: {first}")


def validate(root: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    tracking = root / "Experiment_Tracking"
    experiments_path = tracking / "experiments.csv"
    model_registry_path = tracking / "model_registry.csv"
    alert_registry_path = tracking / "alert_policy_registry.csv"

    experiments = read_csv(experiments_path)
    models = read_csv(model_registry_path)
    policies = read_csv(alert_registry_path)

    check_unique(experiments, "run_id", errors, experiments_path)
    check_unique(models, "model_version", errors, model_registry_path)
    check_unique(policies, "policy_version", errors, alert_registry_path)

    model_versions = {row["model_version"] for row in models}
    policy_versions = {row["policy_version"] for row in policies}

    for row in experiments:
        run_id = row["run_id"]
        if row["sprint"] not in VALID_SPRINTS:
            errors.append(f"{run_id}: invalid sprint {row['sprint']}")
        if row["task"] not in VALID_TASKS:
            errors.append(f"{run_id}: invalid task {row['task']}")
        if row["experiment_type"] in MODEL_EXPERIMENT_TYPES:
            if row["model_version"] not in model_versions:
                errors.append(f"{run_id}: model_version missing from model registry")
            if is_missing(row["map50"]):
                warnings.append(f"{run_id}: mAP@50 not recorded in available artifacts")
            if is_missing(row["best_weight_uri"]):
                errors.append(f"{run_id}: model run missing best_weight_uri")
        if row["experiment_type"] in CALIBRATION_EXPERIMENT_TYPES:
            if row["model_version"] not in model_versions:
                errors.append(f"{run_id}: calibration detector model_version missing from model registry")
            if row["alert_policy_version"] not in policy_versions:
                errors.append(f"{run_id}: alert_policy_version missing from alert policy registry")
            for field in ("false_alerts", "missed_violations", "confidence_config"):
                if is_missing(row.get(field)):
                    errors.append(f"{run_id}: calibration run missing {field}")

    for row in policies:
        version = row["policy_version"]
        if row["detector_model_version"] not in model_versions:
            errors.append(f"{version}: detector_model_version missing from model registry")
        check_file_reference(root, row["threshold_config"], errors, version)

    for cfg in (tracking / "configs").glob("*.yaml"):
        if cfg.stat().st_size == 0:
            errors.append(f"{cfg}: empty config file")

    print("Registry validation")
    print(f"- experiments: {len(experiments)}")
    print(f"- model versions: {len(models)}")
    print(f"- alert policies: {len(policies)}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print("Result:", "PASS" if not errors else "FAIL")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    sys.exit(validate(Path(args.root).resolve()))


if __name__ == "__main__":
    main()
