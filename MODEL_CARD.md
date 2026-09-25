# Model Card: TB-AFB YOLOv8n Research Checkpoint

## Release status

**Validation hold. Not for clinical use.**

The `v1.0.0`/`03_MODELS/best.pt` checkpoint predates the repository’s strict
dataset audit. It must not be used for diagnostic claims or comparative model
reporting because exact duplicate leakage and a quarantined annotation source
were identified after training.

| Field | Value |
| --- | --- |
| Architecture | Ultralytics YOLOv8n, single detection class |
| Target label | Candidate acid-fast bacillus (AFB) appearance |
| Input | Research microscopy raster tiles; experimental WSI tiling |
| Checkpoint SHA-256 | `24d9cc9be1500124c6b8b511fcc4481ce3a10d8b470f7c770609ffe879d76b98` |
| Release | Historical v1.0.0 checkpoint |
| Current decision | Do not use; retrain after a passing dataset audit |

## Intended use

- Reproducing and auditing the historical development pipeline
- Software development for tiled microscopy inference
- Designing a scientifically valid replacement dataset and evaluation
- Qualitative research exploration on non-clinical, de-identified images

## Prohibited or unsupported use

- Diagnosing or excluding tuberculosis
- Identifying *Mycobacterium tuberculosis* at species level
- Issuing a clinical smear grade without a separately validated protocol
- Patient triage, treatment, infection-control, or public-health decisions
- Autonomous reporting or replacement of qualified laboratory personnel
- Claims of prospective, external, multicenter, or clinical validation

## Training and evaluation status

The checkpoint was trained for 150 epochs on the earlier aggregate split. Its
last development-validation outputs were precision 0.7186, recall 0.5620,
mAP@50 0.6406, and mAP@50–95 0.3119. These are retained for provenance only.

They are not valid independent performance estimates because:

1. 131 exact image groups cross train/validation/test.
2. The `afb-detect` source has predominantly implausible large boxes and is now
   quarantined.
3. The reported values came from validation observed during model development.
4. No locked test, external-site, reader, workflow, calibration, or prospective
   study is documented.

## Thresholds and post-processing

The historical confidence threshold was 0.25. It has not been clinically
selected or locked. Morphology filtering is now disabled by default and requires
explicit microns-per-pixel calibration when explored. Threshold selection for a
replacement model must use development data only.

## Known failure modes

- Stain precipitate, debris, scratches, and elongated background structures
- Very low bacillary burden
- Unseen laboratories, scanners, optics, acquisition devices, and stain protocols
- Incorrect or absent pixel calibration
- Tiled boundary effects and dense overlapping detections
- Nontuberculous acid-fast organisms, which microscopy cannot identify as MTB
- Dataset or annotation shift caused by inconsistent upstream class definitions

## Required validation before a new release

- Verified source licenses and class definitions
- Patient/specimen/slide grouping wherever metadata permits
- Exact and perceptual deduplication before splitting
- Entire-source or entire-site held-out testing
- Locked checkpoint and operating threshold
- Confidence intervals clustered at the appropriate biological unit
- Source/site and low-load subgroup results
- Calibration and error analysis when probabilistic output is claimed
- Independent pathological/laboratory review and prospective workflow evaluation

## Ethical and privacy considerations

Do not commit patient data, slide identifiers, or raw clinical images. Evaluate
site, device, and population performance separately before any broader claim.
Model output must remain reviewable and must not obscure uncertainty or failure
modes.
