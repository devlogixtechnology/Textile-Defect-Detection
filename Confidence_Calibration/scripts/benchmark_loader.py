from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TemporalEvent:
    clip: str
    class_name: str
    start_sec: float
    end_sec: float


@dataclass(frozen=True)
class ClipMetadata:
    clip: str
    duration_sec: float | None = None
    source_url: str | None = None
    license: str | None = None
    attribution: str | None = None


def load_clip_metadata(path: str | Path) -> list[ClipMetadata]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [
            ClipMetadata(
                clip=clip["clip"],
                duration_sec=float(clip["duration_sec"]) if clip.get("duration_sec") is not None else None,
                source_url=clip.get("source_url"),
                license=clip.get("license"),
                attribution=clip.get("attribution"),
            )
            for clip in raw.get("clips", [])
        ]

    seen: dict[str, ClipMetadata] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            clip = row["clip"]
            if clip not in seen:
                duration = row.get("duration_sec")
                seen[clip] = ClipMetadata(
                    clip=clip,
                    duration_sec=float(duration) if duration else None,
                    source_url=row.get("source_url") or None,
                    license=row.get("license") or None,
                    attribution=row.get("attribution") or None,
                )
    return list(seen.values())


def load_annotations(path: str | Path) -> list[TemporalEvent]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        events = []
        for clip in raw.get("clips", []):
            for event in clip.get("events", []):
                events.append(
                    TemporalEvent(
                        clip=clip["clip"],
                        class_name=event["class"],
                        start_sec=float(event["start_sec"]),
                        end_sec=float(event["end_sec"]),
                    )
                )
        return events

    with path.open("r", encoding="utf-8", newline="") as f:
        return [
            TemporalEvent(
                clip=row["clip"],
                class_name=row["class"],
                start_sec=float(row["start_sec"]),
                end_sec=float(row["end_sec"]),
            )
            for row in csv.DictReader(f)
            if row.get("label", "1") != "0"
        ]
