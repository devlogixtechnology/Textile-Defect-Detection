from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def csv_to_json(csv_path: Path, json_path: Path) -> None:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export registry CSV files to JSON for presentation tooling.")
    parser.add_argument("--tracking-dir", default="Experiment_Tracking")
    args = parser.parse_args()
    tracking = Path(args.tracking_dir)
    out_dir = tracking / "exports"
    for name in ("experiments", "model_registry", "alert_policy_registry"):
        csv_to_json(tracking / f"{name}.csv", out_dir / f"{name}.json")
        print(f"wrote {out_dir / f'{name}.json'}")


if __name__ == "__main__":
    main()
