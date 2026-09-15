# SED-3 Benchmark Report

## Executive Summary

The integrated 3-camera pipeline completed an actual 30-minute sustained run on
the available local CPU environment.

| Question | Result |
| --- | --- |
| Completed full run? | Yes, `1804.22 s` measured |
| Streams | 3 concurrent simulated cameras |
| Aggregate FPS | `0.352` |
| P95 inference latency | `4151.81 ms` |
| P95 end-to-end latency | `13683.47 ms` |
| Unexpected frame drop | `96.607%` |
| RAM leak evidence | No evidence detected |
| GPU memory stability | Not measured because CUDA/GPU unavailable |
| Crashes / unrecoverable errors | None recorded |
| SED-3 result | PASS for CPU sustained stability; GPU/T4 benchmark still required for GPU claims |

The results do **not** support a literal zero-latency claim. On this CPU-only
machine, the system is stable but not low-latency for 3-stream YOLO inference.

## System Under Test

```text
Concurrent camera streams
  -> SED-1 capture workers and bounded queues
  -> shared CME-1 YOLO detector
  -> CME-2 confidence calibration and temporal confirmation
  -> SED-1 geofence filtering
  -> SED-2 severity engine and action dispatcher
```

- Detector: `cme1-expanded-12class-v1`
- Weights: `Backend/best.pt`
- CME-2 policy: `cme2-alert-calibrated-v1`
- SED-1 version: `SED1-multicam-v1`
- SED-2 version: `SED2-alert-escalation-v1`
- SED-3 version: `SED3-stress-v1`

## Hardware / Software Environment

| Field | Value |
| --- | --- |
| Platform | Windows-11-10.0.26200-SP0 |
| CPU | Intel64 Family 6 Model 142 Stepping 9, GenuineIntel |
| GPU | not available |
| Python | 3.14.3 |
| PyTorch | 2.10.0+cpu |
| CUDA | unavailable |
| Ultralytics | 8.4.24 |

## Benchmark Configuration

| Setting | Value |
| --- | --- |
| Duration | 1800 seconds configured, 1804.22 seconds measured |
| Streams | 3 |
| Device | CPU |
| Image size | 640 |
| Queue size | 2 |
| Micro-batching | enabled |
| Warm-up marking | first 60 seconds |
| Resource sample interval | 5 seconds |
| Sources | SED-1 camera config videos, looped |

## FPS Results

| Camera | Mean FPS | Frames Processed | Eligible Frames | Unexpected Drops | Drop % |
| --- | ---: | ---: | ---: | ---: | ---: |
| camera_01 | 0.117 | 211 | 8581 | 8370 | 97.541 |
| camera_02 | 0.118 | 212 | 8317 | 8105 | 97.451 |
| camera_03 | 0.118 | 212 | 1816 | 1604 | 88.326 |
| aggregate | 0.352 | 635 | 18714 | 18079 | 96.607 |

## Latency Results

| Metric | Inference Latency | End-to-End Latency |
| --- | ---: | ---: |
| Mean | 2840.16 ms | 9216.96 ms |
| P50 | 2998.53 ms | 9642.94 ms |
| P95 | 4151.81 ms | 13683.47 ms |
| P99 | 4925.97 ms | 15337.52 ms |
| Min | 425.56 ms | 2416.04 ms |
| Max | 7814.61 ms | 18094.72 ms |

## Resource Results

| Resource | Start | Mean | Peak | End |
| --- | ---: | ---: | ---: | ---: |
| Process RAM | 358.95 MB | 1002.27 MB | 1057.74 MB | 514.46 MB |
| CPU utilization | n/a | 99.72% | 100.00% | n/a |
| Process CPU utilization | n/a | 315.23% | 364.00% | n/a |
| GPU utilization | unavailable | unavailable | unavailable | unavailable |
| GPU memory | unavailable | unavailable | unavailable | unavailable |

## Stability Analysis

| Check | Result |
| --- | --- |
| Completed normally | Yes |
| Unhandled exceptions | 0 |
| Worker crashes | 0 |
| CUDA OOM | No CUDA runtime present |
| Thread count | start 8, peak 38, end 9 |
| Queue depth | mean 5.87, peak 6.0 |
| RAM growth | no leak detected; slope `1.219 MB/min` |
| GPU memory growth | not applicable; GPU telemetry unavailable |

Queue depth remained near the configured maximum because CPU inference could not
keep up with the configured 3-stream input load. The bounded queue policy
prevented unbounded queue growth, but at the cost of high overload drop rate.

## 5-Minute Window Comparison

| Window | FPS | Mean Latency | P95 Latency | RAM | GPU Memory |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-5 min | 0.280 | 10378.41 ms | 13449.88 ms | 964.34 MB | n/a |
| 5-10 min | 0.282 | 11099.91 ms | 13349.65 ms | 992.08 MB | n/a |
| 10-15 min | 0.271 | 11601.02 ms | 14964.56 ms | 997.89 MB | n/a |
| 15-20 min | 0.326 | 11993.62 ms | 14964.56 ms | 1009.81 MB | n/a |
| 20-25 min | 0.475 | 10724.69 ms | 14964.56 ms | 1016.33 MB | n/a |
| 25-30 min | 0.450 | 8765.37 ms | 14712.35 ms | 1030.18 MB | n/a |

## Memory-Leak Analysis

The automatic RAM trend check found:

```text
slope=1.219 MB/min, final-window growth=26.493 MB, span=543.277 MB
```

This was below the configured leak threshold and the process ended at
`514.46 MB`, below the stable-run peak. The conclusion is:

```text
No evidence of uncontrolled RAM leak during this 30-minute run.
```

GPU memory leak analysis was not possible in this CPU-only environment.

## Latency Claim Evaluation

The measured local CPU run does not justify saying the integrated 3-stream
pipeline is literally zero-latency, nor does it demonstrate low latency on this
hardware.

Evidence:

- Mean inference latency: `2840.16 ms`
- P95 inference latency: `4151.81 ms`
- Mean end-to-end latency: `9216.96 ms`
- P95 end-to-end latency: `13683.47 ms`

Pitch-safe wording from this run:

```text
The pipeline completed a 30-minute integrated stress test without crashes or
uncontrolled memory growth on CPU, but low-latency 3-stream inference requires
GPU/edge-accelerated hardware validation.
```

## Definition Of Done

```text
30-minute continuous run completed: PASS
3 concurrent streams sustained: PASS
FPS documented: PASS
Inference latency documented: PASS
End-to-end latency documented: PASS
P50/P95/P99 latency documented: PASS
CPU monitored: PASS
RAM monitored: PASS
GPU utilization monitored: N/A - GPU unavailable
GPU memory monitored: N/A - GPU unavailable
Frame drop documented: PASS
No unrecoverable crashes: PASS
No CUDA OOM: PASS - CUDA unavailable
No evidence of RAM leak: PASS
No evidence of GPU memory leak: N/A - GPU unavailable
No worker/task leak: PASS
No unbounded queue growth: PASS - bounded at queue capacity
Clean shutdown verified: PASS
Benchmark report generated: PASS
SED-3 OVERALL: PASS for local CPU sustained stability; GPU/T4 performance claim pending
```

