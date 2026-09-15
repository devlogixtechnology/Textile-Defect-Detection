from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class CameraSource(Protocol):
    source_fps: float

    def open(self) -> None:
        ...

    def read(self) -> tuple[bool, Any]:
        ...

    def close(self) -> None:
        ...


class FileCameraSource:
    def __init__(self, source: str, loop: bool = True):
        self.source = source
        self.loop = loop
        self.capture: Any = None
        self.source_fps = 0.0

    def open(self) -> None:
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("opencv-python is required for file camera sources.") from exc
        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"Camera source does not exist: {path}")
        self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open camera source: {path}")
        fps = float(self.capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self.source_fps = fps if fps > 0 else 30.0

    def read(self) -> tuple[bool, Any]:
        if self.capture is None:
            raise RuntimeError("Camera source has not been opened.")
        ok, frame = self.capture.read()
        if ok:
            return True, frame
        if not self.loop:
            return False, None
        self.capture.set(1, 0)
        return self.capture.read()

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None


@dataclass
class SyntheticCameraSource:
    width: int = 640
    height: int = 360
    source_fps: float = 30.0
    max_frames: int | None = None
    fail_after: int | None = None

    def __post_init__(self) -> None:
        self._frame = 0

    def open(self) -> None:
        self._frame = 0

    def read(self) -> tuple[bool, dict[str, int]]:
        if self.fail_after is not None and self._frame >= self.fail_after:
            return False, {}
        if self.max_frames is not None and self._frame >= self.max_frames:
            return False, {}
        self._frame += 1
        time.sleep(1.0 / max(1.0, self.source_fps))
        return True, {"width": self.width, "height": self.height, "synthetic_frame_id": self._frame}

    def close(self) -> None:
        pass


