from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ultralytics import YOLO


HAZARD_CLASS_IDS = {
    7: "chemical hazard",
    8: "fire",
    9: "no helmet",
    10: "smoke",
    11: "water leak",
}
HAZARD_CLASSES = set(HAZARD_CLASS_IDS.values())
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
FIELDNAMES = ["clip", "frame_index", "timestamp_sec", "class", "confidence", "x1", "y1", "x2", "y2"]


def image_label_ids(label_path: Path) -> set[int]:
    if not label_path.exists():
        return set()
    ids = set()
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts:
            ids.add(int(float(parts[0])))
    return ids


def iter_labeled_images(dataset: Path):
    for split in ("val", "test", "train"):
        image_dir = dataset / "images" / split
        label_dir = dataset / "labels" / split
        if not image_dir.exists() or not label_dir.exists():
            continue
        for image_path in sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
            yield image_path, label_dir / f"{image_path.stem}.txt"


def predict_image(model: YOLO, image_path: Path, conf: float) -> list[dict]:
    result = model.predict(source=str(image_path), conf=conf, verbose=False)[0]
    detections = []
    if result.boxes is None:
        return detections
    for box, confidence, class_id in zip(
        result.boxes.xyxy.cpu().tolist(),
        result.boxes.conf.cpu().tolist(),
        result.boxes.cls.cpu().tolist(),
    ):
        class_id = int(class_id)
        detections.append(
            {
                "class": result.names.get(class_id, str(class_id)),
                "confidence": float(confidence),
                "x1": float(box[0]),
                "y1": float(box[1]),
                "x2": float(box[2]),
                "y2": float(box[3]),
            }
        )
    return detections


def rows_for_frame(clip: str, frame_index: int, detections: list[dict], fps: float) -> list[dict]:
    timestamp = frame_index / fps
    if not detections:
        return [
            {
                "clip": clip,
                "frame_index": frame_index,
                "timestamp_sec": f"{timestamp:.3f}",
                "class": "",
                "confidence": "",
                "x1": "",
                "y1": "",
                "x2": "",
                "y2": "",
            }
        ]
    return [
        {
            "clip": clip,
            "frame_index": frame_index,
            "timestamp_sec": f"{timestamp:.3f}",
            "class": det["class"],
            "confidence": f"{det['confidence']:.6f}",
            "x1": f"{det['x1']:.2f}",
            "y1": f"{det['y1']:.2f}",
            "x2": f"{det['x2']:.2f}",
            "y2": f"{det['y2']:.2f}",
        }
        for det in detections
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a temporal frame-replay benchmark from real labeled images.")
    parser.add_argument("--model", default="Backend/best.pt")
    parser.add_argument("--dataset", default="Hazard_Expansion/content_runtime/combined_dataset")
    parser.add_argument("--detections-output", default="Confidence_Calibration/outputs/frame_replay_detections.csv")
    parser.add_argument("--annotations-output", default="Confidence_Calibration/benchmark/annotations/frame_replay_annotations.json")
    parser.add_argument("--clips-per-class", type=int, default=2)
    parser.add_argument("--frames-per-clip", type=int, default=5)
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--max-scan", type=int, default=2000)
    args = parser.parse_args()

    dataset = Path(args.dataset)
    model = YOLO(args.model)
    positives: dict[str, list[tuple[Path, list[dict]]]] = {name: [] for name in HAZARD_CLASSES}
    clean_negative: tuple[Path, list[dict]] | None = None
    hazard_false_positive: tuple[Path, list[dict]] | None = None

    scanned = 0
    for image_path, label_path in iter_labeled_images(dataset):
        if scanned >= args.max_scan:
            break
        scanned += 1
        label_ids = image_label_ids(label_path)
        labels = {HAZARD_CLASS_IDS[i] for i in label_ids if i in HAZARD_CLASS_IDS}
        detections = predict_image(model, image_path, args.conf)
        detected_hazards = [d for d in detections if d["class"] in HAZARD_CLASSES]

        for class_name in labels:
            if len(positives[class_name]) < args.clips_per_class and any(d["class"] == class_name for d in detected_hazards):
                positives[class_name].append((image_path, detections))

        if not labels:
            if clean_negative is None and not detected_hazards:
                clean_negative = (image_path, detections)
            if hazard_false_positive is None and detected_hazards:
                hazard_false_positive = (image_path, detections)

        if all(len(v) >= args.clips_per_class for v in positives.values()) and clean_negative and hazard_false_positive:
            break

    missing = [name for name, items in positives.items() if len(items) < args.clips_per_class]
    if missing:
        raise RuntimeError(f"Could not find enough detected positives for: {', '.join(missing)}")
    if clean_negative is None:
        raise RuntimeError("Could not find a clean non-hazard negative image.")
    if hazard_false_positive is None:
        raise RuntimeError("Could not find a non-hazard image with a hazard false positive.")

    rows = []
    clips = []
    for class_name in sorted(HAZARD_CLASSES):
        for idx, (image_path, detections) in enumerate(positives[class_name], start=1):
            clip = f"{class_name.replace(' ', '_')}_{idx:02d}_frame_replay"
            for frame_index in range(args.frames_per_clip):
                rows.extend(rows_for_frame(clip, frame_index, detections, args.fps))
            clips.append(
                {
                    "clip": clip,
                    "duration_sec": args.frames_per_clip / args.fps,
                    "source_url": "local combined_dataset extracted from project Drive",
                    "license": "project dataset license; see Drive/source dataset documentation",
                    "attribution": str(image_path),
                    "events": [{"class": class_name, "start_sec": 0.0, "end_sec": args.frames_per_clip / args.fps}],
                }
            )

    negative_clip = "negative_hazard_false_positive_spike_frame_replay"
    clean_image, clean_detections = clean_negative
    fp_image, fp_detections = hazard_false_positive
    spike_frame = args.frames_per_clip // 2
    for frame_index in range(args.frames_per_clip):
        detections = fp_detections if frame_index == spike_frame else clean_detections
        rows.extend(rows_for_frame(negative_clip, frame_index, detections, args.fps))
    clips.append(
        {
            "clip": negative_clip,
            "duration_sec": args.frames_per_clip / args.fps,
            "source_url": "local combined_dataset extracted from project Drive",
            "license": "project dataset license; see Drive/source dataset documentation",
            "attribution": f"clean={clean_image}; false_positive={fp_image}",
            "events": [],
        }
    )

    detections_output = Path(args.detections_output)
    detections_output.parent.mkdir(parents=True, exist_ok=True)
    with detections_output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    annotations_output = Path(args.annotations_output)
    annotations_output.parent.mkdir(parents=True, exist_ok=True)
    annotations_output.write_text(json.dumps({"clips": clips}, indent=2), encoding="utf-8")
    print(f"scanned={scanned} clips={len(clips)} rows={len(rows)}")


if __name__ == "__main__":
    main()
