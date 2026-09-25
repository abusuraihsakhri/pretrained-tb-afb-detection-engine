# Contributing

Contributions are welcome when they preserve scientific validity, data privacy,
and reproducibility.

## Before opening a change

- Do not add raw clinical data, patient identifiers, credentials, or private
  dataset links.
- Do not alter raw data in place.
- Document source, version, license, class definitions, and exclusion decisions.
- Keep patient/specimen/slide groups within one dataset split.
- Do not add clinical claims without traceable evidence.

## Local checks

```bash
python -m pytest -q
python -m compileall -q 02_CODE 05_DEPLOYMENT tests
python 02_CODE/scripts/check_data_integrity.py
```

The final command is expected to fail against the historical aggregate until
the corrected dataset is built. Do not bypass it for a reported training run.

## Pull requests

Describe:

1. The scientific or software problem being addressed.
2. Files and behavior changed.
3. Tests and validation executed.
4. Data-provenance, privacy, or licensing effects.
5. Limitations and anything not verified.

Changes to metrics or model claims must include the evaluation manifest and the
locked dataset/model hashes that generated them.
