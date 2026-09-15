# Model Versioning and Experiment Tracking

This folder is the persistent experiment registry for the Vision-Driven
Industrial Safety & Quality Inspection Engine. It began with Sprint 4 model and
calibration tracking and now also records SED-1, SED-2, and SED-3 validation
evidence.

## Tracking Backend

Primary backend: lightweight CSV/YAML registry committed to Git.

Reason: most training happened in Colab or on another laptop, while large
weights and datasets live in Google Drive. Committing registry metadata keeps
the experiment history persistent without committing `mlruns/`, datasets,
videos, or model checkpoints.

Optional backend: local MLflow export.

MLflow is not required to inspect the committed registry. It can be installed
only when a team member wants the MLflow UI:

```powershell
python -m pip install -r Experiment_Tracking/requirements-mlflow.txt
python Experiment_Tracking/scripts/backfill_existing_runs.py
mlflow ui --backend-store-uri Experiment_Tracking/mlruns
```

Then open:

```text
http://127.0.0.1:5000
```

The local `Experiment_Tracking/mlruns/` directory is ignored by Git.

## Registries

- `experiments.csv`: evidence-backed model, calibration, multi-camera,
  escalation, and stress-test runs plus the pre-Sprint baseline reference.
- `model_registry.csv`: deployable or meaningful detector model versions.
- `alert_policy_registry.csv`: CME-2 alert-policy versions separated from model
  versions.
- `configs/`: compact configuration snapshots for reproducibility.
- `reports/Sprint_4_Experiment_Summary.md`: pitch-friendly summary.

## Versioning Convention

Detector versions:

- `baseline-textile-v1`: pre-Sprint-4 7-class textile baseline
- `cme1-textile-improved-v1`: Sprint 4 improved 7-class textile model
- `cme1-expanded-12class-phase1`: Sprint 4 intermediate frozen-transfer run
- `cme1-expanded-12class-v1`: Sprint 4 final 12-class detector

Alert-policy versions:

- `cme2-alert-baseline-v1`: immediate detection-as-alert behavior
- `cme2-alert-calibrated-v1`: calibrated threshold + temporal confirmation

SED stack versions:

- `SED1-multicam-v1`: multi-camera stream architecture
- `SED2-alert-escalation-v1`: severity-tiered escalation policy
- `SED3-stress-v1`: stress-test configuration/run version

Pitch candidate:

- Detector: `cme1-expanded-12class-v1`
- Weights: `Backend/best.pt` locally and Drive
  `Training_Results/Expanded_12-class_model/best.pt`
- Alert policy: `cme2-alert-calibrated-v1`
- Threshold config: `Confidence_Calibration/configs/calibrated_thresholds.yaml`

## Persistence Strategy

GitHub stores:

- experiment metadata
- registries
- config snapshots
- lightweight CSV reports
- summary documentation

Google Drive stores:

- datasets
- model checkpoints
- training outputs
- large/generated media

Main Drive folder:

```text
https://drive.google.com/drive/u/0/folders/1f9qfY8KkIFtAXe1REnx_I-fhNaUEdgkU
```

## Validation

Run:

```powershell
python Experiment_Tracking/scripts/validate_registry.py
```

Expected result:

```text
Result: PASS
```

Warnings are allowed for historical metadata that was not preserved, such as
the phase-1 expanded-model mAP values. Missing data is recorded explicitly as
`not recorded` rather than guessed.

## Optional JSON Export

```powershell
python Experiment_Tracking/scripts/export_registry.py
```

Generated JSON exports are ignored by Git by default.
