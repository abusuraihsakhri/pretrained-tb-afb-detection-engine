from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as functional


class FocalLoss(nn.Module):
    """Binary focal loss with class-balanced alpha weighting."""

    def __init__(
        self, alpha: float = 0.25, gamma: float = 2.0, reduction: str = "mean"
    ):
        super().__init__()
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between 0 and 1")
        if gamma < 0:
            raise ValueError("gamma must be non-negative")
        if reduction not in {"none", "mean", "sum"}:
            raise ValueError("reduction must be none, mean, or sum")
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        if inputs.shape != targets.shape:
            raise ValueError("inputs and targets must have the same shape")
        targets = targets.to(dtype=inputs.dtype)
        binary_cross_entropy = functional.binary_cross_entropy_with_logits(
            inputs, targets, reduction="none"
        )
        probability_true_class = torch.exp(-binary_cross_entropy)
        alpha_weight = self.alpha * targets + (1.0 - self.alpha) * (1.0 - targets)
        loss = (
            alpha_weight
            * (1.0 - probability_true_class).pow(self.gamma)
            * binary_cross_entropy
        )
        if self.reduction == "mean":
            return loss.mean()
        if self.reduction == "sum":
            return loss.sum()
        return loss


class CIOULoss(nn.Module):
    """Complete-IoU loss for boxes represented as center-x, center-y, width, height."""

    def __init__(self, reduction: str = "mean", epsilon: float = 1e-7):
        super().__init__()
        if reduction not in {"none", "mean", "sum"}:
            raise ValueError("reduction must be none, mean, or sum")
        self.reduction = reduction
        self.epsilon = epsilon

    @staticmethod
    def _to_corners(boxes: torch.Tensor) -> tuple[torch.Tensor, ...]:
        center_x, center_y, width, height = boxes.unbind(dim=-1)
        return (
            center_x - width / 2,
            center_y - height / 2,
            center_x + width / 2,
            center_y + height / 2,
        )

    def forward(self, predicted: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        if predicted.shape != target.shape or predicted.shape[-1] != 4:
            raise ValueError("predicted and target must have matching (..., 4) shapes")
        if torch.any(predicted[..., 2:] <= 0) or torch.any(target[..., 2:] <= 0):
            raise ValueError("box width and height must be positive")

        px1, py1, px2, py2 = self._to_corners(predicted)
        tx1, ty1, tx2, ty2 = self._to_corners(target)
        intersection_width = (torch.minimum(px2, tx2) - torch.maximum(px1, tx1)).clamp(min=0)
        intersection_height = (torch.minimum(py2, ty2) - torch.maximum(py1, ty1)).clamp(min=0)
        intersection = intersection_width * intersection_height
        predicted_area = (px2 - px1) * (py2 - py1)
        target_area = (tx2 - tx1) * (ty2 - ty1)
        union = predicted_area + target_area - intersection
        iou = intersection / (union + self.epsilon)

        center_distance = (
            (predicted[..., 0] - target[..., 0]).pow(2)
            + (predicted[..., 1] - target[..., 1]).pow(2)
        )
        enclosing_width = torch.maximum(px2, tx2) - torch.minimum(px1, tx1)
        enclosing_height = torch.maximum(py2, ty2) - torch.minimum(py1, ty1)
        enclosing_diagonal = enclosing_width.pow(2) + enclosing_height.pow(2)
        aspect_penalty = (4.0 / math.pi**2) * (
            torch.atan(target[..., 2] / target[..., 3])
            - torch.atan(predicted[..., 2] / predicted[..., 3])
        ).pow(2)
        with torch.no_grad():
            alpha = aspect_penalty / (1.0 - iou + aspect_penalty + self.epsilon)
        ciou = iou - center_distance / (enclosing_diagonal + self.epsilon) - alpha * aspect_penalty
        loss = 1.0 - ciou
        if self.reduction == "mean":
            return loss.mean()
        if self.reduction == "sum":
            return loss.sum()
        return loss
