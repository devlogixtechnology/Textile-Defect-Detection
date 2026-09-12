# CME-2: Confidence Calibration and False-Positive Reduction

This module adds an alert policy layer around the existing expanded 12-class
YOLO model. It does not retrain the model. The backend still returns raw
detections by default, and the new temporal alert policy is opt-in through the
`apply_alert_policy=true` query parameter.

## What Changed

- Baseline config reproduces the existing alert behavior: immediate alert on a
  single YOLO detection using the default/global confidence threshold.
- Calibrated config adds per-class confidence thresholds and `3 of 5` temporal
  confirmation for the five hazard classes.
- Benchmark tooling can extract YOLO detections from videos, preserve empty
  frames, compare baseline vs calibrated alert policy, and sweep thresholds or
  temporal windows.
- FastAPI integration keeps inference and alert policy separate.

Current policy scope: scene-level per-class confirmation. It confirms that a
hazard class persists across frames; it does not yet assign stable object IDs.

## Files

```text
Confidence_Calibration/
|-- configs/
|   |-- baseline.yaml
|   `-- calibrated_thresholds.yaml
|-- scripts/
|   |-- alert_policy.py
|   |-- benchmark_alerts.py
|   |-- benchmark_loader.py
|   |-- compare_metrics.py
|   |-- extract_detections.py
|   |-- make_frame_replay_benchmark.py
|   |-- temporal_sweep.py
|   `-- threshold_sweep.py
|-- benchmark/
|   |-- README.md
|   |-- clip_manifest.csv
|   |-- source_manifest.csv
|   `-- annotations/example_annotations.json
|-- reports/
`-- tests/
```

## Backend Usage

Raw detection behavior remains unchanged:

```text
POST /predict
```

Opt-in calibrated alert response:

```text
POST /predict?apply_alert_policy=true&frame_index=42&timestamp_sec=8.4
```

The response includes the original `detections` plus:

```json
{
  "alert_policy": {
    "calibrated_detections": [],
    "alerts": []
  }
}
```

## Benchmark Status

Temporal benchmark clips/frame replays were downloaded/generated locally and
evaluated. The frame-replay temporal benchmark passes the CME-2 DoD.

Current measured results are summarized in `reports/benchmark_report.md`.

Frame-replay DoD result:

- false-alert events: `4 -> 1`
- false-alert reduction: `75%`
- calibrated missed true violations: `0`
- result: `PASS`

The public Wikimedia video audit remains documented separately because it
exposes model domain shift rather than alert-policy failure.

To extend the benchmark, place additional legitimate labeled videos in
`Confidence_Calibration/benchmark/media/`, update the annotations, then run the
commands in `benchmark/README.md`.

Commit benchmark results only after they are produced from real clips. Required
evidence:

- baseline false alert events
- calibrated false alert events
- percent false-alert reduction
- missed true violations
- precision, recall, false-alert rate per minute, mean latency, and per-class
  metrics

## Source Notes

The project Drive remains the primary artifact store:

https://drive.google.com/drive/u/0/folders/1f9qfY8KkIFtAXe1REnx_I-fhNaUEdgkU

Candidate public sources are listed in `benchmark/source_manifest.csv`. Verify
license and attribution at download time, especially for video sources that
require registration or separate terms.
