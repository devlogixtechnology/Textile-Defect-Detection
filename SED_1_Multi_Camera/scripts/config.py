from __future__ import annotations

import json
import ast
from pathlib import Path
from typing import Any

from .models import CameraConfig, GeofenceConfig


def _normalise_class(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        return _load_sed1_yaml_subset(text)
    return yaml.safe_load(text) or {}


def _parse_value(value: str) -> Any:
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip('"').strip("'")


def _load_sed1_yaml_subset(text: str) -> dict[str, Any]:
    """Small fallback parser for the committed SED-1 config files.

    It intentionally supports only the structure used by configs/cameras.yaml
    and configs/benchmark.yaml; normal environments should use PyYAML.
    """

    data: dict[str, Any] = {}
    current_camera: dict[str, Any] | None = None
    current_geofence: dict[str, Any] | None = None
    current_list: list[Any] | None = None
    in_benchmark = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            current_camera = None
            current_geofence = None
            current_list = None
            in_benchmark = stripped == "benchmark:"
            if stripped == "cameras:":
                data["cameras"] = {}
            elif in_benchmark:
                data["benchmark"] = {}
            elif ":" in stripped:
                key, value = stripped.split(":", 1)
                data[key] = _parse_value(value)
            continue

        if in_benchmark and indent == 2 and ":" in stripped:
            key, value = stripped.split(":", 1)
            data.setdefault("benchmark", {})[key] = _parse_value(value)
            continue

        if indent == 2 and stripped.endswith(":"):
            camera_id = stripped[:-1]
            current_camera = {}
            data.setdefault("cameras", {})[camera_id] = current_camera
            current_geofence = None
            current_list = None
            continue

        if current_camera is None:
            continue

        if indent == 4 and stripped.endswith(":"):
            key = stripped[:-1]
            current_camera[key] = []
            current_list = current_camera[key]
            continue

        if indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_camera[key] = _parse_value(value)
            current_list = None
            continue

        if indent == 6 and stripped.startswith("- ") and isinstance(current_list, list):
            item = stripped[2:]
            if item.startswith("id:"):
                current_geofence = {"id": _parse_value(item.split(":", 1)[1])}
                current_list.append(current_geofence)
            else:
                current_list.append(_parse_value(item))
            continue

        if current_geofence is None:
            continue

        if indent == 8 and stripped.endswith(":"):
            key = stripped[:-1]
            current_geofence[key] = []
            current_list = current_geofence[key]
            continue

        if indent == 8 and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_geofence[key] = _parse_value(value)
            continue

        if indent == 10 and stripped.startswith("- ") and isinstance(current_list, list):
            current_list.append(_parse_value(stripped[2:]))

    return data


def load_camera_configs(path: str | Path, limit: int | None = None) -> list[CameraConfig]:
    path = Path(path)
    raw = _load_yaml_or_json(path)
    project_root = path.resolve().parents[2]
    cameras = raw.get("cameras") or {}
    configs: list[CameraConfig] = []
    for camera_id, cfg in cameras.items():
        geofences = []
        for geofence in cfg.get("geofences", []) or []:
            geofences.append(
                GeofenceConfig(
                    id=str(geofence["id"]),
                    polygon=[(float(x), float(y)) for x, y in geofence.get("polygon", [])],
                    classes={_normalise_class(c) for c in geofence.get("classes", [])},
                    enabled=bool(geofence.get("enabled", True)),
                    alert_behavior=geofence.get("alert_behavior"),
                )
            )
        source = Path(str(cfg.get("source", "")))
        resolved_source = source if source.is_absolute() else project_root / source
        configs.append(
            CameraConfig(
                camera_id=str(camera_id),
                name=str(cfg.get("name", camera_id)),
                source=str(resolved_source),
                enabled=bool(cfg.get("enabled", True)),
                loop=bool(cfg.get("loop", True)),
                sampling_fps=cfg.get("sampling_fps"),
                monitored_classes={_normalise_class(c) for c in cfg.get("monitored_classes", [])},
                geofences=geofences,
            )
        )
    enabled = [camera for camera in configs if camera.enabled]
    return enabled[:limit] if limit else enabled


def load_benchmark_config(path: str | Path) -> dict[str, Any]:
    return _load_yaml_or_json(Path(path))

