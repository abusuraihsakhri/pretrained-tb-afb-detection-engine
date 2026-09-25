from __future__ import annotations

from typing import Optional

import numpy as np


class MacenkoNormalizer:
    """Experimental two-stain optical-density normalization.

    The implementation estimates source and reference stain bases, scales the
    source concentrations to reference percentiles, and reconstructs RGB using
    the reference basis. It must be validated on representative ZN controls
    before use in a reported analysis; Macenko was not originally designed as
    a universal ZN normalization method.
    """

    def __init__(
        self,
        reference_image: Optional[np.ndarray] = None,
        *,
        alpha: float = 1.0,
        beta: float = 0.15,
    ):
        if not 0 < alpha < 50:
            raise ValueError("alpha must be between 0 and 50")
        if beta <= 0:
            raise ValueError("beta must be positive")
        self.alpha = alpha
        self.beta = beta
        self.stain_matrix_target: np.ndarray | None = None
        self.max_concentration_target: np.ndarray | None = None
        if reference_image is not None:
            self.fit(reference_image)

    @staticmethod
    def _validate_rgb(image: np.ndarray) -> np.ndarray:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected an RGB image with shape (height, width, 3).")
        if image.size == 0:
            raise ValueError("Image is empty.")
        return np.asarray(image, dtype=np.float64)

    def _rgb_to_od(self, image: np.ndarray) -> np.ndarray:
        rgb = np.clip(self._validate_rgb(image), 1.0, 255.0)
        return -np.log(rgb / 255.0)

    @staticmethod
    def _od_to_rgb(od: np.ndarray) -> np.ndarray:
        image = 255.0 * np.exp(-np.clip(od, 0.0, 10.0))
        return np.clip(image, 0, 255).astype(np.uint8)

    def _stain_matrix(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        od = self._rgb_to_od(image).reshape((-1, 3))
        tissue_od = od[(od > self.beta).any(axis=1)]
        if tissue_od.shape[0] < 10:
            raise ValueError("Insufficient stained pixels for stain-basis estimation.")

        _, eigenvectors = np.linalg.eigh(np.cov(tissue_od, rowvar=False))
        plane = eigenvectors[:, -2:]
        projections = tissue_od @ plane
        angles = np.arctan2(projections[:, 1], projections[:, 0])
        low = np.percentile(angles, self.alpha)
        high = np.percentile(angles, 100.0 - self.alpha)
        first = plane @ np.array([np.cos(low), np.sin(low)])
        second = plane @ np.array([np.cos(high), np.sin(high)])
        stain_matrix = np.column_stack((first, second))
        stain_matrix /= np.linalg.norm(stain_matrix, axis=0, keepdims=True)

        # Stable ordering: the first vector has the greater red-channel loading.
        if stain_matrix[0, 0] < stain_matrix[0, 1]:
            stain_matrix = stain_matrix[:, ::-1]
        concentrations, *_ = np.linalg.lstsq(stain_matrix, od.T, rcond=None)
        return stain_matrix, concentrations

    def fit(self, image: np.ndarray) -> "MacenkoNormalizer":
        stain_matrix, concentrations = self._stain_matrix(image)
        maxima = np.percentile(concentrations, 99.0, axis=1)
        if np.any(maxima <= 0) or not np.all(np.isfinite(maxima)):
            raise ValueError("Reference stain concentrations are not numerically valid.")
        self.stain_matrix_target = stain_matrix
        self.max_concentration_target = maxima
        return self

    def transform(self, image: np.ndarray) -> np.ndarray:
        if self.stain_matrix_target is None or self.max_concentration_target is None:
            raise RuntimeError("Fit the normalizer on a reference image before transform().")
        source_matrix, concentrations = self._stain_matrix(image)
        del source_matrix  # concentrations already encode the estimated source basis
        source_maxima = np.percentile(concentrations, 99.0, axis=1)
        if np.any(source_maxima <= 0) or not np.all(np.isfinite(source_maxima)):
            raise ValueError("Source stain concentrations are not numerically valid.")
        scaled = concentrations * (
            self.max_concentration_target / source_maxima
        )[:, np.newaxis]
        normalized_od = (self.stain_matrix_target @ scaled).T.reshape(image.shape)
        return self._od_to_rgb(normalized_od)
