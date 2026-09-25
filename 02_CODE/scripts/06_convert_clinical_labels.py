#!/usr/bin/env python3
"""Convert reviewed Pascal VOC AFB boxes into a provenance-staged YOLO import."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ResearchAnnotationConverter:
    def __init__(
        self,
        target_root: Path,
        source_id: str,
        source_version: str,
        license_id: str,
        afb_names: set[str] | None = None,
    ):
        self.target_root = target_root.resolve()
        self.source_id = source_id.strip()
        self.source_version = source_version.strip()
        self.license_id = license_id.strip()
        self.afb_names = {
            name.lower()
            for name in (afb_names or {"afb", "bacillus", "acid-fast bacillus"})
        }
        if not self.source_id or not self.source_version or not self.license_id:
            raise ValueError("source_id, source_version, and license_id are required")
        if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in self.source_id):
            raise ValueError("source_id may contain letters, numbers, hyphens, and underscores only")

    def convert_pascal_voc(self, xml_dir: Path, img_dir: Path, split: str) -> int:
        if split not in {"train", "val", "test", "unassigned"}:
            raise ValueError("split must be train, val, test, or unassigned")
        xml_dir = xml_dir.resolve()
        img_dir = img_dir.resolve()
        destination = self.target_root / self.source_id / split
        dst_img = destination / "images"
        dst_lbl = destination / "labels"
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)
        records = []

        for xml_path in sorted(xml_dir.glob("*.xml")):
            try:
                root = ET.parse(xml_path).getroot()
            except ET.ParseError as exc:
                raise ValueError(f"Malformed XML: {xml_path}") from exc
            filename = (root.findtext("filename") or "").strip()
            if not filename or Path(filename).name != filename:
                raise ValueError(f"{xml_path}: missing or unsafe filename")
            source_image = img_dir / filename
            if not source_image.is_file() or source_image.suffix.lower() not in IMAGE_SUFFIXES:
                raise FileNotFoundError(f"{xml_path}: source image not found: {filename}")
            size = root.find("size")
            if size is None:
                raise ValueError(f"{xml_path}: missing image size")
            width = int(size.findtext("width", "0"))
            height = int(size.findtext("height", "0"))
            if width <= 0 or height <= 0:
                raise ValueError(f"{xml_path}: non-positive image dimensions")

            labels = []
            for object_number, obj in enumerate(root.findall("object"), start=1):
                name = (obj.findtext("name") or "").strip().lower()
                if name not in self.afb_names:
                    continue
                box = obj.find("bndbox")
                if box is None:
                    raise ValueError(f"{xml_path}: object {object_number} has no bndbox")
                try:
                    xmin = float(box.findtext("xmin", ""))
                    ymin = float(box.findtext("ymin", ""))
                    xmax = float(box.findtext("xmax", ""))
                    ymax = float(box.findtext("ymax", ""))
                except ValueError as exc:
                    raise ValueError(
                        f"{xml_path}: object {object_number} has non-numeric bounds"
                    ) from exc
                if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
                    raise ValueError(
                        f"{xml_path}: object {object_number} lies outside the image"
                    )
                center_x = (xmin + xmax) / (2 * width)
                center_y = (ymin + ymax) / (2 * height)
                box_width = (xmax - xmin) / width
                box_height = (ymax - ymin) / height
                labels.append(
                    f"0 {center_x:.10g} {center_y:.10g} "
                    f"{box_width:.10g} {box_height:.10g}"
                )

            stem = f"{self.source_id}_v{self.source_version}_{xml_path.stem}"
            destination_image = dst_img / f"{stem}{source_image.suffix.lower()}"
            destination_label = dst_lbl / f"{stem}.txt"
            if destination_image.exists() or destination_label.exists():
                raise FileExistsError(f"Refusing to overwrite staged record: {stem}")
            shutil.copy2(source_image, destination_image)
            destination_label.write_text(
                "\n".join(labels) + ("\n" if labels else ""), encoding="utf-8"
            )
            records.append(
                {
                    "record_id": stem,
                    "source_id": self.source_id,
                    "source_version": self.source_version,
                    "license_id": self.license_id,
                    "declared_split": split,
                    "original_filename": filename,
                    "image_sha256": sha256_file(destination_image),
                    "annotation_file": destination_label.name,
                    "afb_boxes": len(labels),
                }
            )

        manifest = destination / "conversion_manifest.csv"
        with manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=records[0].keys() if records else (
                "record_id", "source_id", "source_version", "license_id",
                "declared_split", "original_filename", "image_sha256",
                "annotation_file", "afb_boxes",
            ))
            writer.writeheader()
            writer.writerows(records)
        print(f"Converted {len(records):,} images into staging. Manifest: {manifest}")
        return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-dir", type=Path, required=True)
    parser.add_argument("--img-dir", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--license-id", required=True)
    parser.add_argument(
        "--target-root", type=Path, default=Path("01_DATA/import_staging")
    )
    parser.add_argument(
        "--split", choices=["train", "val", "test", "unassigned"], default="unassigned"
    )
    parser.add_argument("--afb-name", action="append", dest="afb_names")
    args = parser.parse_args()
    names = set(args.afb_names) if args.afb_names else None
    ResearchAnnotationConverter(
        args.target_root,
        args.source_id,
        args.source_version,
        args.license_id,
        names,
    ).convert_pascal_voc(args.xml_dir, args.img_dir, args.split)


if __name__ == "__main__":
    main()
