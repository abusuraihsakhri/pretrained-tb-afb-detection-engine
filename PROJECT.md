# Project State

## Purpose

Develop a reproducible, local-first research pipeline for candidate AFB object
detection in Ziehl–Neelsen microscopy while preserving biological independence,
data provenance, privacy, and transparent limitations.

## Current status

- Repository software remediation: local pass complete; review/publish pending
- Historical v1.0.0 checkpoint: validation hold
- Historical aggregate dataset: audit failed
- Corrected dataset manifest: provenance review required
- Replacement training: blocked until the strict audit passes
- Locked independent evaluation: not yet performed
- Clinical deployment: unsupported

## Main workflows

1. Inventory and review source provenance.
2. Materialize a group-safe, license-verified dataset.
3. Run the strict integrity audit.
4. Train using development data only.
5. Freeze model and threshold.
6. Evaluate the locked test split once.
7. Publish the model card, dataset card, hashes, uncertainty, and limitations.

## Current priorities

1. Reconstruct upstream class definitions and licenses.
2. Exclude or correct the quarantined `afb-detect` annotations.
3. Assign biological group IDs and a whole-source test holdout.
4. Retrain and conduct independent evaluation.

## Known limitations

See `MODEL_CARD.md` and `DATA_CARD.md`.
