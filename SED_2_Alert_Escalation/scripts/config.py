from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from .models import ActionRule, HazardRule, Severity


DEFAULT_HAZARD_CLASSES = {
    "fire",
    "smoke",
    "water leak",
    "chemical hazard",
    "no helmet",
}


def normalize_class_name(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


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


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        return _load_yaml_subset(text)


def _load_yaml_subset(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, data)]
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            raise RuntimeError("SED-2 fallback YAML parser does not support list items in configs.")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_value(value)
    return data


def load_severity_rules(path: str | Path) -> dict[str, HazardRule]:
    raw = _load_yaml_or_json(Path(path))
    hazards = raw.get("hazards") or {}
    rules: dict[str, HazardRule] = {}
    errors: list[str] = []
    for hazard, cfg in hazards.items():
        hazard_name = normalize_class_name(hazard)
        if hazard_name not in DEFAULT_HAZARD_CLASSES:
            errors.append(f"unknown hazard class: {hazard}")
            continue
        try:
            initial = Severity.from_value(str(cfg["initial_severity"]))
        except Exception as exc:
            errors.append(f"{hazard}: invalid initial_severity: {exc}")
            continue
        escalation = cfg.get("escalation") or {}
        warning_after = escalation.get("warning_after_seconds")
        critical_after = escalation.get("critical_after_seconds")
        clear_after = float(escalation.get("clear_after_seconds", raw.get("default_clear_after_seconds", 5.0)))
        for name, value in (
            ("warning_after_seconds", warning_after),
            ("critical_after_seconds", critical_after),
            ("clear_after_seconds", clear_after),
        ):
            if value is not None and float(value) < 0:
                errors.append(f"{hazard}: {name} must be non-negative")
        if warning_after is not None and critical_after is not None and float(critical_after) < float(warning_after):
            errors.append(f"{hazard}: critical_after_seconds cannot be lower than warning_after_seconds")
        overrides = {}
        for geofence_id, severity in (cfg.get("geofence_overrides") or {}).items():
            try:
                overrides[str(geofence_id)] = Severity.from_value(str(severity))
            except ValueError as exc:
                errors.append(f"{hazard}: invalid geofence override {geofence_id}: {exc}")
        rules[hazard_name] = HazardRule(
            hazard_class=hazard_name,
            initial_severity=initial,
            warning_after_seconds=float(warning_after) if warning_after is not None else None,
            critical_after_seconds=float(critical_after) if critical_after is not None else None,
            clear_after_seconds=clear_after,
            geofence_overrides=overrides,
            category=str(cfg.get("category", "safety")),
        )
    missing = DEFAULT_HAZARD_CLASSES - set(rules)
    if missing:
        errors.append(f"missing hazard rules: {', '.join(sorted(missing))}")
    if errors:
        raise ValueError("Invalid SED-2 severity config: " + "; ".join(errors))
    return rules


def load_action_mapping(path: str | Path) -> dict[Severity, ActionRule]:
    raw = _load_yaml_or_json(Path(path))
    actions = raw.get("actions") or {}
    mapping: dict[Severity, ActionRule] = {}
    errors: list[str] = []
    for severity_name, cfg in actions.items():
        try:
            severity = Severity.from_value(str(severity_name))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        mapping[severity] = ActionRule(
            log=bool(cfg.get("log", False)),
            dashboard_flash=bool(cfg.get("dashboard_flash", False)),
            dashboard_critical=bool(cfg.get("dashboard_critical", False)),
            mock_iot_shutdown=bool(cfg.get("mock_iot_shutdown", False)),
        )
    for severity in Severity:
        if severity not in mapping:
            errors.append(f"missing action mapping for {severity.value}")
    if errors:
        raise ValueError("Invalid SED-2 action config: " + "; ".join(errors))
    return mapping

