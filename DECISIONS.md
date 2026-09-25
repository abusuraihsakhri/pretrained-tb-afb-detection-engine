# Decisions

## 2026-09-25 — Place v1.0.0 on validation hold

**Decision:** Preserve the historical checkpoint for provenance but remove
clinical-readiness and independent-validation claims.

**Reason:** The strict audit found 131 exact duplicate groups crossing splits
and a high-volume source with implausible annotations.

## 2026-09-25 — Block training on audit failure

**Decision:** The training entry point must run the all-split dataset audit and
exit non-zero on leakage, invalid boxes, missing files, or quarantined sources.

**Reason:** A successful optimizer run is not useful when the underlying data
violates the evaluation design.

## 2026-09-25 — Require explicit biological grouping

**Decision:** Do not generate a corrected random split automatically. Require a
reviewed manifest with biological group IDs, verified license/provenance, and at
least one declared whole-source test holdout.

**Reason:** Filenames alone cannot establish patient, specimen, or slide
independence.

## 2026-09-25 — Disable clinical and regulated-use claims

**Decision:** Describe the system as research software and the output as
candidate detections.

**Reason:** AFB microscopy is not species-specific, and no prospective,
external, workflow, or regulatory validation has been completed.

## 2026-09-25 — Keep the service local by default

**Decision:** Bind Docker to localhost, require a token for mutations, and make
remote training a separate opt-in control.

**Reason:** The application handles potentially sensitive research images and
is not designed as a hardened public service.
