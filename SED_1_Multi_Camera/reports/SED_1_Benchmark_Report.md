# SED-1 Benchmark Report

## Configuration

- Architecture: `SED1-multicam-v1`
- Detector: `cme1-expanded-12class-v1`
- Weights: `Backend/best.pt`
- Alert policy: `cme2-alert-calibrated-v1`
- Configured camera sampling: `5 FPS`
- Queue size: `2`
- Micro-batching: enabled, one latest frame per active camera
- Frame-drop metric: `overload_drops / eligible_frames * 100`

Configured sampling skips are tracked separately and are not counted as overload
drops.

## Local Benchmark Environment

- Python: `3.14.3`
- Platform: `Windows-11-10.0.26200-SP0`
- CPU: `Intel64 Family 6 Model 142 Stepping 9, GenuineIntel`
- PyTorch: `2.10.0+cpu`
- Ultralytics: `8.4.24`
- CUDA: unavailable
- GPU: unavailable

This local machine is CPU-only, so it is not equivalent to the historical Colab
T4 environment. The local runs below are real YOLO/OpenCV measurements, but they
do **not** satisfy the SED-1 performance Definition of Done.

## Local CPU Results

| Streams | Aggregate FPS | Avg FPS/Camera | Avg Latency (ms) | P95 Latency (ms) | Drop % |
| ------: | ------------: | -------------: | ---------------: | ---------------: | -----: |
| 1 | 1.998 | 1.998 | 816.695 | 992.248 | 60.000 |
| 2 | 0.896 | 0.448 | 3143.613 | 5336.168 | 90.722 |
| 3 | 0.954 | 0.318 | 5196.519 | 7186.886 | 90.385 |
| 4 | 0.964 | 0.241 | 4174.107 | 10248.810 | 93.197 |

## Mandatory 3-Stream Local CPU Run

- Duration: `10.49 s` measured after `1 s` warm-up
- Eligible frames: `104`
- Processed frames: `10`
- Unexpected drops: `94`
- Overall unexpected drop rate: `90.385%`
- Aggregate FPS: `0.954`
- Average FPS/camera: `0.318`

Per-camera results:

| Camera | Processed FPS | Eligible | Processed | Unexpected Drops | Drop % |
| ------ | ------------: | -------: | --------: | ----------------: | -----: |
| camera_01 | 0.397 | 48 | 4 | 44 | 91.667 |
| camera_02 | 0.298 | 46 | 3 | 43 | 93.478 |
| camera_03 | 0.286 | 10 | 3 | 7 | 70.000 |

## Final GPU/T4 Benchmark Command

Run this on the target CUDA/T4 environment from the repository root:

```powershell
python -m pip install -r requirements.txt
python SED_1_Multi_Camera/scripts/benchmark_multistream.py --streams 1 --duration-seconds 60 --warmup-seconds 5 --device 0
python SED_1_Multi_Camera/scripts/benchmark_multistream.py --streams 2 --duration-seconds 60 --warmup-seconds 5 --device 0
python SED_1_Multi_Camera/scripts/benchmark_multistream.py --streams 3 --duration-seconds 60 --warmup-seconds 5 --device 0
python SED_1_Multi_Camera/scripts/benchmark_multistream.py --streams 4 --duration-seconds 60 --warmup-seconds 5 --device 0
```

Only the resulting GPU/T4 `benchmark_3_streams.json` should be used to mark the
performance DoD as passed.

## Definition of Done

```text
3 concurrent streams processed: PASS (architecture and local execution)
Near-real-time processing demonstrated: FAIL on local CPU
Per-camera geofences implemented: PASS
Unexpected frame drop <5%: FAIL on local CPU
Camera state isolation verified: PASS
SED-1 OVERALL: FAIL pending GPU/T4 benchmark
```
