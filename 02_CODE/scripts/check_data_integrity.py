#!/usr/bin/env python3
"""Validate the AFB detection dataset before training or evaluation.

The audit is deliberately strict. It checks every declared split, validates
YOLO boxes, decodes images, reports source-level distributions, and detects
byte-identical images within and across splits. A non-zero exit status means
the dataset must not be used for a reported training or evaluation run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DEFAULT_SPLITS = ("train", "val", "test")
DEFAULT_QUARANTINED_SOURCES = {"afb-detect"}


@dataclass(frozen=True)
class ImageRecord:
    split: str
    path: Path
    source: str


@dataclass
class SourceStats:
    images: int = 0
    boxes: int = 0
    empty_labels: int = 0
    large_boxes: int = 0
    widths: list[float] = field(default_factory=list, repr=False)
    heights: list[float] = field(default_factory=list, repr=False)

    def summary(self) -> dict[str, int | float | None]:
        return {
            "images": self.images,
            "boxes": self.boxes,
            "empty_labels": self.empty_labels,
            "large_boxes": self.large_boxes,
            "median_width": statistics.median(self.widths) if self.widths else None,
            "median_height": statistics.median(self.heights) if self.heights else None,
        }


@dataclass
class AuditReport:
    dataset_root: str
    splits: dict[str, dict[str, int]] = field(default_factory=dict)
    sources: dict[str, dict[str, int | float | None]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cross_split_duplicate_groups: list[dict[str, object]] = field(default_factory=list)
    within_split_duplicate_groups: dict[str, int] = field(default_factory=dict)
    total_images: int = 0
    total_boxes: int = 0
    total_empty_labels: int = 0

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["passed"] = self.passed
        return result


def infer_source(stem: str) -> str:
    """Return a stable source key from the ingestion filename convention."""
    if stem.startswith("pub_"):
        remainder = stem[4:]
        return remainder.split("_", 1)[0]
    if stem.startswith("acad_mendeley_"):
        return "acad_mendeley"
    if stem.startswith("acad_"):
        return "academic_negative_controls"
    if stem.startswith("uganda_"):
        return "uganda"
    return stem.split("_", 1)[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_image(path: Path) -> bool:
    """Decode an image without making OpenCV a requirement for light tests."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return True
    try:
        payload = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(payload, cv2.IMREAD_UNCHANGED)
    except (OSError, ValueError):
        return False
    return image is not None and image.size > 0


