# Dataset Card: TB-AFB Working Aggregate

## Status

**Audit failed. The current aggregate is not approved for retraining or reported
evaluation.** Raw and derived images are intentionally excluded from Git.

## Current local inventory

| Split | Images | Label boxes | Empty labels | Annotation violations |
| --- | ---: | ---: | ---: | ---: |
| Train | 13,136 | 59,518 | 7,242 | 12,337 |
| Validation | 952 | 6,280 | 251 | 984 |
| Test | 863 | 4,925 | 267 | 389 |
| Total | 14,951 | 70,723 | 7,760 | 13,710 |

“Annotation violations” counts failed rules and may include more than one rule
for a single box. The machine-readable audit under `06_LOGS/audits/` is the
authoritative local detail.

## Blocking audit findings

- 131 byte-identical image groups cross dataset splits.
- 967 additional exact-duplicate groups exist within training.
- The `afb-detect` source is quarantined: 25,690 of 26,326 boxes cross the
  normalized 0.20 size flag and many extend outside image boundaries.
- Available filenames do not provide a reliable patient/specimen/slide grouping
  key for every source.
- Source licenses and upstream class definitions are not yet fully documented.

## Source registry

The following source identifiers are visible in the local aggregate. Inclusion
does not imply that redistribution, class mapping, independence, or scientific
eligibility has been verified.

| Source identifier | Images | Boxes | Governance status |
| --- | ---: | ---: | --- |
| `tuberculosis-p8whq` | 3,681 | 0 in current converted labels | Class/provenance review required |
| `tuberculosis-czyfb` | 2,787 | 0 in current converted labels | Class/provenance review required |
| `tuberculosis-2` | 2,899 | 28,137 | License and grouping review required |
| `afb-detect` | 2,108 | 26,326 | **Quarantined** |
| `afb-zpazz` | 880 | 1,166 | License and grouping review required |
| `technique-for-detecting-acid-fast-bacilli` | 631 | 1,944 | License and grouping review required |
| `afb-test-y7` | 371 | 1,902 | License and grouping review required |
| `acad_mendeley` | 1,338 | 11,248 | License and grouping review required |
| Academic negative controls | 256 | 0 | License and grouping review required |

The zero converted-box counts are themselves a warning: the current class
mapping or conversion history must be reconstructed from the pinned upstream
versions before those images can be treated as negative fields.

## Required provenance fields

Every image in a corrected manifest should have, where available:

```text
record_id
source_id
source_version
source_url
license_id
original_filename
content_sha256
patient_id_research
specimen_id_research
slide_or_smear_id
field_id
site
scanner_or_microscope
magnification
microns_per_pixel
annotation_version
review_status
split
exclusion_reason
```

Patient and clinical identifiers must be de-identified research IDs. Unknown
fields must remain unknown rather than being inferred from filenames.

## Split policy for the replacement dataset

1. Normalize provenance without modifying raw source files.
2. Exclude quarantined or license-unresolved records.
3. Cluster exact and perceptual duplicates.
4. Group by the highest available biological unit: patient, then specimen,
   smear/slide, original field, and source.
5. Allocate whole groups, never tiles, to a single split.
6. Reserve complete sources/sites for locked testing when scientifically feasible.
7. Tune models and thresholds on training/development validation only.
8. Run the locked test once and preserve the evaluation manifest.

## Validation command

```bash
python 02_CODE/scripts/check_data_integrity.py
```

The training entry point executes the same audit and refuses to start if it
fails.
