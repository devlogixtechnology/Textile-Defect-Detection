from __future__ import annotations

from typing import Any

from .models import CameraConfig, GeofenceConfig


def normalize_class_name(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


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


def box_center(det: dict[str, Any]) -> tuple[float, float] | None:
    box = detection_box(det)
    if box is None:
        return None
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y)
        if intersects:
            x_at_y = (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
            if x < x_at_y:
                inside = not inside
        j = i
    return inside


def _frame_shape(frame: Any) -> tuple[int, int] | None:
    shape = getattr(frame, "shape", None)
    if shape is not None and len(shape) >= 2:
        return int(shape[1]), int(shape[0])
    if isinstance(frame, dict) and "width" in frame and "height" in frame:
        return int(frame["width"]), int(frame["height"])
    return None


def _normalised_center(center: tuple[float, float], frame: Any) -> tuple[float, float]:
    shape = _frame_shape(frame)
    if shape is None:
        return center
    width, height = shape
    x, y = center
    if x > 1.0 or y > 1.0:
        return (x / max(1, width), y / max(1, height))
    return center


def detection_in_geofence(det: dict[str, Any], geofence: GeofenceConfig, frame: Any = None) -> bool:
    if not geofence.enabled:
        return False
    class_name = normalize_class_name(str(det.get("class_name", det.get("class", ""))))
    if geofence.classes and class_name not in geofence.classes:
        return False
    center = box_center(det)
    if center is None:
        return False
    return point_in_polygon(_normalised_center(center, frame), geofence.polygon)


def filter_detections_for_camera(
    detections: list[dict[str, Any]], camera: CameraConfig, frame: Any = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return detections that match this camera's class/geofence policy.

    A detection is inside a geofence when the bounding-box center falls inside the
    configured polygon. Geofence polygons use normalized coordinates by default.
    """

    accepted: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for det in detections:
        class_name = normalize_class_name(str(det.get("class_name", det.get("class", ""))))
        if camera.monitored_classes and class_name not in camera.monitored_classes:
            continue
        if not camera.geofences:
            out = dict(det)
            out["class_name"] = class_name
            accepted.append(out)
            continue
        for geofence in camera.geofences:
            if detection_in_geofence(det, geofence, frame):
                out = dict(det)
                out["class_name"] = class_name
                out["geofence_id"] = geofence.id
                accepted.append(out)
                matches.append({"class_name": class_name, "geofence_id": geofence.id})
                break
    return accepted, matches


