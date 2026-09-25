#!/usr/bin/env python3
"""Create and materialize a provenance-reviewed, group-safe dataset manifest.

The inventory command never changes source data. The build command refuses to
copy records until licenses, provenance, biological grouping, explicit splits,
duplicate isolation, and an entire held-out test source are documented.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from check_data_integrity import IMAGE_SUFFIXES, audit_dataset, infer_source


FIELDS = (
    "record_id",
    "source_id",
    "source_version",
    "original_split",
    "image_path",
    "label_path",
    "content_sha256",
    "biological_group_id",
    "target_split",
    "license_id",
    "provenance_status",
    "include",
    "exclusion_reason",
)
VALID_SPLITS = {"train", "val", "test"}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n", ""}
UNRESOLVED = {"", "unknown", "unverified", "pending", "tbd", "none"}
QUARANTINED_SOURCES = {"afb-detect"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_inventory(dataset_root: Path, output: Path) -> int:
    dataset_root = dataset_root.resolve()
    rows = []
    for split in sorted(VALID_SPLITS):
        image_dir = dataset_root / split / "images"
        label_dir = dataset_root / split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise FileNotFoundError(f"Missing split directories under {dataset_root / split}")
        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.is_file():
                raise FileNotFoundError(f"Missing label for {image_path}")
            source = infer_source(image_path.stem)
            digest = sha256_file(image_path)
            rows.append(
                {
                    "record_id": image_path.stem,
                    "source_id": source,
                    "source_version": "unknown",
                    "original_split": split,
                    "image_path": str(image_path.relative_to(dataset_root)),
                    "label_path": str(label_path.relative_to(dataset_root)),
                    "content_sha256": digest,
                    "biological_group_id": "",
                    "target_split": "",
                    "license_id": "",
                    "provenance_status": "needs_review",
                    "include": "false" if source in QUARANTINED_SOURCES else "",
                    "exclusion_reason": (
                        "quarantined_annotation_source"
                        if source in QUARANTINED_SOURCES
                        else ""
                    ),
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def parse_include(value: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"row {row_number}: include must be true or false")


def load_reviewed_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest is missing columns: {sorted(missing)}")
        return [dict(row) for row in reader]


def validate_manifest(
    rows: list[dict[str, str]],
    dataset_root: Path,
    test_sources: set[str],
) -> list[dict[str, str]]:
    if not test_sources:
        raise ValueError("At least one --test-source is required for held-out evaluation.")
    included = []
    groups: dict[str, set[str]] = defaultdict(set)
    hashes: dict[str, set[str]] = defaultdict(set)
    records = set()

    for row_number, row in enumerate(rows, start=2):
        record_id = row["record_id"].strip()
        if not record_id or record_id in records:
            raise ValueError(f"row {row_number}: record_id is blank or duplicated")
        records.add(record_id)
        include = parse_include(row["include"], row_number)
        if not include:
            if not row["exclusion_reason"].strip():
                raise ValueError(f"row {row_number}: excluded record needs a reason")
            continue

        source = row["source_id"].strip()
        split = row["target_split"].strip().lower()
        group = row["biological_group_id"].strip()
        license_id = row["license_id"].strip()
        provenance = row["provenance_status"].strip().lower()
        digest = row["content_sha256"].strip().lower()
        if source in QUARANTINED_SOURCES:
            raise ValueError(f"row {row_number}: quarantined source {source} cannot be included")
        if split not in VALID_SPLITS:
            raise ValueError(f"row {row_number}: target_split must be train, val, or test")
        if not group:
            raise ValueError(f"row {row_number}: biological_group_id is required")
        if license_id.lower() in UNRESOLVED:
            raise ValueError(f"row {row_number}: verified license_id is required")
        if provenance != "verified":
            raise ValueError(f"row {row_number}: provenance_status must be verified")
        image_path = (dataset_root / row["image_path"]).resolve()
        label_path = (dataset_root / row["label_path"]).resolve()
        if not image_path.is_relative_to(dataset_root) or not label_path.is_relative_to(dataset_root):
            raise ValueError(f"row {row_number}: source path escapes dataset root")
        if not image_path.is_file() or not label_path.is_file():
            raise ValueError(f"row {row_number}: image or label is missing")
        if len(digest) != 64 or sha256_file(image_path) != digest:
            raise ValueError(f"row {row_number}: content SHA-256 mismatch")
        if source in test_sources and split != "test":
            raise ValueError(f"row {row_number}: held-out source {source} must remain in test")
        if source not in test_sources and split == "test":
            raise ValueError(
                f"row {row_number}: test record source {source} was not declared --test-source"
            )
        groups[group].add(split)
        hashes[digest].add(split)
        included.append(row)

    if not included:
        raise ValueError("Manifest contains no included records")
    crossed_groups = [group for group, splits in groups.items() if len(splits) > 1]
    if crossed_groups:
        raise ValueError(f"Biological groups cross splits: {crossed_groups[:5]}")
    crossed_hashes = [digest for digest, splits in hashes.items() if len(splits) > 1]
    if crossed_hashes:
        raise ValueError(f"Exact duplicate content crosses splits: {crossed_hashes[:5]}")
    missing_test_sources = test_sources - {row["source_id"].strip() for row in included}
    if missing_test_sources:
        raise ValueError(f"Held-out sources have no included records: {sorted(missing_test_sources)}")
    return included


def materialize(
    rows: list[dict[str, str]], dataset_root: Path, output_root: Path
) -> None:
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_root}")
    for split in sorted(VALID_SPLITS):
        (output_root / split / "images").mkdir(parents=True, exist_ok=True)
        (output_root / split / "labels").mkdir(parents=True, exist_ok=True)
    for row in rows:
        split = row["target_split"].strip().lower()
        source_image = dataset_root / row["image_path"]
        source_label = dataset_root / row["label_path"]
        destination_image = output_root / split / "images" / source_image.name
        destination_label = output_root / split / "labels" / source_label.name
        if destination_image.exists() or destination_label.exists():
            raise FileExistsError(f"Duplicate destination filename: {source_image.stem}")
        shutil.copy2(source_image, destination_image)
        shutil.copy2(source_label, destination_label)


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory")
    inventory.add_argument(
        "--dataset-root",
        type=Path,
        default=project_root / "01_DATA" / "processed_tiles",
    )
    inventory.add_argument("--output", type=Path, required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--dataset-root", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--test-source", action="append", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "inventory":
        count = write_inventory(args.dataset_root, args.output)
        print(f"Inventory written: {args.output} ({count:,} records)")
        return 0

    dataset_root = args.dataset_root.resolve()
    output_root = args.output_root.resolve()
    rows = load_reviewed_manifest(args.manifest)
    included = validate_manifest(rows, dataset_root, set(args.test_source))
    materialize(included, dataset_root, output_root)
    audit = audit_dataset(output_root, quarantined_sources=set())
    report_path = output_root / "dataset_build_report.json"
    report_path.write_text(json.dumps(audit.to_dict(), indent=2) + "\n", encoding="utf-8")
    if not audit.passed:
        raise SystemExit(f"Materialized dataset failed audit; see {report_path}")
    print(f"Curated dataset passed audit: {output_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
