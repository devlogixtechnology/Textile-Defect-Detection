#!/usr/bin/env python3
"""
dataset_statistics.py
=====================
Standalone dataset statistics generator for the Textile Defect Detection project.

Generates:
  - Resolution statistics (min/max/median)
  - Class distribution (annotations per class)
  - Split distribution (images per split)
  - Missing/empty label file counts
  - CSV and Markdown table outputs

Usage:
    python scripts/dataset_statistics.py --dataset path/to/dataset --output reports/
"""

import argparse
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import yaml
from tqdm import tqdm

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SPLITS = ["train", "val", "valid", "test"]


# ─────────────────────────────────────────────────────────────────────────────
# Core statistics functions
# ─────────────────────────────────────────────────────────────────────────────

def load_yaml(yaml_path: Path) -> dict:
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_split_stats(dataset_root: Path, cfg: dict) -> dict:
    """Collect per-split image and annotation counts."""
    class_names = cfg.get("names", [])
    num_classes = len(class_names)

    stats = {
        "class_names": class_names,
        "num_classes": num_classes,
        "splits": {},
        "resolutions": [],
        "class_counts": Counter(),
        "total_images": 0,
        "total_annotations": 0,
        "missing_labels": 0,
        "empty_labels": 0,
        "invalid_labels": 0,
        "corrupted_images": 0,
    }

    for split in SPLITS:
        img_dir = dataset_root / "images" / split
        lbl_dir = dataset_root / "labels" / split

        if not img_dir.exists():
            continue

        image_files = sorted(
            p for p in img_dir.iterdir()
            if p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        split_data = {
            "image_count": len(image_files),
            "annotation_count": 0,
            "missing_labels": 0,
            "empty_labels": 0,
            "class_counts": Counter(),
        }

        for img_path in tqdm(image_files, desc=f"  Scanning {split}"):
            # Image resolution
            img = cv2.imread(str(img_path))
            if img is None:
                stats["corrupted_images"] += 1
                continue
            h, w = img.shape[:2]
            stats["resolutions"].append((w, h))

            # Label
            if lbl_dir.exists():
                label_path = lbl_dir / (img_path.stem + ".txt")
                if not label_path.exists():
                    split_data["missing_labels"] += 1
                    stats["missing_labels"] += 1
                    continue

                with open(label_path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]

                if not lines:
                    split_data["empty_labels"] += 1
                    stats["empty_labels"] += 1
                    continue

                for line in lines:
                    parts = line.split()
                    if len(parts) >= 1:
                        try:
                            cls_id = int(parts[0])
                            split_data["class_counts"][cls_id] += 1
                            stats["class_counts"][cls_id] += 1
                            split_data["annotation_count"] += 1
                            stats["total_annotations"] += 1
                        except (ValueError, IndexError):
                            stats["invalid_labels"] += 1

        stats["total_images"] += split_data["image_count"]
        stats["splits"][split] = split_data

    return stats


def resolution_stats(resolutions: list) -> dict:
    """Calculate min/max/median/mean resolution stats."""
    if not resolutions:
        return {}
    widths = [r[0] for r in resolutions]
    heights = [r[1] for r in resolutions]
    return {
        "count": len(resolutions),
        "min_w": int(np.min(widths)),
        "max_w": int(np.max(widths)),
        "median_w": int(np.median(widths)),
        "mean_w": float(np.mean(widths)),
        "min_h": int(np.min(heights)),
        "max_h": int(np.max(heights)),
        "median_h": int(np.median(heights)),
        "mean_h": float(np.mean(heights)),
        "unique_resolutions": len(set(resolutions)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def write_csv(output_dir: Path, filename: str, rows: list, header: list):
    path = output_dir / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  Saved: {path}")


def write_markdown_summary(output_path: Path, stats: dict, res_stats: dict, dataset_root: Path):
    class_names = stats["class_names"]
    lines = [
        "# Dataset Statistics Report\n",
        f"**Dataset path:** `{dataset_root}`\n",
        f"**Generated:** {__import__('datetime').datetime.now().isoformat()}\n",
        "\n---\n",
        "## Overall Counts\n",
        f"| Metric | Value |",
        "|---|---|",
        f"| Total images | {stats['total_images']} |",
        f"| Total annotations | {stats['total_annotations']} |",
        f"| Classes | {stats['num_classes']} |",
        f"| Corrupted images | {stats['corrupted_images']} |",
        f"| Missing label files | {stats['missing_labels']} |",
        f"| Empty label files | {stats['empty_labels']} |",
        f"| Invalid label lines | {stats['invalid_labels']} |",
        "",
        "## Split Distribution\n",
        "| Split | Images | Annotations |",
        "|---|---|---|",
    ]

    for split, data in stats["splits"].items():
        lines.append(f"| {split} | {data['image_count']} | {data['annotation_count']} |")

    lines += [
        "",
        "## Class Distribution\n",
        "| Class ID | Class Name | Annotations |",
        "|---|---|---|",
    ]
    for cls_id, count in sorted(stats["class_counts"].items()):
        name = class_names[cls_id] if cls_id < len(class_names) else f"unknown_{cls_id}"
        lines.append(f"| {cls_id} | {name} | {count} |")

    if res_stats:
        lines += [
            "",
            "## Resolution Statistics\n",
            "| Metric | Width | Height |",
            "|---|---|---|",
            f"| Min | {res_stats['min_w']} | {res_stats['min_h']} |",
            f"| Max | {res_stats['max_w']} | {res_stats['max_h']} |",
            f"| Median | {res_stats['median_w']} | {res_stats['median_h']} |",
            f"| Mean | {res_stats['mean_w']:.1f} | {res_stats['mean_h']:.1f} |",
            f"| Unique sizes | {res_stats['unique_resolutions']} | — |",
        ]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Saved: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_statistics(dataset_root: Path, output_dir: Path):
    yaml_path = dataset_root / "data.yaml"
    if not yaml_path.exists():
        print(f"[ERROR] data.yaml not found at {yaml_path}")
        return

    cfg = load_yaml(yaml_path)
    print(f"\nDataset: {dataset_root}")
    print(f"Classes: {cfg.get('names', [])}\n")

    stats = collect_split_stats(dataset_root, cfg)
    res = resolution_stats(stats["resolutions"])

    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV: class distribution
    write_csv(
        output_dir,
        "class_distribution.csv",
        [
            [cls_id, (cfg.get("names", [])[cls_id] if cls_id < len(cfg.get("names", [])) else "?"), cnt]
            for cls_id, cnt in sorted(stats["class_counts"].items())
        ],
        ["class_id", "class_name", "annotation_count"],
    )

    # CSV: split distribution
    write_csv(
        output_dir,
        "split_distribution.csv",
        [[split, d["image_count"], d["annotation_count"]] for split, d in stats["splits"].items()],
        ["split", "image_count", "annotation_count"],
    )

    # CSV: resolution distribution
    if res:
        unique_res = Counter(stats["resolutions"])
        write_csv(
            output_dir,
            "resolution_distribution.csv",
            [[w, h, cnt] for (w, h), cnt in sorted(unique_res.items(), key=lambda x: -x[1])],
            ["width", "height", "count"],
        )

    # Markdown summary
    write_markdown_summary(output_dir / "statistics_summary.md", stats, res, dataset_root)

    # Print summary
    print("\n" + "=" * 50)
    print("DATASET STATISTICS SUMMARY")
    print("=" * 50)
    print(f"Total images     : {stats['total_images']}")
    print(f"Total annotations: {stats['total_annotations']}")
    print(f"Classes          : {stats['num_classes']}")
    for split, data in stats["splits"].items():
        print(f"  {split:10s}   : {data['image_count']} images, {data['annotation_count']} annotations")
    if res:
        print(f"Resolution range : {res['min_w']}×{res['min_h']} to {res['max_w']}×{res['max_h']}")
        print(f"Median resolution: {res['median_w']}×{res['median_h']}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Generate dataset statistics for a YOLO dataset.")
    parser.add_argument("--dataset", type=str, required=True, help="Path to dataset root")
    parser.add_argument("--output", type=str, default="reports/", help="Output directory for CSV/MD reports")
    args = parser.parse_args()

    dataset_root = Path(args.dataset).resolve()
    output_dir = Path(args.output).resolve()
    run_statistics(dataset_root, output_dir)


if __name__ == "__main__":
    main()
