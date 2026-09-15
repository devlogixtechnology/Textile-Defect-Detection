from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


ARCHITECTURE_VERSION = "SED1-multicam-v1"


@dataclass(frozen=True)
class GeofenceConfig:
    id: str
    polygon: list[tuple[float, float]]
    classes: set[str]
    enabled: bool = True
    alert_behavior: str | None = None


@dataclass(frozen=True)
class CameraConfig:
    camera_id: str
    name: str
    source: str
    enabled: bool = True
    loop: bool = True
    sampling_fps: float | None = None
    monitored_classes: set[str] = field(default_factory=set)
    geofences: list[GeofenceConfig] = field(default_factory=list)


@dataclass(frozen=True)
class FramePacket:
    camera_id: str
    frame_id: int
    timestamp: float
    frame: Any
    source_fps: float
    capture_time: float = field(default_factory=perf_counter)


@dataclass
class DetectionResult:
    camera_id: str
    frame_id: int
    timestamp: float
    detections: list[dict[str, Any]]
    calibrated_detections: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    escalations: list[dict[str, Any]] = field(default_factory=list)
    geofence_matches: list[dict[str, Any]] = field(default_factory=list)
    inference_time: float = 0.0
    processing_time: float = 0.0
    end_to_end_latency: float = 0.0


@dataclass
class CameraMetrics:
    captured: int = 0
    eligible: int = 0
    submitted: int = 0
    processed: int = 0
    configured_skips: int = 0
    overload_drops: int = 0
    decode_failures: int = 0
    queue_depth_samples: list[int] = field(default_factory=list)
    inference_times: list[float] = field(default_factory=list)
    processing_times: list[float] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)
    started_at: float | None = None
    ended_at: float | None = None
    status: str = "stopped"
    last_error: str | None = None

    @property
    def unexpected_drop_rate(self) -> float:
        if self.eligible <= 0:
            return 0.0
        return (self.overload_drops / self.eligible) * 100.0

    @property
    def processed_fps(self) -> float:
        if self.started_at is None or self.ended_at is None:
            return 0.0
        elapsed = max(0.000001, self.ended_at - self.started_at)
        return self.processed / elapsed


@dataclass
class StreamStatus:
    camera_id: str
    name: str
    enabled: bool
    status: str
    captured: int
    eligible: int
    processed: int
    overload_drops: int
    drop_rate_pct: float
    processed_fps: float
    queue_depth: int
    last_error: str | None = None


