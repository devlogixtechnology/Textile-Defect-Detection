# CME-2 Temporal Benchmark

This folder defines the benchmark format for confidence calibration and
false-positive reduction. Large videos are intentionally not stored in Git.

## Required Local Layout

```text
Confidence_Calibration/
|-- benchmark/
|   |-- media/                 # ignored; put local benchmark videos here
|   |-- annotations/
|   |   `-- annotations.json   # committed only after labels are real
|   |-- clip_manifest.csv
|   `-- source_manifest.csv
`-- outputs/                   # ignored; generated detections/results
```

If command-line network access is available, download the selected Wikimedia
Commons clips with:

```powershell
python Confidence_Calibration/scripts/download_commons_clips.py
```

After download, visually verify every clip before using it as benchmark truth.
Some candidates are domain-shifted or only contain the target class during part
of the video, so `annotations.json` must be created from observed intervals.

## Annotation Format

Use one event row for each real hazard interval. Negative clips can be included
with an empty `events` list; they are important for measuring false alerts.

```json
{
  "clips": [
    {
      "clip": "clip_001.mp4",
      "duration_sec": 18.2,
      "source_url": "https://example.com/original-source",
      "license": "Example license",
      "attribution": "Required credit text",
      "events": [
        {
          "class": "fire",
          "start_sec": 4.0,
          "end_sec": 9.5
        }
      ]
    }
  ]
}
```

## Run Order

### Public Video Audit

```powershell
python Confidence_Calibration/scripts/extract_detections.py `
  --model Backend/best.pt `
  --input Confidence_Calibration/benchmark/media `
  --sample-fps 5 `
  --output Confidence_Calibration/outputs/detections.csv

python Confidence_Calibration/scripts/benchmark_alerts.py `
  --detections Confidence_Calibration/outputs/detections.csv `
  --annotations Confidence_Calibration/benchmark/annotations/annotations.json `
  --config Confidence_Calibration/configs/baseline.yaml `
  --output Confidence_Calibration/reports/baseline_metrics.csv `
  --per-class-output Confidence_Calibration/reports/baseline_per_class.csv

python Confidence_Calibration/scripts/benchmark_alerts.py `
  --detections Confidence_Calibration/outputs/detections.csv `
  --annotations Confidence_Calibration/benchmark/annotations/annotations.json `
  --config Confidence_Calibration/configs/calibrated_thresholds.yaml `
  --output Confidence_Calibration/reports/calibrated_metrics.csv `
  --per-class-output Confidence_Calibration/reports/calibrated_per_class.csv

python Confidence_Calibration/scripts/compare_metrics.py `
  --baseline Confidence_Calibration/reports/baseline_metrics.csv `
  --calibrated Confidence_Calibration/reports/calibrated_metrics.csv `
  --output Confidence_Calibration/reports/dod_summary.csv
```

### Frame-Replay DoD Benchmark

```powershell
python Confidence_Calibration/scripts/make_frame_replay_benchmark.py `
  --model Backend/best.pt `
  --dataset Hazard_Expansion/content_runtime/combined_dataset `
  --detections-output Confidence_Calibration/outputs/frame_replay_detections.csv `
  --annotations-output Confidence_Calibration/benchmark/annotations/frame_replay_annotations.json `
  --clips-per-class 2 `
  --frames-per-clip 5 `
  --fps 1 `
  --conf 0.25

python Confidence_Calibration/scripts/benchmark_alerts.py `
  --detections Confidence_Calibration/outputs/frame_replay_detections.csv `
  --annotations Confidence_Calibration/benchmark/annotations/frame_replay_annotations.json `
  --config Confidence_Calibration/configs/baseline.yaml `
  --output Confidence_Calibration/reports/frame_replay_baseline_metrics.csv `
  --per-class-output Confidence_Calibration/reports/frame_replay_baseline_per_class.csv

python Confidence_Calibration/scripts/benchmark_alerts.py `
  --detections Confidence_Calibration/outputs/frame_replay_detections.csv `
  --annotations Confidence_Calibration/benchmark/annotations/frame_replay_annotations.json `
  --config Confidence_Calibration/configs/calibrated_thresholds.yaml `
  --output Confidence_Calibration/reports/frame_replay_calibrated_metrics.csv `
  --per-class-output Confidence_Calibration/reports/frame_replay_calibrated_per_class.csv

python Confidence_Calibration/scripts/compare_metrics.py `
  --baseline Confidence_Calibration/reports/frame_replay_baseline_metrics.csv `
  --calibrated Confidence_Calibration/reports/frame_replay_calibrated_metrics.csv `
  --output Confidence_Calibration/reports/frame_replay_dod_summary.csv
```

## DoD Rule

The CME-2 Definition of Done is only satisfied when the same labeled clips show:

- false alert events reduced by at least `30%`
- missed true violations equal `0`

Do not mark CME-2 as passing until those numbers are produced from real clips.
