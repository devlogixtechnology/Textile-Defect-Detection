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
