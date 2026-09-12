# Sprint 4 Experiment Summary

Sprint 4 consists of:

- CME-1: Hazard Expansion
- CME-2: Confidence Calibration & False-Positive Reduction
- CME-3: Model Versioning & Experiment Tracking

## Sprint Narrative

CME-1 expanded the original 7-class textile defect detector into a 12-class
industrial safety and quality inspection model. It introduced five safety
classes while preserving the textile defect classes.

CME-2 added an alert-policy layer on top of the CME-1 detector. It did not train
a new model. It tuned confidence thresholds and temporal confirmation to reduce
false alerts while keeping true violations detectable.

CME-3 creates the persistent registry for the above work. It separates detector
model versions from alert-policy versions and records metrics, datasets,
weights, and missing metadata transparently.

## Dataset Registry

| Dataset | Version | Classes | Train | Val | Test | Total |
|---|---|---:|---:|---:|---:|---:|
| Textile defect dataset | `textile_defect_yolov8_final` | 7 | 3900 | 562 | 280 | 4742 |
| Combined textile + hazard dataset | `combined_dataset.zip` | 12 | 4974 | 777 | 334 | 6085 |

Combined dataset class order is read from
`Hazard_Expansion/content_runtime/combined_dataset/data.yaml`.

## Model Comparison

| Run | Sprint | Task | Classes | Purpose | Precision | Recall | mAP@50 | mAP@50-95 | Weights | Status |
|---|---|---:|---:|---|---:|---:|---:|---:|---|---|
| Original baseline | Pre-Sprint-4 | Baseline | 7 | Reference textile detector | 0.7697 | 0.7476 | 0.7882 | 0.4712 | Drive `Training_Results/yolov8s_textile_initial/best.pt` | archived |
| Improved textile | Sprint 4 | CME-1 | 7 | Improve weaker textile classes | 0.8415 | 0.7824 | 0.8476 | 0.5408 | `Hazard_Expansion/content_runtime/improved_model_results/best.pt` | superseded |
| Expanded model | Sprint 4 | CME-1 | 12 | Quality + hazards detector | 0.8127 | 0.7053 | 0.7656 | 0.4407 | `Backend/best.pt` and Drive `Training_Results/Expanded_12-class_model/best.pt` | pitch candidate |

## CME-1 Runs

| Run ID | Stage | Epochs | Batch | Image Size | Optimizer | LR | Patience | Metrics |
|---|---|---:|---|---:|---|---:|---:|---|
| `CME1-EXP-001` | Improved Textile Training | 50 | -1 auto-batch | 640 | SGD | 0.01 | 10 | recorded |
| `CME1-EXP-002` | Hazard Expansion Phase 1 | 20 | -1 auto-batch | 640 | SGD | 0.005 | 20 | not recorded |
| `CME1-EXP-003` | Hazard Expansion Phase 2 Final | 60 | -1 auto-batch | 640 | SGD | 0.01 | 15 | recorded |

## CME-2 Calibration Comparison

| Policy | Detector | False Alerts | Missed Violations | FP Reduction | Mean Latency | Status |
|---|---|---:|---:|---:|---:|---|
| `cme2-alert-baseline-v1` | `cme1-expanded-12class-v1` | 4 | 0 | 0% | 0.0s | reference |
| `cme2-alert-calibrated-v1` | `cme1-expanded-12class-v1` | 1 | 0 | 75% | 2.0s | pitch candidate |

The CME-2 passing benchmark is the frame-replay temporal benchmark in
`Confidence_Calibration/reports/frame_replay_dod_summary.csv`.

The public Wikimedia video audit is retained as a domain-shift check. It reduced
false alerts but missed too many true events because the base detector did not
detect most public clips as the correct hazard class.

## Pitch Candidate

Detector:

- Version: `cme1-expanded-12class-v1`
- Classes: 12
- Weights: `Backend/best.pt`
- External weight location: Drive `Training_Results/Expanded_12-class_model/best.pt`
- Source: `Hazard_Expansion/03_train_expanded_model.ipynb`

Alert policy:

- Version: `cme2-alert-calibrated-v1`
- Config: `Confidence_Calibration/configs/calibrated_thresholds.yaml`
- Temporal confirmation: `3 of 5` frames
- Cooldown: 10 frames
- Clear policy: 5 absent frames
- Frame-replay DoD: PASS

## Missing Metadata

- Baseline optimizer, learning rate, weight decay, patience, and seed are not
  recorded in the available committed artifacts.
- Improved model weight decay and seed are not recorded.
- Expanded phase-1 validation metrics and phase-1 local checkpoint are not
  currently available.
- Expanded phase-2 weight decay and seed are not recorded.
- Last checkpoints were path-recorded in notebooks but are not verified locally.
- Public Drive links are recorded at folder level; direct per-file Drive URLs
  were not invented.

## Final Validation Checklist

| Requirement | Result | Notes |
|---|---|---|
| All CME-1 Sprint 4 model runs logged | PASS | Improved textile, expanded phase 1, expanded phase 2 final |
| All meaningful CME-2 Sprint 4 calibration runs logged | PASS | Baseline, public audit, final frame-replay policy |
| CME-1 hyperparameters logged | PASS | Available notebook evidence recorded; missing values marked |
| CME-1 mAP metrics logged | PASS | Recorded where evidence exists; phase 1 marked not recorded |
| CME-1 exported weights linked | PASS | Local/Drive/path-recorded references classified |
| CME-2 detector relationships recorded | PASS | Policies reference `cme1-expanded-12class-v1` |
| CME-2 calibration configurations logged | PASS | Baseline and calibrated YAML tracked |
| CME-2 benchmark metrics logged | PASS | CSV reports tracked |
| Persistent tracking implemented | PASS | Git registries + Drive artifact strategy |
| Model versioning implemented | PASS | `model_registry.csv` |
| Alert-policy versioning implemented | PASS | `alert_policy_registry.csv` |
| Pitch candidate identified | PASS | Detector + alert policy documented |

CME-3 Definition of Done: PASS
