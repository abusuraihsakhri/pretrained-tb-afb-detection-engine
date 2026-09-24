from pathlib import Path
from typing import Any, Dict, List

import torch


class YOLOAFBDetector:
    """Single-class YOLOv8 AFB detector."""

    def __init__(self, model_size: str = "n", num_classes: int = 1, pretrained: bool = True):
        self.model_size = model_size
        self.num_classes = num_classes
        self.pretrained = pretrained
        self.model = None

    def build_model(self) -> Any:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Ultralytics is not installed.") from exc

        if self.model_size not in {"n", "s", "m", "l", "x"}:
            raise ValueError(f"Invalid model size: {self.model_size}")
        self.model = YOLO(f"yolov8{self.model_size}.pt")
        return self.model

    def load_checkpoint(self, checkpoint: Path) -> Any:
        from ultralytics import YOLO

        checkpoint = Path(checkpoint).resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
        self.model = YOLO(str(checkpoint))
        return self.model

    def train(self, data_yaml: Path, epochs: int = 100, batch_size: int = 8,
              device: str | None = None, **kwargs) -> Path:
        if device is None:
            if torch.cuda.is_available():
                device = "0"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        data_yaml = Path(data_yaml).resolve()
        if not data_yaml.is_file():
            raise FileNotFoundError("Data YAML missing.")
        if self.model is None:
            raise RuntimeError("Model has not been built.")

        results = self.model.train(
            data=str(data_yaml),
            epochs=int(epochs),
            batch=int(batch_size),
            workers=0,
            device=device,
            imgsz=640,
            amp=device != "cpu",
            degrees=15.0,
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            flipud=0.5,
            fliplr=0.5,
            mosaic=1.0,
            patience=50,
            seed=42,
            deterministic=True,
            **kwargs,
        )
        save_dir = Path(results.save_dir)
        return save_dir / "weights" / "best.pt"

    def predict(self, image, conf_threshold: float = 0.25,
                iou_threshold: float = 0.45, max_det: int = 300) -> List[Dict]:
        if self.model is None:
            raise RuntimeError("No trained model is loaded.")
        if image.size > 50_000_000:
            raise ValueError("Input image exceeds the inference size limit.")

        conf = max(0.01, min(1.0, float(conf_threshold)))
        iou = max(0.01, min(1.0, float(iou_threshold)))
        max_det = max(1, min(5000, int(max_det)))

        detections = []
        for result in self.model(image, conf=conf, iou=iou, max_det=max_det, verbose=False):
            if result.boxes is None:
                continue
            for box in result.boxes:
                detections.append({
                    "bbox": box.xywh[0].tolist(),
                    "confidence": float(box.conf[0]),
                    "class_id": int(box.cls[0]),
                })
        return detections
