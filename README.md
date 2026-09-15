# Textile Defect Detection and Industrial Hazard Expansion

Computer vision proof of concept for textile defect detection and industrial
safety monitoring, developed for Devlogix Technology.

The project started as a 7-class textile defect detector and was expanded into a
12-class model by adding five industrial hazard classes.

## Classes

Textile defect classes:

- `baekra`
- `color issues`
- `contamination`
- `cut`
- `gray stitch`
- `selvet`
- `stain`

Industrial hazard classes:

- `chemical hazard`
- `fire`
- `no helmet`
- `smoke`
- `water leak`

## Repository Structure

```text
Textile-Defect-Detection/
|-- Backend/
|   |-- fastapi_endpoint.ipynb
|   `-- main.py
|-- Frontend/
|   |-- app.py
|   |-- README.md
|   `-- requirements.txt
|-- Confidence_Calibration/
|   |-- configs/
|   |-- scripts/
|   |-- benchmark/
|   |-- reports/
|   `-- tests/
|-- Experiment_Tracking/
|   |-- configs/
|   |-- reports/
|   |-- scripts/
|   |-- experiments.csv
|   |-- model_registry.csv
|   `-- alert_policy_registry.csv
|-- SED_1_Multi_Camera/
|   |-- configs/
|   |-- reports/
|   |-- scripts/
|   `-- tests/
|-- SED_2_Alert_Escalation/
|   |-- configs/
|   |-- reports/
|   |-- scripts/
|   `-- tests/
|-- SED_3_Stress_Testing/
|   |-- configs/
|   |-- reports/
|   |-- scripts/
|   `-- tests/
|-- Hazard_Expansion/
|   |-- 01_prepare_combined_dataset.ipynb
|   |-- 02_improve_existing_model.ipynb
|   |-- 03_train_expanded_model.ipynb
|   |-- 04_evaluate_and_compare.ipynb
|   `-- content_runtime/              # ignored local/Colab runtime artifacts
|-- Preprocessing/
|   |-- notebooks/
|   |-- reports/
|   `-- scripts/
|-- Training/
|   `-- Textile_Defect_Detection_Training.ipynb
|-- requirements.txt
|-- .gitignore
`-- LICENSE.txt
```

Large datasets, model checkpoints, runtime outputs, images, and training result
artifacts are not stored in GitHub. They are kept in Google Drive.

## Google Drive Artifacts

Main Drive folder:

https://drive.google.com/drive/u/0/folders/1f9qfY8KkIFtAXe1REnx_I-fhNaUEdgkU

Drive contents:

```text
Drive root folder/
|-- textile_defect_yolov8_final.zip       # local folder name: final_dataset
|-- combined_dataset.zip                  # 12-class combined dataset
`-- Training_Results/
    |-- yolov8s_textile_initial/          # baseline 7-class training outputs
    |-- yolov8s_improved_7class/          # improved 7-class checkpoint/results
    |-- Expanded_12-class_model/          # expanded 12-class checkpoint/results
    `-- hazard_reports/                   # final report, matrices, examples
