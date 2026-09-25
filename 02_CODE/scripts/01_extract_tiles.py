#!/usr/bin/env python3
"""Stream de-identified raster/WSI tiles and record a reproducible manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import cv2
import numpy as np

try:
    import openslide

    OPENSLIDE_AVAILABLE = True
except ImportError:
    openslide = None
    OPENSLIDE_AVAILABLE = False


WSI_SUFFIXES = {".svs", ".ndpi", ".vms", ".vmu", ".scn", ".bif", ".mrxs"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tile_positions(length: int, tile_size: int, overlap: int) -> list[int]:
    if length <= tile_size:
        return [0]
    step = tile_size - overlap
    positions = list(range(0, length - tile_size + 1, step))
    final = length - tile_size
    if positions[-1] != final:
        positions.append(final)
    return positions


def tissue_fraction(image: np.ndarray, background_threshold: int = 235) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(np.count_nonzero(gray < background_threshold) / gray.size)


def write_tile(path: Path, image: np.ndarray) -> None:
    ok, payload = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise OSError(f"Could not encode tile: {path}")
    path.write_bytes(payload.tobytes())


def extract_wsi_patches(
    wsi_path: Path,
    output_dir: Path,
    patch_size: int = 640,
    overlap: int = 64,
    min_tissue_fraction: float = 0.05,
) -> int:
    if patch_size <= 0 or overlap < 0 or overlap >= patch_size:
        raise ValueError("Require patch_size > 0 and 0 <= overlap < patch_size.")
    if not 0 <= min_tissue_fraction <= 1:
        raise ValueError("min_tissue_fraction must be between 0 and 1.")
    wsi_path = wsi_path.expanduser().resolve()
    if not wsi_path.is_file():
        raise FileNotFoundError(wsi_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_hash = sha256_file(wsi_path)
    slide_id = source_hash[:16]
    records = []

    use_openslide = wsi_path.suffix.lower() in WSI_SUFFIXES
    if wsi_path.suffix.lower() in {".tif", ".tiff"} and OPENSLIDE_AVAILABLE:
        try:
            probe = openslide.OpenSlide(str(wsi_path))
            probe.close()
            use_openslide = True
        except openslide.OpenSlideUnsupportedFormatError:
            use_openslide = False

    if use_openslide:
        if not OPENSLIDE_AVAILABLE:
            raise RuntimeError("OpenSlide is required for this WSI format.")
        slide = openslide.OpenSlide(str(wsi_path))
        try:
            width, height = slide.dimensions
            mpp_x = slide.properties.get("openslide.mpp-x")
            mpp_y = slide.properties.get("openslide.mpp-y")
            for y in tile_positions(height, patch_size, overlap):
                for x in tile_positions(width, patch_size, overlap):
                    region = slide.read_region(
                        (x, y), 0, (patch_size, patch_size)
                    ).convert("RGB")
                    tile = cv2.cvtColor(np.asarray(region), cv2.COLOR_RGB2BGR)
                    fraction = tissue_fraction(tile)
                    if fraction < min_tissue_fraction:
                        continue
                    filename = f"{slide_id}_{x}_{y}.jpg"
                    write_tile(output_dir / filename, tile)
                    records.append(
                        {
                            "slide_content_sha256": source_hash,
                            "tile_filename": filename,
                            "x_level0": x,
                            "y_level0": y,
                            "width": patch_size,
                            "height": patch_size,
                            "level": 0,
                            "mpp_x": mpp_x or "",
                            "mpp_y": mpp_y or "",
                            "tissue_fraction": f"{fraction:.6f}",
                        }
                    )
        finally:
            slide.close()
    else:
        payload = np.fromfile(str(wsi_path), dtype=np.uint8)
        image = cv2.imdecode(payload, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not decode image: {wsi_path.name}")
        height, width = image.shape[:2]
        for y in tile_positions(height, patch_size, overlap):
            for x in tile_positions(width, patch_size, overlap):
                tile = image[y:y + patch_size, x:x + patch_size]
                fraction = tissue_fraction(tile)
                if fraction < min_tissue_fraction:
                    continue
                filename = f"{slide_id}_{x}_{y}.jpg"
                write_tile(output_dir / filename, tile)
                records.append(
                    {
                        "slide_content_sha256": source_hash,
                        "tile_filename": filename,
                        "x_level0": x,
                        "y_level0": y,
                        "width": tile.shape[1],
                        "height": tile.shape[0],
                        "level": 0,
                        "mpp_x": "",
                        "mpp_y": "",
                        "tissue_fraction": f"{fraction:.6f}",
                    }
                )

    manifest_path = output_dir / f"{slide_id}_tiles_manifest.csv"
    fieldnames = (
        "slide_content_sha256",
        "tile_filename",
        "x_level0",
        "y_level0",
        "width",
        "height",
        "level",
        "mpp_x",
        "mpp_y",
        "tissue_fraction",
    )
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Extracted {len(records):,} tissue tiles. Manifest: {manifest_path}")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wsi", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("01_DATA/raw_tiles"))
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--overlap", type=int, default=64)
    parser.add_argument("--min-tissue-fraction", type=float, default=0.05)
    args = parser.parse_args()
    extract_wsi_patches(
        args.wsi,
        args.out.resolve(),
        args.size,
        args.overlap,
        args.min_tissue_fraction,
    )


if __name__ == "__main__":
    main()
