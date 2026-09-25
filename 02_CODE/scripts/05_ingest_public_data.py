#!/usr/bin/env python3
"""Import explicitly mapped public Roboflow AFB datasets.

A dataset is never ingested unless its AFB class IDs are declared. Source train,
validation and test partitions remain separate.
"""
import argparse
import math
import os
import shutil
from pathlib import Path

DATASETS = [
    # 🛡️ Baseline TB-AFB microscopy cohorts (7,979 patches)
    {"workspace": "swu-5alfk", "project": "tuberculosis-p8whq", "version": 1, "afb_class_ids": {0, 1}},
    {"workspace": "swu-5alfk", "project": "tuberculosis-czyfb", "version": 3, "afb_class_ids": {0}},
    {"workspace": "huzaifa-athar", "project": "afb-zpazz", "version": 1, "afb_class_ids": {0}},
    {"workspace": "naresuan-university-1yqlq", "project": "technique-for-detecting-acid-fast-bacilli", "version": 15, "afb_class_ids": {0, 1}},

    # 🚀 Expansion Cohort #1 (2,899 patches, 10,000+ AFB instances)
    {"workspace": "detection-tb", "project": "tuberculosis-2", "version": 5, "afb_class_ids": {0, 1}},

    # 🚀 Expansion Cohort #2 (2,108 patches, 8,817 AFB instances)
    {
        "workspace": "afb-dataset",
        "project": "afb-detect",
        "version": 4,
        "afb_class_ids": {0},
        "quarantined": True,
        "quarantine_reason": (
            "Annotation audit found predominantly image-spanning boxes. "
            "Verify the upstream task, class map, and annotation format first."
        ),
    },

    # 🚀 Expansion Cohort #3 (371 patches, 1,959 AFB instances)
    {"workspace": "suci-aulia", "project": "afb-test-y7", "version": 10, "afb_class_ids": {0}},
]


def remap_label(src: Path, dst: Path, afb_class_ids: set[int]) -> None:
    """Convert a verified YOLO detection label without silent repair.

    Non-AFB classes are deliberately omitted. Any malformed annotation for a
    selected AFB class aborts ingestion so polygons or corrupt boxes cannot be
    silently truncated into a different task.
    """
    lines = []
    if src.exists():
        for line_number, raw in enumerate(
            src.read_text(encoding="utf-8").splitlines(), start=1
        ):
            parts = raw.split()
            if not parts:
                continue
            try:
                raw_class = float(parts[0])
            except ValueError as exc:
                raise ValueError(f"{src}:{line_number}: non-numeric class ID") from exc
            source_class = int(raw_class)
            if raw_class != source_class:
                raise ValueError(f"{src}:{line_number}: class ID must be an integer")
            if source_class not in afb_class_ids:
                continue
            if len(parts) != 5:
                raise ValueError(
                    f"{src}:{line_number}: expected YOLO detection format "
                    f"(class x y width height), found {len(parts)} values"
                )
            try:
                x, y, width, height = map(float, parts[1:])
            except ValueError as exc:
                raise ValueError(f"{src}:{line_number}: non-numeric box value") from exc
            values = (x, y, width, height)
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{src}:{line_number}: non-finite box value")
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError(f"{src}:{line_number}: box center is outside [0, 1]")
            if not (0 < width <= 1 and 0 < height <= 1):
                raise ValueError(f"{src}:{line_number}: box dimensions must be in (0, 1]")
            tolerance = 1e-6
            if (
                x - width / 2 < -tolerance
                or y - height / 2 < -tolerance
                or x + width / 2 > 1 + tolerance
                or y + height / 2 > 1 + tolerance
            ):
                raise ValueError(f"{src}:{line_number}: box extends outside image bounds")
            lines.append(f"0 {x:.10g} {y:.10g} {width:.10g} {height:.10g}")
    dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def ingest(api_key: str, spec: dict, target_root: Path) -> int:
    try:
        from roboflow import Roboflow
    except ImportError as exc:
        raise RuntimeError(
            "Roboflow is required only for downloading configured public datasets."
        ) from exc
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
                stem = f"pub_{spec['project']}_v{spec['version']}_{image.stem}"
                destination_image = dst_images / f"{stem}{image.suffix.lower()}"
                destination_label = dst_labels / f"{stem}.txt"
                if destination_image.exists() or destination_label.exists():
                    raise FileExistsError(
                        f"Refusing to overwrite an existing ingestion record: {stem}"
                    )
                remap_label(
                    labels / f"{image.stem}.txt",
                    destination_label,
                    set(spec["afb_class_ids"]),
                )
                shutil.copy2(image, destination_image)
                count += 1
    finally:
        shutil.rmtree(source, ignore_errors=True)
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default=os.getenv("ROBOFLOW_API_KEY"))
    parser.add_argument("--project", help="Ingest one configured project only")
    parser.add_argument(
        "--allow-quarantined",
        action="store_true",
        help="Explicitly allow a quarantined source after independent review.",
    )
    args = parser.parse_args()
    if not args.key:
        raise SystemExit("ROBOFLOW_API_KEY is required.")

    selected = [d for d in DATASETS if not args.project or d["project"] == args.project]
    if not selected:
        raise SystemExit("Unknown configured project.")
    quarantined = [spec for spec in selected if spec.get("quarantined")]
    if quarantined and not args.allow_quarantined:
        details = "; ".join(
            f"{spec['project']}: {spec['quarantine_reason']}" for spec in quarantined
        )
        raise SystemExit(f"Refusing quarantined source(s): {details}")
    target = Path("01_DATA/processed_tiles")
    for spec in selected:
        print(f"{spec['project']}: {ingest(args.key, spec, target)} images imported")


if __name__ == "__main__":
    main()
