# SED-3 Stress Testing & Latency Benchmarking

SED-3 provides sustained-load benchmarking for the integrated vision pipeline:

```text
SED-1 multi-camera streams
  -> shared CME-1 detector
  -> CME-2 confirmation
  -> SED-1 geofence routing
  -> SED-2 severity escalation
```

The benchmark intentionally excludes Streamlit browser rendering from the core
pipeline measurements.

## Configuration

```text
SED_3_Stress_Testing/configs/stress_test.yaml
```

Default sustained run:

- `streams`: 3
- `duration_seconds`: 1800
- `warmup_seconds`: 60
- `sample_interval`: 1 second in config, 5 seconds in the committed local run
- `imgsz`: 640
- `queue_size`: 2

## Run A Smoke Test

```powershell
python SED_3_Stress_Testing/scripts/run_stress_test.py --streams 3 --duration-seconds 60 --warmup-seconds 5 --device cpu --output-dir SED_3_Stress_Testing/reports/smoke_yolo
```

## Run The 30-Minute Test

```powershell
python SED_3_Stress_Testing/scripts/run_stress_test.py --streams 3 --duration-seconds 1800 --warmup-seconds 60 --sample-interval 5 --device cpu --output-dir SED_3_Stress_Testing/reports
```

For a CUDA/T4 run, use `--device 0` on the GPU runtime.

## Outputs

```text
SED_3_Stress_Testing/reports/
  stress_test_timeseries.csv
  stress_test_summary.json
  latency_summary.csv
  resource_summary.csv
  fps_over_time.png
  latency_over_time.png
  ram_over_time.png
  SED_3_Benchmark_Report.md
```

## Metric Definitions

- Inference latency: time spent inside the model inference batch call.
- End-to-end latency: time from eligible frame capture/submission to result completion.
- Unexpected frame drop: SED-1 overload queue drops divided by eligible frames.
- Memory leak evidence: resource trend analysis over stable samples, not a simple start/end comparison.

