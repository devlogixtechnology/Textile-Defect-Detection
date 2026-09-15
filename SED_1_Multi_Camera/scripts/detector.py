from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any


class SharedYOLODetector:
    """Single YOLO model instance shared by the inference scheduler."""

    def __init__(self, weights: str | Path, device: str | None = None, imgsz: int = 640):
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ultralytics is required for YOLO inference.") from exc
        self.weights = str(weights)
        self.device = device
        self.imgsz = imgsz
        self.model = YOLO(self.weights)

    def predict_batch(self, frames: list[Any]) -> tuple[list[list[dict[str, Any]]], float]:
        started = perf_counter()
        kwargs: dict[str, Any] = {"source": frames, "verbose": False, "imgsz": self.imgsz}
        if self.device:
            kwargs["device"] = self.device
        results = self.model.predict(**kwargs)
        elapsed = perf_counter() - started
        return [self._convert_result(res) for res in results], elapsed

    @staticmethod
    def _convert_result(res: Any) -> list[dict[str, Any]]:
        detections: list[dict[str, Any]] = []
        if getattr(res, "boxes", None) is None:
            return detections
        for box, confidence, class_id in zip(
            res.boxes.xyxy.cpu().tolist(),
            res.boxes.conf.cpu().tolist(),
            res.boxes.cls.cpu().tolist(),
        ):
            class_id = int(class_id)
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": res.names.get(class_id, str(class_id)),
                    "confidence": float(confidence),
                    "coordinates": {
                        "x1": float(box[0]),
                        "y1": float(box[1]),
                        "x2": float(box[2]),
                        "y2": float(box[3]),
                    },
                }
            )
        return detections


class NullDetector:
    """Deterministic detector for architecture tests; not valid for SED-1 DoD."""

    def predict_batch(self, frames: list[Any]) -> tuple[list[list[dict[str, Any]]], float]:
        return [[] for _ in frames], 0.0


