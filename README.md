# TB-AFB Detection Research Pipeline

### [Open the Project Site →](https://abusuraihsakhri.github.io/pretrained-tb-afb-detection-engine/)

A research codebase for detecting acid-fast bacilli (AFB) in Ziehl-Neelsen microscopy images using YOLO-based object detection, tiled inference, and expert annotation workflows.

> **Research use only.** This repository is not a validated diagnostic medical device. A trained AFB checkpoint is intentionally not bundled at present; model weights and reproducible evaluation artifacts will be added separately.

## Current status

The repository contains the training, data-conversion, inference, annotation, and API infrastructure. The pipeline has been revised so that missing or unreadable model/image inputs fail explicitly rather than producing a negative result.

Previously published performance figures have been removed because the corresponding trained checkpoint, frozen split manifest, and evaluation outputs are not currently committed. Performance will be reported again when those artifacts can be released together.

## What is implemented

- Single-class AFB object-detection configuration.
- YOLOv8 training with a deterministic seed.
- Raster microscopy inference with overlapping tiles and global NMS.
- OpenSlide-based WSI tiling and CLI inference.
- Pascal VOC to YOLO conversion that retains valid negative images.
- Public-data ingestion that preserves train/validation/test partitions.
- Explicit source-class mapping requirement for third-party datasets.
- Expert annotation endpoints for building additional training data.
- Optional smear grading only when an explicit number of examined fields is supplied.
- FastAPI backend and local browser UI.
- Static GitHub Pages project site in `docs/`.

## Repository layout

```text
02_CODE/
  data.yaml                 # single-class dataset configuration
  scripts/                  # ingestion, conversion, training and inference
  src/tb_afb/               # detector, WSI, post-processing and grading modules
05_DEPLOYMENT/api/          # FastAPI backend and local UI
docs/                       # static GitHub Pages project site
tests/                      # lightweight regression tests
```

## Data and reproducibility

Raw images, processed datasets, generated weights, and logs are excluded from Git. This protects local data and avoids presenting untracked binaries as reproducible research artifacts.

For third-party public datasets, verify the pinned dataset version and its class names before entering `afb_class_ids` in `02_CODE/scripts/05_ingest_public_data.py`. The importer will refuse to run a source whose AFB class mapping has not been verified.

Do not merge source test data into validation data. For microscopy datasets derived from slides, prefer patient/slide-level partitioning so correlated patches from the same specimen cannot cross evaluation partitions.

## Training

Install the Python dependencies in an isolated environment, prepare `01_DATA/processed_tiles/{train,val,test}/{images,labels}`, then run:

```bash
python 02_CODE/scripts/02_train.py --data data.yaml --epochs 150 --batch 8
```

The training wrapper uses a deterministic seed. The resulting `best.pt` is generated under the Ultralytics run directory and is intentionally ignored by Git until a validated release checkpoint is supplied.

## Inference

After placing a trained AFB checkpoint on the machine:

```bash
python 02_CODE/scripts/04_inference.py \
  --model /path/to/best.pt \
  --wsi /path/to/image-or-slide.svs \
  --conf 0.25
```

To calculate a research smear grade, the acquisition protocol must provide the number of examined microscopic fields:

```bash
python 02_CODE/scripts/04_inference.py \
  --model /path/to/best.pt \
  --wsi /path/to/image.svs \
  --fields-examined 100
```

The API's `/api/v1/analyze` endpoint accepts ordinary raster microscopy images. Proprietary WSI formats are handled by the OpenSlide/CLI workflow rather than being passed to OpenCV.

## Local API

```bash
uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001
```

The backend returns HTTP 503 when no trained AFB checkpoint is available. It does not substitute a color-threshold heuristic for the trained model.

## Evaluation artifacts to add with the trained weights

When the trained checkpoint is supplied, the repository should add a model card and frozen evaluation bundle containing:

- checkpoint identity/hash and training configuration;
- exact dataset versions and licenses;
- slide/patient-level split manifest;
- random seed and software versions;
- object-level precision, recall, F1, AP50 and AP50-95;
- false positives per image/field;
- PR curves, confusion matrix and representative error analysis;
- independent test-set results kept separate from validation;
- documented decision threshold.

No performance number should be presented as verified without those corresponding artifacts.

## Privacy and clinical use

Do not commit patient slides, identifiers, annotations containing protected information, local logs, API keys, or environment files. The project is intended for research and method development. Clinical use requires appropriate validation, governance, regulatory review, and local quality assurance.

## Technology

Python, PyTorch, Ultralytics YOLO, OpenCV, OpenSlide, NumPy, FastAPI and a static HTML/CSS/JavaScript project site.

## License

Apache License 2.0. See `LICENSE`.