```

Important local runtime folders used during development:

- `final_dataset/`: extracted 7-class textile dataset, ignored by Git.
- `Hazard_Expansion/content_runtime/combined_dataset/`: extracted 12-class
  combined dataset, ignored by Git.
- `Hazard_Expansion/content_runtime/improved_model_results/`: local copy of the
  improved 7-class `best.pt` and `results.json`, ignored by Git.
- `Hazard_Expansion/content_runtime/expanded_model_results/`: local copy of the
  expanded 12-class results, ignored by Git.
- `Backend/best.pt`: deployed expanded 12-class checkpoint, ignored by Git.

## Main Workflows

### 1. Preprocessing

The original textile preprocessing workflow lives in:

```text
Preprocessing/notebooks/dataset_preprocessing.ipynb
```

Standalone helpers:

```powershell
python Preprocessing/scripts/validate_yolo_dataset.py --dataset final_dataset/
python Preprocessing/scripts/dataset_statistics.py --dataset final_dataset/ --output Preprocessing/reports/
```

### 2. Baseline Training

The original YOLOv8s 7-class baseline training workflow lives in:

```text
Training/Textile_Defect_Detection_Training.ipynb
```

Baseline metrics:

| Metric | Value |
|---|---:|
| Precision | 76.97% |
| Recall | 74.76% |
| mAP@50 | 78.82% |
| mAP@50-95 | 47.12% |

### 3. Hazard Expansion

The hazard expansion workflow is directly under `Hazard_Expansion/`:

```text
01_prepare_combined_dataset.ipynb
02_improve_existing_model.ipynb
03_train_expanded_model.ipynb
04_evaluate_and_compare.ipynb
```

Notebook 4 performs the final comparison across:

- Experiment A: historical 7-class baseline
- Experiment B: improved 7-class model
- Experiment C: expanded 12-class model

The final Definition of Done rule is:

- at least `2/5` hazard classes must reach `>= 70%` mAP@50
- at least `1/3` of the remaining hazard classes must reach `>= 60%` mAP@50

Current expanded-model DoD result: `PASS`.

Passing classes:

- `no helmet`: 89.4% AP@50
- `water leak`: 70.5% AP@50
- `fire`: 62.1% AP@50 support pass

Primary weak classes:

- `chemical hazard`: 49.1% AP@50
- `smoke`: 57.3% AP@50

### 4. Confidence Calibration and False-Positive Reduction

CME-2 lives in:

```text
Confidence_Calibration/
```

It adds an alert-policy layer around the expanded 12-class model without
retraining. The baseline config represents the existing behavior: a single YOLO
detection is enough to alert. The calibrated config adds per-class thresholds
and temporal confirmation for the hazard classes.

Benchmark status: measured. The frame-replay temporal benchmark passes the
CME-2 DoD with `75%` false-alert reduction and `0` missed true violations.
Public Wikimedia clips were also audited and documented separately; they expose
base-model domain shift rather than alert-policy failure.

The benchmark media folder is ignored by Git:

```text
Confidence_Calibration/benchmark/media/
```

The detailed benchmark report is in:

```text
Confidence_Calibration/reports/benchmark_report.md
```

### 5. Model Versioning and Experiment Tracking

CME-3 lives in:

```text
Experiment_Tracking/
```

Sprint 4 tracking uses lightweight persistent registries in Git, with large
weights and datasets kept in Google Drive. MLflow is optional for local UI
inspection; the committed CSV/YAML files are the source of truth.

Tracked registries:

- `Experiment_Tracking/experiments.csv`
- `Experiment_Tracking/model_registry.csv`
- `Experiment_Tracking/alert_policy_registry.csv`

Current pitch candidate:

- Detector: `cme1-expanded-12class-v1`
- Weights: `Backend/best.pt` locally and Drive
  `Training_Results/Expanded_12-class_model/best.pt`
- Alert policy: `cme2-alert-calibrated-v1`
- Config: `Confidence_Calibration/configs/calibrated_thresholds.yaml`

Open optional MLflow UI after installing the focused tracking dependency:

```powershell
python -m pip install -r Experiment_Tracking/requirements-mlflow.txt
python Experiment_Tracking/scripts/backfill_existing_runs.py
mlflow ui --backend-store-uri Experiment_Tracking/mlruns
```

Validate the registry:

```powershell
python Experiment_Tracking/scripts/validate_registry.py
```

Sprint 4 summary:

```text
Experiment_Tracking/reports/Sprint_4_Experiment_Summary.md
```

## Backend

The backend is a FastAPI app in `Backend/main.py`. It loads `Backend/best.pt`,
which should be the expanded 12-class checkpoint.

Run locally:

```powershell
python -m uvicorn Backend.main:api_app --host 127.0.0.1 --port 8000
```

Prediction endpoint:

```text
POST /predict
```

The endpoint accepts an uploaded image and returns detected class names,
confidence scores, and pixel bounding boxes.

Optional CME-2 alert policy:

```text
POST /predict?apply_alert_policy=true&frame_index=0&timestamp_sec=0.0
```

This preserves raw detections and adds an `alert_policy` object with calibrated
detections and confirmed temporal alerts.

## Frontend

The frontend is a Streamlit dashboard in `Frontend/app.py`.

Run locally after starting the backend:

```powershell
streamlit run Frontend/app.py
```

The dashboard uploads images to the FastAPI backend and displays detections on
the image. It does not run YOLO inference locally.

## 6. Multi-Camera Stream Architecture

SED-1 lives in:

```text
SED_1_Multi_Camera/
```

It refactors inference into a reusable multi-camera pipeline:

```text
Capture workers -> bounded latest-frame queues -> fair scheduler
-> shared YOLO detector -> per-camera geofence filter
-> per-camera CME-2 AlertPolicy -> camera-specific alerts/results
```

Key properties:

- supports 1-4 simulated camera feeds from video files
- uses one shared `cme1-expanded-12class-v1` detector by default
- preserves independent CME-2 temporal state per camera
- supports normalized polygon geofences per camera
- tracks captured, eligible, submitted, processed, configured skipped, overload
  dropped, and failed frames separately
- exposes optional FastAPI demo endpoints for camera status/results/alerts
- adds a Streamlit multi-camera status tab without replacing image inference

Configuration:

```text
SED_1_Multi_Camera/configs/cameras.yaml
SED_1_Multi_Camera/configs/benchmark.yaml
```

Benchmark:

```powershell
python SED_1_Multi_Camera/scripts/benchmark_multistream.py --streams 3 --duration-seconds 60 --warmup-seconds 5 --device 0
```

Local CPU benchmark evidence is stored in:

```text
SED_1_Multi_Camera/reports/
```

The local CPU-only environment (`torch 2.10.0+cpu`, CUDA unavailable) validates
that the architecture runs but does **not** satisfy the SED-1 performance DoD.
The measured 3-stream CPU run processed `10/104` eligible frames with `90.385%`
unexpected drops. Run the same benchmark on the target CUDA/T4 environment
before marking the `<5%` frame-drop performance requirement as passed.

## 7. Real-Time Alert Escalation

SED-2 lives in:

```text
SED_2_Alert_Escalation/
```

It adds a severity-tiered response layer after CME-2 confirmation and SED-1
multi-camera routing:

```text
Confirmed violation -> SeverityEngine -> EscalationManager -> ActionDispatcher
```

Severity tiers:

- `INFO`: structured log only
- `WARNING`: structured log plus dashboard warning/flash state
- `CRITICAL`: structured log, critical dashboard state, and safe mock IoT
  shutdown simulation

Configuration:

```text
SED_2_Alert_Escalation/configs/severity_rules.yaml
SED_2_Alert_Escalation/configs/action_mapping.yaml
```

Policy version:

```text
SED2-alert-escalation-v1
```

The default safety rules cover:

- `fire`
- `smoke`
- `water leak`
- `chemical hazard`
- `no helmet`

The state machine is monotonic during one active event (`INFO -> WARNING ->
CRITICAL`) and resolves only after the configured clear period. Geofence
overrides are supported, and multi-camera events remain isolated by camera,
hazard, and geofence. The mock IoT relay is software-only and never controls
physical hardware.

Validate SED-2:

```powershell
python -m unittest discover -s SED_2_Alert_Escalation\tests
```

Current deterministic validation result: `15` tests passed. The detailed report
is in:

```text
SED_2_Alert_Escalation/reports/SED_2_Validation_Report.md
```

## 8. Stress Testing & Latency Benchmarking

SED-3 lives in:

```text
SED_3_Stress_Testing/
```

It benchmarks the current integrated pipeline:

```text
SED-1 streams -> CME-1 detector -> CME-2 confirmation
-> SED-1 geofences -> SED-2 escalation
```

The committed local run is a real 3-stream, 30-minute CPU stress test:

| Metric | Result |
| --- | ---: |
| Duration | 1804.22 s |
| Streams | 3 |
| Device | CPU |
| Frames processed | 635 |
| Aggregate FPS | 0.352 |
| P95 inference latency | 4151.81 ms |
| P95 end-to-end latency | 13683.47 ms |
| Unexpected frame drop | 96.607% |
| RAM peak | 1057.74 MB |
| Crashes | 0 |
| RAM leak evidence | none detected |

This CPU-only run validates sustained stability and clean shutdown, but it does
not support a literal zero-latency claim or a low-latency 3-stream performance
claim on this hardware. GPU/T4 validation should be run separately with:

```powershell
python SED_3_Stress_Testing/scripts/run_stress_test.py --streams 3 --duration-seconds 1800 --warmup-seconds 60 --sample-interval 5 --device 0 --output-dir SED_3_Stress_Testing/reports
```

Report:

```text
SED_3_Stress_Testing/reports/SED_3_Benchmark_Report.md
```

## Notes for GitHub

The following are intentionally ignored and should remain in Drive/local storage:

- datasets and dataset zips
- `content_runtime/`
- `hazard_reports/`
- images
- `*.pt` checkpoints
- generated JSON runtime outputs
- YOLO `runs/`
- `Experiment_Tracking/mlruns/`

## Contact

GitHub username: `ehtisham5618`

Email: `ehtisham.malik5618@gmail.com`
