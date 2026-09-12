from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
from ultralytics import YOLO


FIELDNAMES = [
    "clip",
    "frame_index",
    "timestamp_sec",
    "class",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
]


def iter_video_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    suffixes = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    return sorted(p for p in input_path.rglob("*") if p.suffix.lower() in suffixes)


def extract_video(model: YOLO, video_path: Path, sample_fps: float) -> list[dict]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or sample_fps
    stride = max(1, round(native_fps / sample_fps))
    rows = []
    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % stride != 0:
                frame_index += 1
                continue

            timestamp_sec = frame_index / native_fps
            result = model.predict(source=frame, verbose=False)[0]
            wrote_detection = False
            if result.boxes is not None:
                for box, confidence, class_id in zip(
                    result.boxes.xyxy.cpu().tolist(),
                    result.boxes.conf.cpu().tolist(),
                    result.boxes.cls.cpu().tolist(),
                ):
                    class_id = int(class_id)
                    rows.append(
                        {
                            "clip": video_path.name,
                            "frame_index": frame_index,
                            "timestamp_sec": f"{timestamp_sec:.3f}",
                            "class": result.names.get(class_id, str(class_id)),
                            "confidence": f"{float(confidence):.6f}",
                            "x1": f"{float(box[0]):.2f}",
                            "y1": f"{float(box[1]):.2f}",
                            "x2": f"{float(box[2]):.2f}",
                            "y2": f"{float(box[3]):.2f}",
                        }
                    )
                    wrote_detection = True
            if not wrote_detection:
                rows.append(
                    {
                        "clip": video_path.name,
                        "frame_index": frame_index,
                        "timestamp_sec": f"{timestamp_sec:.3f}",
                        "class": "",
                        "confidence": "",
                        "x1": "",
                        "y1": "",
                        "x2": "",
                        "y2": "",
                    }
                )
            frame_index += 1
    finally:
        cap.release()

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deployed YOLO model over temporal benchmark clips.")
    parser.add_argument("--model", default="Backend/best.pt")
    parser.add_argument("--input", required=True, help="A video file or folder containing benchmark clips.")
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    model = YOLO(args.model)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    videos = iter_video_paths(Path(args.input))
    if not videos:
        raise RuntimeError(f"No video files found under {args.input}")

    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for video_path in videos:
            writer.writerows(extract_video(model, video_path, args.sample_fps))


if __name__ == "__main__":
    main()
