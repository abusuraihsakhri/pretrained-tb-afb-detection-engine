# TB-AFB Detection Research Pipeline

[![Research use only](https://img.shields.io/badge/status-research%20use%20only-b45309)](MODEL_CARD.md)
[![Tests](https://github.com/abusuraihsakhri/pretrained-tb-afb-detection-model/actions/workflows/tests.yml/badge.svg)](https://github.com/abusuraihsakhri/pretrained-tb-afb-detection-model/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/code-Apache--2.0-2563eb)](LICENSE)

[Project site](https://abusuraihsakhri.github.io/pretrained-tb-afb-detection-model/) ·
[Model card](MODEL_CARD.md) ·
[Dataset card](DATA_CARD.md) ·
[Security](SECURITY.md) ·
[Third-party notices](THIRD_PARTY_NOTICES.md)

> **Research use only — validation hold.** The published v1.0.0 checkpoint was
> trained before an independent audit found exact image leakage across splits and
> a quarantined source with implausible annotations. Do not use this checkpoint
> for diagnosis, patient management, smear grading, or reported performance
> comparisons. A corrected checkpoint has not yet been trained.

This repository is a local-first research pipeline for detecting candidate
acid-fast bacilli (AFB) in Ziehl–Neelsen microscopy images. It includes strict
dataset validation, YOLO development training, tiled raster/WSI inference,
global non-maximum suppression, a review queue, and a FastAPI research UI.

AFB appearance is **not species-specific**. A detection must not be described as
identification of *Mycobacterium tuberculosis* or as confirmation of tuberculosis.

## Current evidence status

The repository contains a historical 150-epoch YOLOv8n checkpoint. Its final
development-validation outputs were approximately:

| Development metric | Historical value | Current interpretation |
| --- | ---: | --- |
| Precision | 0.7186 | Not an independent test estimate |
| Recall | 0.5620 | Not an independent test estimate |
| mAP@50 | 0.6406 | Invalid for clinical/generalization claims |
| mAP@50–95 | 0.3119 | Invalid for clinical/generalization claims |

These values are retained only for provenance. They must not be called
“accuracy,” “clinical validation,” “cross-validation,” or performance on an
unseen cohort.

### Audit findings blocking retraining

The strict audit of the current 14,951-image working dataset found:

| Finding | Count |
| --- | ---: |
| Label boxes across all splits | 70,723 |
| Empty label files across all splits | 7,760 |
| Exact duplicate image groups crossing splits | 131 |
| Annotation violations reported | 13,710 |
| `afb-detect` boxes crossing the large-box flag | 25,690 / 26,326 |

The source `afb-detect` is quarantined by default. Training is intentionally
blocked until the audit passes.

## Reproducible workflow

### 1. Create an environment

Python 3.12 is used in CI. The pinned runtime file preserves the historical
software snapshot; package upgrades require a compatibility evaluation.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Audit the dataset

```bash
python 02_CODE/scripts/check_data_integrity.py
```

The command checks all splits, image decoding, image/label symmetry, box
validity, class IDs, source-level box distributions, quarantined sources, and
exact duplicate leakage. It writes a machine-readable report under
`06_LOGS/audits/` and exits non-zero when the dataset is unsuitable.

### 3. Train only after the audit passes

```bash
python 02_CODE/scripts/02_train.py --data data.yaml --epochs 150 --batch 16
```

Training records the configuration, dataset-audit, Git commit, and checkpoint
hashes. The pretrained initialization is pinned by `yolov8n.pt.sha256`; training
refuses an absent or altered base checkpoint instead of silently downloading a
different artifact. It uses development validation only and does not evaluate
the test split.

### 4. Evaluate the locked test set once

After the dataset, model, and operating threshold are frozen:

```bash
python 02_CODE/scripts/03_evaluate_locked.py \
  --model 03_MODELS/best.pt \
  --data 02_CODE/data.yaml \
  --split test \
  --acknowledge-test-lock
```

### 5. Run research inference

```bash
python 02_CODE/scripts/04_inference.py \
  --model 03_MODELS/best.pt \
  --wsi path/to/research-image.png \
  --conf 0.25
```

Morphology filtering is disabled by default. It may be explored only with a
known calibration:

```bash
python 02_CODE/scripts/04_inference.py \
  --model 03_MODELS/best.pt \
  --wsi path/to/research-image.png \
  --microns-per-pixel 0.25 \
  --morphology-filter
```

Smear-category output additionally requires an explicit 1000× sampling-protocol
confirmation. It remains research output, not a diagnosis.

## Local API and review UI

Start the API locally:

```bash
uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001
```

Then open `http://127.0.0.1:8001/ui/`.

Data-changing endpoints are disabled until `TB_AFB_API_TOKEN` is set. Submitted
annotations enter `01_DATA/review_queue/`; they are not assigned randomly to
training or validation. A curator must attach specimen/slide provenance and
assign a group-safe split.

For the container workflow, create a local `.env` containing a strong token and
the expected model checksum. Docker Compose binds only to `127.0.0.1` and uses
the reproducible CPU runtime by default. Configure and validate a separate
hardware-specific image before enabling GPU acceleration.

## Repository structure

```text
01_DATA/                 Local, ignored source and derived data
02_CODE/scripts/         Audit, ingestion, training, evaluation, inference
02_CODE/src/tb_afb/      Reusable model and inference modules
03_MODELS/               Pinned checkpoint and SHA-256 sidecar
05_DEPLOYMENT/           Local FastAPI application and review UI
06_LOGS/                 Ignored audit, training, and evaluation records
docs/                    GitHub Pages research status site
tests/                   Unit and validation tests
```

## Scientific limitations

- The current checkpoint has not passed independent evaluation.
- The available filenames do not establish patient- or specimen-level
  independence for every source.
- Source licenses and upstream class definitions require a completed provenance
  review before redistribution or retraining.
- AFB microscopy does not identify a mycobacterial species.
- Performance across laboratories, scanners, stains, populations, and low-load
  specimens is unknown.
- No prospective, external-site, workflow, reader, calibration, fairness, or
  clinical-impact study has been completed.

See [MODEL_CARD.md](MODEL_CARD.md) and [DATA_CARD.md](DATA_CARD.md) for the
release and data-governance status.

## License

Repository code is provided under Apache License 2.0. Model, dependency, and
dataset licenses must be reviewed separately; the repository license does not
replace third-party terms.
