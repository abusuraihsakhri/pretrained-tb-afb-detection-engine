import sys
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")
SRC = Path(__file__).parents[1] / "02_CODE/src"
sys.path.insert(0, str(SRC))

from tb_afb.models.loss_functions import CIOULoss, FocalLoss


def test_ciou_is_zero_for_identical_boxes():
    boxes = torch.tensor([[0.5, 0.5, 0.2, 0.1]], dtype=torch.float32)
    loss = CIOULoss()(boxes, boxes)
    assert float(loss) == pytest.approx(0.0, abs=1e-5)


def test_ciou_penalizes_shifted_boxes():
    predicted = torch.tensor([[0.2, 0.2, 0.2, 0.1]], dtype=torch.float32)
    target = torch.tensor([[0.8, 0.8, 0.2, 0.1]], dtype=torch.float32)
    assert float(CIOULoss()(predicted, target)) > 1.0


def test_focal_loss_preserves_shape_without_reduction():
    inputs = torch.tensor([0.0, 0.0], dtype=torch.float32)
    targets = torch.tensor([0.0, 1.0], dtype=torch.float32)
    result = FocalLoss(reduction="none")(inputs, targets)
    assert result.shape == inputs.shape
    assert torch.all(result >= 0)
