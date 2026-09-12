# Confidence Calibration Benchmark Report

Benchmark date: 2026-09-12

Model under test: `Backend/best.pt` expanded 12-class YOLO checkpoint.

## Alert Policies

Baseline:

- YOLO default/global confidence behavior represented as `0.25`
- immediate alert from a single detection
- no temporal confirmation

Calibrated:

- per-class confidence thresholds from `configs/calibrated_thresholds.yaml`
- `3 of 5` frame temporal confirmation
- scene-level per-class alert state

## Public Wikimedia Video Audit

Input clips:

- 10 downloaded public Wikimedia Commons clips
- 2 clips per hazard class
- media stored locally under `Confidence_Calibration/benchmark/media/`
- clip source/license/attribution tracked in `benchmark/clip_manifest.csv`

Results:

| Metric | Baseline | Calibrated |
|---|---:|---:|
| True events | 10 | 10 |
| True events detected | 1 | 1 |
| Missed events | 9 | 9 |
| False alert events | 30 | 6 |
| False-alert rate/min | 3.146 | 0.629 |
| Precision | 0.032 | 0.143 |
| Recall | 0.100 | 0.100 |

DoD summary:

- false-alert reduction: `80%`
- calibrated missed true violations: `9`
- result: `FAIL`

Reason: the deployed model rarely detects the public clips as the correct hazard
classes. This is a model/domain-shift limitation, not an alert-policy tuning
issue. Confidence calibration cannot recover events that are not detected by the
base model.

## Frame-Replay Temporal Benchmark

Input:

- real labeled images from the local 12-class combined dataset
- real YOLO detections from `Backend/best.pt`
- synthetic temporal ordering that replays each image as a short clip
- one non-hazard false-positive spike frame from the combined dataset

This benchmark isolates the alert-policy requirement: sustained true hazards
must alert, while a one-frame false positive should not become an alert.

Results:

| Metric | Baseline | Calibrated |
|---|---:|---:|
| True events | 10 | 10 |
| True events detected | 10 | 10 |
| Missed events | 0 | 0 |
| False alert events | 4 | 1 |
| False-alert rate/min | 4.364 | 1.091 |
| Precision | 0.714 | 0.909 |
| Recall | 1.000 | 1.000 |

DoD summary:

- false-alert reduction: `75%`
- calibrated missed true violations: `0`
- result: `PASS`

Per-class calibrated result:

| Class | True Events | Detected | Missed | False Alerts | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| chemical hazard | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| fire | 2 | 2 | 0 | 1 | 0.667 | 1.000 |
| no helmet | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| smoke | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| water leak | 2 | 2 | 0 | 0 | 1.000 | 1.000 |

## Conclusion

The implementation is ready and tested. CME-2 passes on the frame-replay
temporal benchmark and fails on the public Wikimedia video audit because the
base model does not detect most domain-shifted public videos.

Observed value:

- frame replay: DoD pass with 75% false-alert reduction and 0 missed true events
- public clips: large false-alert reduction, but unacceptable missed events

Recommended next evidence:

- more realistic CCTV/industrial video clips from the same visual domain as the
  hazard training data
- at least some negative clips that trigger baseline hazard false alerts
- calibrated policy must reduce those false alert events by at least `30%` while
  keeping missed true violations at `0`
