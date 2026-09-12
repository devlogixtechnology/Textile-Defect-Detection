from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - config loading reports this clearly
    yaml = None


DEFAULT_SAFETY_CLASSES = {
    "chemical hazard",
    "fire",
    "no helmet",
    "smoke",
    "water leak",
}


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list: str | None = None
    current_class: str | None = None
    in_classes = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if stripped.startswith("- ") and current_list:
            data.setdefault(current_list, []).append(stripped[2:].strip())
            continue

        if indent == 0:
            current_class = None
            in_classes = False
            if stripped.endswith(":"):
                key = stripped[:-1]
                data[key] = [] if key == "alert_classes" else {}
                current_list = key if key == "alert_classes" else None
                in_classes = key == "classes"
                continue
            key, value = stripped.split(":", 1)
            data[key] = _parse_scalar(value)
            current_list = None
            continue

        if "classes" in data and indent == 2 and stripped.endswith(":"):
            current_class = stripped[:-1]
            data.setdefault("classes", {})[current_class] = {}
            in_classes = True
            continue

        if in_classes and current_class and indent == 4:
            key, value = stripped.split(":", 1)
            data["classes"][current_class][key] = _parse_scalar(value)

    return data


def normalize_class_name(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


@dataclass(frozen=True)
class AlertClassConfig:
    confidence: float
    window_size: int = 5
    required_frames: int = 3
    cooldown_frames: int = 10
    clear_frames: int = 5
    track_iou: float = 0.1


@dataclass
class AlertPolicyConfig:
    default_confidence: float = 0.25
    process_fps: float = 5.0
    alert_classes: set[str] = field(default_factory=lambda: set(DEFAULT_SAFETY_CLASSES))
    classes: dict[str, AlertClassConfig] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AlertPolicyConfig":
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) if yaml is not None else _load_simple_yaml(path)
        raw = raw or {}
        class_cfgs = {}
        for name, cfg in (raw.get("classes") or {}).items():
            class_cfgs[normalize_class_name(name)] = AlertClassConfig(**cfg)
        return cls(
            default_confidence=float(raw.get("default_confidence", 0.25)),
            process_fps=float(raw.get("process_fps", 5.0)),
            alert_classes={normalize_class_name(c) for c in raw.get("alert_classes", DEFAULT_SAFETY_CLASSES)},
            classes=class_cfgs,
        )

    def for_class(self, class_name: str) -> AlertClassConfig:
        class_name = normalize_class_name(class_name)
        return self.classes.get(class_name, AlertClassConfig(confidence=self.default_confidence))


def load_policy_config(path: str | Path | None) -> AlertPolicyConfig:
    if path is None:
        return AlertPolicyConfig()
    path = Path(path)
    if not path.exists():
        return AlertPolicyConfig()
    return AlertPolicyConfig.from_yaml(path)


def detection_box(det: dict[str, Any]) -> tuple[float, float, float, float] | None:
    coords = det.get("coordinates") or det.get("box") or det.get("bbox")
    if coords is None:
        return None
    if isinstance(coords, dict):
        return (
            float(coords["x1"]),
            float(coords["y1"]),
            float(coords["x2"]),
            float(coords["y2"]),
        )
    return tuple(float(v) for v in coords[:4])


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


class ConfidenceCalibrator:
    def __init__(self, config: AlertPolicyConfig):
        self.config = config

    def filter(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        calibrated = []
        for det in detections:
            class_name = normalize_class_name(str(det.get("class_name", det.get("class", ""))))
            threshold = self.config.for_class(class_name).confidence
            if float(det.get("confidence", 0.0)) >= threshold:
                out = dict(det)
                out["class_name"] = class_name
                out["threshold"] = threshold
                calibrated.append(out)
        return calibrated


class AlertManager:
    """Sliding-window temporal confirmation with per-class state and cooldown."""

    def __init__(self, config: AlertPolicyConfig):
        self.config = config
        self.histories: dict[str, deque[bool]] = {}
        self.active: dict[str, bool] = defaultdict(bool)
        self.cooldown_remaining: dict[str, int] = defaultdict(int)
        self.clear_counts: dict[str, int] = defaultdict(int)

    def update(self, detections: list[dict[str, Any]], frame_index: int, timestamp_sec: float | None = None) -> list[dict[str, Any]]:
        classes_seen = {normalize_class_name(str(d.get("class_name", d.get("class", "")))) for d in detections}
        alert_classes = self.config.alert_classes | set(self.config.classes)
        alerts = []

        for class_name in sorted(alert_classes):
            cfg = self.config.for_class(class_name)
            history = self.histories.setdefault(class_name, deque(maxlen=cfg.window_size))
            history.append(class_name in classes_seen)
            confirmed = sum(history) >= cfg.required_frames

            if confirmed:
                self.clear_counts[class_name] = 0
                if not self.active[class_name] and self.cooldown_remaining[class_name] <= 0:
                    self.active[class_name] = True
                    self.cooldown_remaining[class_name] = cfg.cooldown_frames
                    alerts.append(
                        {
                            "class_name": class_name,
                            "state": "confirmed",
                            "frame_index": frame_index,
                            "timestamp_sec": timestamp_sec,
                            "window_size": cfg.window_size,
                            "required_frames": cfg.required_frames,
                            "confidence_threshold": cfg.confidence,
                        }
                    )
            else:
                self.clear_counts[class_name] += 1
                if self.clear_counts[class_name] >= cfg.clear_frames:
                    self.active[class_name] = False

            if self.cooldown_remaining[class_name] > 0:
                self.cooldown_remaining[class_name] -= 1

        return alerts


class AlertPolicy:
    def __init__(self, config: AlertPolicyConfig):
        self.calibrator = ConfidenceCalibrator(config)
        self.manager = AlertManager(config)

    def process_frame(self, detections: list[dict[str, Any]], frame_index: int, timestamp_sec: float | None = None) -> dict[str, Any]:
        calibrated = self.calibrator.filter(detections)
        alerts = self.manager.update(calibrated, frame_index=frame_index, timestamp_sec=timestamp_sec)
        return {"calibrated_detections": calibrated, "alerts": alerts}
