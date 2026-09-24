#!/usr/bin/env python3
"""Import explicitly mapped public Roboflow AFB datasets.

A dataset is never ingested unless its AFB class IDs are declared. Source train,
validation and test partitions remain separate.
"""
import argparse
import os
import shutil
from pathlib import Path

from roboflow import Roboflow

DATASETS = [
    # Fill afb_class_ids only after verifying the source dataset's class names/version.
    {"workspace": "harshita-hhmns", "project": "afb-u0hdn", "version": 1, "afb_class_ids": None},
    {"workspace": "swu-5alfk", "project": "tuberculosis-p8whq", "version": 1, "afb_class_ids": None},
    {"workspace": "swu-5alfk", "project": "tuberculosis-czyfb", "version": 3, "afb_class_ids": None},
    {"workspace": "huzaifa-athar", "project": "afb-zpazz", "version": 1, "afb_class_ids": None},
    {"workspace": "naresuan-university-1yqlq", "project": "technique-for-detecting-acid-fast-bacilli", "version": 15, "afb_class_ids": None},
]


def remap_label(src: Path, dst: Path, afb_class_ids: set[int]) -> None:
    lines = []
    if src.exists():
        for raw in src.read_text(encoding="utf-8").splitlines():
            parts = raw.split()
            if len(parts) != 5:
                raise ValueError(f"Malformed YOLO label in {src}: {raw!r}")
            source_class = int(parts[0])
            if source_class in afb_class_ids:
                lines.append("0 " + " ".join(parts[1:]))
    dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def ingest(api_key: str, spec: dict, target_root: Path) -> int:
    if spec["afb_class_ids"] is None:
        raise ValueError(
            f"{spec['project']}: afb_class_ids has not been verified. "
            "Inspect the pinned source dataset version before ingestion."
        )
    dataset = (
        Roboflow(api_key=api_key)
        .workspace(spec["workspace"])
        .project(spec["project"])
        .version(spec["version"])
        .download("yolov8")
    )
    source = Path(dataset.location)
    count = 0
    try:
        for source_split, target_split in (("train", "train"), ("valid", "val"), ("test", "test")):
            images = source / source_split / "images"
            labels = source / source_split / "labels"
            if not images.exists():
                continue
            dst_images = target_root / target_split / "images"
            dst_labels = target_root / target_split / "labels"
            dst_images.mkdir(parents=True, exist_ok=True)
            dst_labels.mkdir(parents=True, exist_ok=True)
            for image in images.iterdir():
                if image.suffix.lower() not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
                    continue
                stem = f"pub_{spec['project']}_{image.stem}"
                shutil.copy2(image, dst_images / f"{stem}{image.suffix.lower()}")
                remap_label(labels / f"{image.stem}.txt", dst_labels / f"{stem}.txt",
                            set(spec["afb_class_ids"]))
                count += 1
    finally:
        shutil.rmtree(source, ignore_errors=True)
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default=os.getenv("ROBOFLOW_API_KEY"))
    parser.add_argument("--project", help="Ingest one configured project only")
    args = parser.parse_args()
    if not args.key:
        raise SystemExit("ROBOFLOW_API_KEY is required.")

    selected = [d for d in DATASETS if not args.project or d["project"] == args.project]
    if not selected:
        raise SystemExit("Unknown configured project.")
    target = Path("01_DATA/processed_tiles")
    for spec in selected:
        print(f"{spec['project']}: {ingest(args.key, spec, target)} images imported")


if __name__ == "__main__":
    main()
