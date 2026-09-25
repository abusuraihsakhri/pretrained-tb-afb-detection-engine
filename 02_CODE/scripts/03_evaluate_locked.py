#!/usr/bin/env python3
"""Evaluate a frozen checkpoint after the dataset audit passes.

The test split is never evaluated by the training script. Running it requires
an explicit acknowledgement so threshold/model selection remains confined to
development data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

from check_data_integrity import audit_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_root_from_yaml(path: Path) -> Path:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = Path(str(config["path"]))
    return (path.parent / root).resolve() if not root.is_absolute() else root.resolve()


def current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument(
        "--acknowledge-test-lock",
        action="store_true",
        help="Confirm that model and thresholds were locked before test evaluation.",
    )
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_path = args.model.expanduser().resolve()
    data_yaml = args.data.expanduser().resolve()
    if not model_path.is_file() or not data_yaml.is_file():
        raise SystemExit("Model checkpoint and data YAML must both exist.")
    if args.split == "test" and not args.acknowledge_test_lock:
        raise SystemExit(
            "Test evaluation is locked. Finalize the model and operating threshold, "
            "then rerun with --acknowledge-test-lock."
        )

    dataset_root = dataset_root_from_yaml(data_yaml)
    audit = audit_dataset(dataset_root)
    if not audit.passed:
        raise SystemExit(
            "Dataset audit failed. Correct leakage and annotation errors before evaluation."
        )

    from ultralytics import YOLO

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = f"{args.split}_{timestamp}"
    model = YOLO(str(model_path))
    metrics = model.val(
        data=str(data_yaml),
        split=args.split,
        device=args.device,
        project=str(PROJECT_ROOT / "06_LOGS" / "evaluation"),
        name=run_name,
        plots=True,
    )
    results = {
        key: float(value) if hasattr(value, "__float__") else str(value)
        for key, value in metrics.results_dict.items()
    }
    manifest = {
        "status": "research_evaluation",
        "split": args.split,
        "evaluated_at_utc": timestamp,
        "checkpoint": str(model_path),
        "checkpoint_sha256": sha256_file(model_path),
        "data_yaml_sha256": sha256_file(data_yaml),
        "dataset_root": str(dataset_root),
        "git_commit": current_commit(),
        "dataset_audit": audit.to_dict(),
        "metrics": results,
    }
    output_dir = PROJECT_ROOT / "06_LOGS" / "evaluation" / run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evaluation_manifest.json"
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Evaluation manifest: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