def iter_images(directory: Path) -> Iterable[Path]:
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def audit_dataset(
    dataset_root: Path,
    *,
    splits: tuple[str, ...] = DEFAULT_SPLITS,
    allowed_classes: set[int] | None = None,
    quarantined_sources: set[str] | None = None,
    large_box_threshold: float = 0.20,
    decode_images: bool = True,
) -> AuditReport:
    dataset_root = dataset_root.resolve()
    allowed_classes = {0} if allowed_classes is None else allowed_classes
    quarantined_sources = (
        DEFAULT_QUARANTINED_SOURCES
        if quarantined_sources is None
        else quarantined_sources
    )
    report = AuditReport(dataset_root=str(dataset_root))
    hashes: dict[str, list[ImageRecord]] = defaultdict(list)
    source_stats: dict[str, SourceStats] = defaultdict(SourceStats)

    for split in splits:
        image_dir = dataset_root / split / "images"
        label_dir = dataset_root / split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            report.errors.append(
                f"{split}: expected images/ and labels/ under {dataset_root / split}"
            )
            continue

        images = list(iter_images(image_dir))
        labels = sorted(path for path in label_dir.glob("*.txt") if path.is_file())
        image_stems = {path.stem for path in images}
        label_stems = {path.stem for path in labels}
        missing_labels = sorted(image_stems - label_stems)
        orphan_labels = sorted(label_stems - image_stems)
        if missing_labels:
            report.errors.append(
                f"{split}: {len(missing_labels)} images have no label file; "
                f"examples: {missing_labels[:3]}"
            )
        if orphan_labels:
            report.errors.append(
                f"{split}: {len(orphan_labels)} labels have no image; "
                f"examples: {orphan_labels[:3]}"
            )

        split_boxes = 0
        split_empty = 0
        split_invalid = 0
        split_decode_failures = 0
        for image_path in images:
            source = infer_source(image_path.stem)
            source_stats[source].images += 1
            if image_path.stat().st_size == 0:
                report.errors.append(f"{split}: zero-byte image: {image_path.name}")
                split_decode_failures += 1
            elif decode_images and not decode_image(image_path):
                report.errors.append(f"{split}: image cannot be decoded: {image_path.name}")
                split_decode_failures += 1
            try:
                digest = sha256_file(image_path)
            except OSError as exc:
                report.errors.append(f"{split}: cannot hash {image_path.name}: {exc}")
            else:
                hashes[digest].append(ImageRecord(split, image_path, source))

            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                continue
            try:
                lines = [
                    line.strip()
                    for line in label_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except (OSError, UnicodeError) as exc:
                report.errors.append(f"{split}: cannot read {label_path.name}: {exc}")
                split_invalid += 1
                continue
            if not lines:
                split_empty += 1
                source_stats[source].empty_labels += 1
            for line_number, line in enumerate(lines, start=1):
                parts = line.split()
                location = f"{split}/{label_path.name}:{line_number}"
                if len(parts) != 5:
                    report.errors.append(
                        f"{location}: expected 5 YOLO values, found {len(parts)}"
                    )
                    split_invalid += 1
                    continue
                try:
                    raw_class, x, y, width, height = map(float, parts)
                except ValueError:
                    report.errors.append(f"{location}: non-numeric YOLO value")
                    split_invalid += 1
                    continue
                values = (raw_class, x, y, width, height)
                if not all(math.isfinite(value) for value in values):
                    report.errors.append(f"{location}: non-finite YOLO value")
                    split_invalid += 1
                    continue
                class_id = int(raw_class)
                if raw_class != class_id or class_id not in allowed_classes:
                    report.errors.append(
                        f"{location}: class {raw_class!r} is not one of {sorted(allowed_classes)}"
                    )
                    split_invalid += 1
                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                    report.errors.append(f"{location}: center lies outside normalized image bounds")
                    split_invalid += 1
                if not (0.0 < width <= 1.0 and 0.0 < height <= 1.0):
                    report.errors.append(f"{location}: width and height must be in (0, 1]")
                    split_invalid += 1
                tolerance = 1e-6
                if (
                    x - width / 2 < -tolerance
                    or y - height / 2 < -tolerance
                    or x + width / 2 > 1.0 + tolerance
                    or y + height / 2 > 1.0 + tolerance
                ):
                    report.errors.append(f"{location}: box extends outside image bounds")
                    split_invalid += 1

                split_boxes += 1
                stats = source_stats[source]
                stats.boxes += 1
                stats.widths.append(width)
                stats.heights.append(height)
                if width > large_box_threshold or height > large_box_threshold:
                    stats.large_boxes += 1

        report.splits[split] = {
            "images": len(images),
            "labels": len(labels),
            "boxes": split_boxes,
            "empty_labels": split_empty,
            "invalid_annotations": split_invalid,
            "decode_failures": split_decode_failures,
        }
        report.total_images += len(images)
        report.total_boxes += split_boxes
        report.total_empty_labels += split_empty

    within_split = Counter()
    for digest, records in sorted(hashes.items()):
        if len(records) < 2:
            continue
        record_splits = sorted({record.split for record in records})
        if len(record_splits) > 1:
            report.cross_split_duplicate_groups.append(
                {
                    "sha256": digest,
                    "splits": record_splits,
                    "files": [
                        str(record.path.relative_to(dataset_root)) for record in records
                    ],
                }
            )
        else:
            within_split[record_splits[0]] += 1
    report.within_split_duplicate_groups = {
        split: within_split.get(split, 0) for split in splits
    }
    if report.cross_split_duplicate_groups:
        report.errors.append(
            f"{len(report.cross_split_duplicate_groups)} byte-identical image groups cross dataset splits"
        )

    report.sources = {
        source: stats.summary() for source, stats in sorted(source_stats.items())
    }
    present_quarantined = sorted(set(report.sources) & quarantined_sources)
    if present_quarantined:
        report.errors.append(
            "quarantined sources are present: " + ", ".join(present_quarantined)
        )
    for source, stats in sorted(source_stats.items()):
        if stats.boxes and stats.large_boxes / stats.boxes >= 0.25:
            report.warnings.append(
                f"{source}: {stats.large_boxes}/{stats.boxes} boxes exceed "
                f"the normalized {large_box_threshold:.2f} size threshold"
            )

    return report


def print_report(report: AuditReport) -> None:
    status = "PASS" if report.passed else "FAIL"
    print(f"DATA VALIDATION: {status}")
    print(f"Root: {report.dataset_root}")
    print(
        f"Images: {report.total_images:,} | Boxes: {report.total_boxes:,} | "
        f"Empty labels: {report.total_empty_labels:,}"
    )
    for split, stats in report.splits.items():
        print(
            f"  {split:<5} images={stats['images']:,} boxes={stats['boxes']:,} "
            f"empty={stats['empty_labels']:,} invalid={stats['invalid_annotations']:,}"
        )
    print(
        "Cross-split exact duplicate groups: "
        f"{len(report.cross_split_duplicate_groups):,}"
    )
    for source, stats in report.sources.items():
        print(
            f"  source={source:<24} images={stats['images']:,} boxes={stats['boxes']:,} "
            f"large={stats['large_boxes']:,} median_wh="
            f"{stats['median_width']!s}/{stats['median_height']!s}"
        )
    if report.warnings:
        print("WARNINGS")
        for warning in report.warnings:
            print(f"  - {warning}")
    if report.errors:
        print("ERRORS")
        for error in report.errors[:50]:
            print(f"  - {error}")
        remaining = len(report.errors) - 50
        if remaining > 0:
            print(f"  - ... {remaining:,} additional errors are in the JSON report")


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=project_root / "01_DATA" / "processed_tiles",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=project_root / "06_LOGS" / "audits" / "data_integrity.json",
    )
    parser.add_argument("--skip-decode", action="store_true")
    parser.add_argument("--warn-only", action="store_true")
    parser.add_argument(
        "--quarantined-source",
        action="append",
        default=sorted(DEFAULT_QUARANTINED_SOURCES),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_dataset(
        args.dataset_root,
        quarantined_sources=set(args.quarantined_source),
        decode_images=not args.skip_decode,
    )
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(
        json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    print_report(report)
    print(f"Machine-readable report: {args.json_report}")
    return 0 if report.passed or args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
