from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

import numpy as np
import openslide


class WSIResourceLimitError(Exception):
    """Raised when a requested decoded region exceeds the configured bound."""


class WSILoader:
    """Metadata-aware, tile-bounded OpenSlide reader."""

    MAX_REGION_PIXELS = 25_000_000

    def __init__(
        self,
        file_path: Union[str, Path],
        *,
        objective_power: float | None = None,
        microns_per_pixel: Tuple[float, float] | None = None,
    ):
        self.file_path = Path(file_path).expanduser().resolve()
        if not self.file_path.is_file():
            raise FileNotFoundError(f"WSI file not found: {self.file_path}")
        if objective_power is not None and objective_power <= 0:
            raise ValueError("objective_power must be positive")
        if microns_per_pixel is not None and any(value <= 0 for value in microns_per_pixel):
            raise ValueError("microns_per_pixel values must be positive")
        try:
            self.slide = openslide.OpenSlide(str(self.file_path))
        except openslide.OpenSlideError as exc:
            raise ValueError(f"Failed to open WSI: {exc}") from exc
        self.level_count = self.slide.level_count
        self.level_dimensions = self.slide.level_dimensions
        self.level_downsamples = self.slide.level_downsamples
        self.properties = dict(self.slide.properties)
        self._objective_power = objective_power
        self._microns_per_pixel = microns_per_pixel

    def __enter__(self) -> "WSILoader":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def get_objective_power(self) -> float:
        if self._objective_power is not None:
            return self._objective_power
        value = self.properties.get(openslide.PROPERTY_NAME_OBJECTIVE_POWER)
        if value is None:
            value = self.properties.get("aperio.AppMag")
        if value is None:
            raise ValueError(
                "Objective power is absent from slide metadata; provide it explicitly."
            )
        try:
            objective = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid objective-power metadata: {value!r}") from exc
        if objective <= 0:
            raise ValueError("Objective power must be positive")
        return objective

    def get_level_for_magnification(self, target_magnification: float) -> int:
        if target_magnification <= 0:
            raise ValueError("target_magnification must be positive")
        target_downsample = self.get_objective_power() / target_magnification
        if target_downsample < 1:
            raise ValueError(
                "Target magnification exceeds the level-0 objective; upsampling is not allowed."
            )
        return int(self.slide.get_best_level_for_downsample(target_downsample))

    def read_region(self, level: int, x: int, y: int, width: int, height: int) -> np.ndarray:
        if not 0 <= level < self.level_count:
            raise ValueError("Requested pyramid level is out of bounds.")
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("Region coordinates and dimensions must be positive and in bounds.")
        if width * height > self.MAX_REGION_PIXELS:
            raise WSIResourceLimitError(
                f"Requested region has {width * height:,} decoded pixels; "
                f"limit is {self.MAX_REGION_PIXELS:,}."
            )
        level_width, level_height = self.level_dimensions[level]
        downsample = float(self.level_downsamples[level])
        max_x = int(max(0, (level_width - width) * downsample))
        max_y = int(max(0, (level_height - height) * downsample))
        if x > max_x or y > max_y:
            raise ValueError("Requested region extends beyond the slide level.")
        image = self.slide.read_region((x, y), level, (width, height)).convert("RGB")
        return np.asarray(image, dtype=np.uint8)

    def get_pixel_size_microns(self) -> Tuple[float, float]:
        if self._microns_per_pixel is not None:
            return self._microns_per_pixel
        x_value = self.properties.get(openslide.PROPERTY_NAME_MPP_X)
        y_value = self.properties.get(openslide.PROPERTY_NAME_MPP_Y)
        if x_value is None or y_value is None:
            raise ValueError(
                "Microns-per-pixel metadata is absent; provide calibration explicitly."
            )
        try:
            mpp = (float(x_value), float(y_value))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid microns-per-pixel metadata") from exc
        if any(value <= 0 for value in mpp):
            raise ValueError("Microns-per-pixel values must be positive")
        return mpp

    def get_mpp_at_level(self, level: int) -> Tuple[float, float]:
        if not 0 <= level < self.level_count:
            raise ValueError("Requested pyramid level is out of bounds.")
        mpp_x, mpp_y = self.get_pixel_size_microns()
        downsample = float(self.level_downsamples[level])
        return mpp_x * downsample, mpp_y * downsample

    def close(self) -> None:
        if getattr(self, "slide", None) is not None:
            self.slide.close()
            self.slide = None


# Backward-compatible import name for callers of the initial prototype.
WSI_DenialOfService_Error = WSIResourceLimitError
