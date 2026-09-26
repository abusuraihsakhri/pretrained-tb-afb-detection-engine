# TB-AFB Detection Model

[![Research use only](https://img.shields.io/badge/status-research%20use%20only-b45309)](LICENSE)
[![Tests](https://github.com/abusuraihsakhri/pretrained-tb-afb-detection-model/actions/workflows/tests.yml/badge.svg)](https://github.com/abusuraihsakhri/pretrained-tb-afb-detection-model/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/code-Apache--2.0-2563eb)](LICENSE)

[Project site](https://abusuraihsakhri.github.io/pretrained-tb-afb-detection-model/) ·
[Quick start](#quick-start) ·
[Run locally](#local-web-interface)

TB-AFB Detection is a deep-learning object-detection model for locating candidate acid-fast bacilli (AFB) in Ziehl–Neelsen microscopy images. The included single-class Ultralytics YOLOv8n model was trained for 150 epochs on labelled microscopy imagery and returns bounding boxes with confidence scores.

It can analyse standard microscopy images directly and uses tile-based processing for large images and compatible whole-slide imaging workflows.

> **Research use only.** Model output identifies visual AFB candidates; it does not identify *Mycobacterium tuberculosis*, confirm tuberculosis, or replace laboratory or clinical judgement.

## Model at a glance

| Item | Description |
| --- | --- |
| Architecture | Ultralytics YOLOv8n |
| Task | Single-class object detection |
| Target class | Candidate acid-fast bacillus (AFB) |
| Input | Ziehl–Neelsen microscopy images; tiled large-image and WSI workflows |
| Output | Bounding boxes, confidence scores, processing summary |
| Training run | 150 epochs |
| Included checkpoint | `03_MODELS/best.pt` |

### Recorded development outputs

| Metric | Output |
| --- | ---: |
| Precision | 0.7186 |
| Recall | 0.5620 |
| mAP@50 | 0.6406 |
| mAP@50–95 | 0.3119 |

These values describe the recorded development run. They are presented as model-development outputs, not diagnostic or clinical performance claims.

## What is included

- `best.pt` YOLOv8n checkpoint with SHA-256 sidecar file.
- Command-line inference for microscopy raster images and supported large images.
- Tiled whole-slide processing with overlap handling and global non-maximum suppression.
- FastAPI backend and local browser interface for image review.
- Python modules for model loading, tiled inference, post-processing, and optional research reporting.
- Training and data-preparation code for further method development.

## Quick start

Clone the repository and install the dependencies:

```bash
git clone https://github.com/abusuraihsakhri/pretrained-tb-afb-detection-model.git
cd pretrained-tb-afb-detection-model
python -m pip install -r requirements.txt
```

Run the included model on a local microscopy image:

```bash
python 02_CODE/scripts/04_inference.py --model 03_MODELS/best.pt --wsi path/to/microscopy-image.png --conf 0.25
```

The command prints the number of candidate detections, the number of processed tiles, and elapsed processing time.

For a large image or whole-slide workflow, pass the image path through the same `--wsi` option. Supported slide formats require a compatible local OpenSlide installation.

## Local web interface

Start the local API:

```bash
uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001
```

Then open [http://127.0.0.1:8001/ui/](http://127.0.0.1:8001/ui/) in a browser. The interface is intended for local image review and annotation workflows.

## Project structure

```text
02_CODE/
  data.yaml                 # single-class AFB model configuration
  scripts/                  # training and inference entry points
  src/tb_afb/               # detector, image tiling, post-processing, utilities
03_MODELS/
  best.pt                   # included YOLOv8n checkpoint
05_DEPLOYMENT/
  api/                      # FastAPI service and browser interface
docs/                       # GitHub Pages project site
tests/                      # automated tests
```

## Using your own data

The project includes model-development code for labelled microscopy images using the single AFB class defined in `02_CODE/data.yaml`. Keep image and label data outside Git, use compatible YOLO labels, and run training with:

```bash
python 02_CODE/scripts/02_train.py --data data.yaml --epochs 150 --batch 8
```

The repository keeps raw microscopy data and generated research outputs out of version control.

## Limitations

- Candidate AFB detection is not species identification and does not confirm tuberculosis.
- Output can vary with staining, optics, scanner or microscope characteristics, image quality, and specimen preparation.
- Review predictions alongside the original image and the appropriate laboratory workflow.
- Whole-slide processing depends on compatible readers and correct image calibration.

## Technology

Python, PyTorch, Ultralytics YOLO, OpenCV, OpenSlide, NumPy, FastAPI, and a static GitHub Pages site.

## License

Code is available under the [Apache License 2.0](LICENSE).
