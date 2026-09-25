from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import cv2
import numpy as np

from ..models.yolo_detector import YOLOAFBDetector
from .postprocessor import DetectionPostprocessor

try:
    import openslide

    OPENSLIDE_AVAILABLE = True
except ImportError:
    openslide = None
    OPENSLIDE_AVAILABLE = False


RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}
WSI_SUFFIXES = {".svs", ".ndpi", ".mrxs", ".scn", ".vms", ".vmu", ".bif"}


class SlidingWindowInference:
    """Tile raster images and WSIs, reproject detections, then apply global NMS."""

    def __init__(
        self,
        model: YOLOAFBDetector,
        tile_size: int = 640,
        overlap: int = 64,
        batch_size: int = 16,
        confidence_threshold: float = 0.25,
        *,
        enable_morphology_filter: bool = False,
        microns_per_pixel: float | None = None,
    ):
        if tile_size <= 0:
            raise ValueError("tile_size must be positive")
        if overlap < 0 or overlap >= tile_size:
            raise ValueError("overlap must be non-negative and smaller than tile_size")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if microns_per_pixel is not None and microns_per_pixel <= 0:
            raise ValueError("microns_per_pixel must be positive")

        self.model = model
        self.tile_size = tile_size
        self.overlap = overlap
        self.batch_size = batch_size
        self.confidence_threshold = confidence_threshold
        self.microns_per_pixel = microns_per_pixel
        self.postprocessor = DetectionPostprocessor(
            min_confidence=confidence_threshold,
            enable_morphology_filter=enable_morphology_filter,
        )

    @staticmethod
    def _tile_positions(length: int, tile_size: int, overlap: int) -> list[int]:
        if length <= tile_size:
            return [0]
        step = tile_size - overlap
        positions = list(range(0, length - tile_size + 1, step))
        final_position = length - tile_size
        if positions[-1] != final_position:
            positions.append(final_position)
        return positions

    def _coordinates(self, width: int, height: int) -> Iterator[Tuple[int, int]]:
        x_positions = self._tile_positions(width, self.tile_size, self.overlap)
        y_positions = self._tile_positions(height, self.tile_size, self.overlap)
        for y in y_positions:
            for x in x_positions:
                yield x, y

    @staticmethod
    def _translate(detections: List[Dict], x: int, y: int) -> List[Dict]:
        translated = []
        for detection in detections:
            clone = dict(detection)
            cx, cy, width, height = clone["bbox"]
            clone["bbox"] = [cx + x, cy + y, width, height]
            translated.append(clone)
        return translated

    @staticmethod
    def _contains_tissue(image: np.ndarray) -> bool:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) < 245.0

    def _infer_tile(self, image: np.ndarray, x: int, y: int) -> List[Dict]:
        detections = self.model.predict(
            image, conf_threshold=self.confidence_threshold
        )
        return self._translate(detections, x, y)

    def _process_raster(self, path: Path) -> tuple[list[Dict], int, float | None]:
        payload = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(payload, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not decode raster image: {path.name}")
        height, width = image.shape[:2]
        detections: list[Dict] = []
        tiles_processed = 0
        for x, y in self._coordinates(width, height):
            tile = image[y:y + self.tile_size, x:x + self.tile_size]
            if tile.size == 0 or not self._contains_tissue(tile):
                continue
            detections.extend(self._infer_tile(tile, x, y))
            tiles_processed += 1
        return detections, tiles_processed, self.microns_per_pixel

    @staticmethod
    def _slide_mpp(slide: Any) -> float | None:
        properties = slide.properties
        x_value = properties.get("openslide.mpp-x")
        y_value = properties.get("openslide.mpp-y")
        try:
            values = [float(value) for value in (x_value, y_value) if value is not None]
        except (TypeError, ValueError):
            return None
        return sum(values) / len(values) if values else None

    def _process_wsi(self, path: Path) -> tuple[list[Dict], int, float | None]:
        if not OPENSLIDE_AVAILABLE:
            raise RuntimeError(
                "OpenSlide is required for WSI input. Install OpenSlide or use a raster image."
            )
        slide = openslide.OpenSlide(str(path))
        detections: list[Dict] = []
        tiles_processed = 0
        try:
            width, height = slide.dimensions
            slide_mpp = self._slide_mpp(slide)
            for x, y in self._coordinates(width, height):
                region = slide.read_region(
                    (x, y), 0, (self.tile_size, self.tile_size)
                ).convert("RGB")
                tile = cv2.cvtColor(np.asarray(region), cv2.COLOR_RGB2BGR)
                if not self._contains_tissue(tile):
                    continue
                detections.extend(self._infer_tile(tile, x, y))
                tiles_processed += 1
        finally:
            slide.close()
        return detections, tiles_processed, self.microns_per_pixel or slide_mpp

    def process_slide(self, wsi_path: Path) -> Dict[str, Any]:
        start_time = time.perf_counter()
        path = Path(wsi_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Missing image payload: {path}")

        suffix = path.suffix.lower()
        if suffix in RASTER_SUFFIXES:
            detections, tiles_processed, mpp = self._process_raster(path)
            input_type = "raster"
        elif suffix in WSI_SUFFIXES:
            detections, tiles_processed, mpp = self._process_wsi(path)
            input_type = "wsi"
        elif suffix in {".tif", ".tiff"} and OPENSLIDE_AVAILABLE:
            try:
                detections, tiles_processed, mpp = self._process_wsi(path)
                input_type = "wsi"
            except openslide.OpenSlideUnsupportedFormatError:
                detections, tiles_processed, mpp = self._process_raster(path)
                input_type = "raster"
        elif suffix in {".tif", ".tiff"}:
            detections, tiles_processed, mpp = self._process_raster(path)
            input_type = "raster"
        else:
            raise ValueError(f"Unsupported image extension: {suffix or '<none>'}")

        final_detections = self.postprocessor.filter(
            detections, pixel_size_microns=mpp
        )
        return {
            "total_detections": len(final_detections),
            "detections": final_detections,
            "processing_time": time.perf_counter() - start_time,
            "tiles_processed": tiles_processed,
            "input_type": input_type,
            "microns_per_pixel": mpp,
            "morphology_filter_applied": self.postprocessor.enable_morphology_filter,
        }
