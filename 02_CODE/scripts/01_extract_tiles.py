import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

try:
    import openslide
    OPENSLIDE_AVAILABLE = True
except ImportError:
    OPENSLIDE_AVAILABLE = False


def process_single_tile(args):
    slide_path, x, y, patch_size, output_dir, basename = args
    import openslide

    slide = openslide.OpenSlide(slide_path)
    try:
        rgba = slide.read_region((x, y), 0, (patch_size, patch_size))
        img = cv2.cvtColor(np.asarray(rgba), cv2.COLOR_RGBA2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if cv2.countNonZero(gray) and np.mean(gray) < 220:
            cv2.imwrite(str(Path(output_dir) / f"{basename}_{x}_{y}.jpg"), img)
            return 1
        return 0
    finally:
        slide.close()


def extract_wsi_patches(wsi_path: Path, output_dir: Path, patch_size: int = 512, overlap: int = 0):
    if patch_size <= 0 or overlap < 0 or overlap >= patch_size:
        raise ValueError("Require patch_size > 0 and 0 <= overlap < patch_size.")
    output_dir.mkdir(parents=True, exist_ok=True)
    basename = wsi_path.stem
    step = patch_size - overlap

    if OPENSLIDE_AVAILABLE and wsi_path.suffix.lower() in {".svs", ".ndpi", ".vms", ".scn", ".mrxs"}:
        slide = openslide.OpenSlide(str(wsi_path))
        try:
            width, height = slide.dimensions
        finally:
            slide.close()
        tasks = [
            (str(wsi_path), x, y, patch_size, str(output_dir), basename)
            for y in range(0, height - patch_size + 1, step)
            for x in range(0, width - patch_size + 1, step)
        ]
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            count = sum(executor.map(process_single_tile, tasks))
        print(f"Extracted {count} tissue tiles.")
        return

    img = cv2.imread(str(wsi_path))
    if img is None:
        raise ValueError(f"Could not decode image: {wsi_path}")
    height, width = img.shape[:2]
    count = 0
    for y in range(0, height - patch_size + 1, step):
        for x in range(0, width - patch_size + 1, step):
            patch = img[y:y + patch_size, x:x + patch_size]
            if np.mean(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)) < 230:
                cv2.imwrite(str(output_dir / f"{basename}_{x}_{y}.jpg"), patch)
                count += 1
    print(f"Extracted {count} tissue tiles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wsi", required=True)
    parser.add_argument("--out", default="01_DATA/raw_tiles")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--overlap", type=int, default=0)
    args = parser.parse_args()
    extract_wsi_patches(Path(args.wsi).resolve(), Path(args.out).resolve(), args.size, args.overlap)
