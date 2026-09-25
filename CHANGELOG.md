# Changelog

## Unreleased

### Scientific validity

- Added strict all-split dataset auditing, exact duplicate detection, source
  distributions, image decoding, and YOLO box-bound checks.
- Quarantined `afb-detect` by default.
- Made public-label conversion fail on malformed or polygon-like annotations
  instead of silently truncating them.
- Blocked training and locked-test evaluation when the dataset audit fails.
- Reclassified v1.0.0 metrics as historical development outputs.

### Inference and safety

- Added real raster tiling and explicit WSI/raster routing.
- Made morphology filtering opt-in and calibration-dependent.
- Corrected continuous-coordinate NMS area calculations.
- Required sampling-protocol confirmation for research smear categories.
- Added checkpoint SHA-256 verification.

### API and deployment

- Disabled mutation endpoints unless an API token is configured.
- Replaced random train/validation assignment with a provenance review queue.
- Added upload pixel limits, stricter annotation schemas, a bounded WSI cache,
  research-only reports, and an opt-in remote-training gate.
- Hardened Docker with a non-root user, localhost host binding, health check,
  read-only runtime, dropped capabilities, and `.dockerignore` protection.

### Documentation and web

- Corrected the renamed repository and Pages URLs.
- Replaced unsupported clinical claims with a validation-hold notice.
- Added model, dataset, security, and reproducibility documentation.

## 1.0.0

- Historical initial checkpoint and development site.
- Superseded for performance claims after the post-release data audit.
