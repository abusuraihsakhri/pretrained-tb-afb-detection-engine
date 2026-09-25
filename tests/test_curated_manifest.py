import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parents[1] / "02_CODE/scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE = SCRIPTS / "prepare_curated_dataset.py"
SPEC = importlib.util.spec_from_file_location("prepare_curated_dataset", MODULE)
CURATE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CURATE
SPEC.loader.exec_module(CURATE)


def make_rows(root: Path):
    rows = []
    for split in ("train", "val", "test"):
        image_dir = root / split / "images"
        label_dir = root / split / "labels"
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        image = image_dir / f"{split}_record.png"
        label = label_dir / f"{split}_record.txt"
        image.write_bytes(split.encode())
        label.write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
        rows.append(
            {
                "record_id": image.stem,
                "source_id": split,
                "source_version": "1",
                "original_split": split,
                "image_path": str(image.relative_to(root)),
                "label_path": str(label.relative_to(root)),
                "content_sha256": CURATE.sha256_file(image),
                "biological_group_id": f"group-{split}",
                "target_split": split,
                "license_id": "CC-BY-4.0",
                "provenance_status": "verified",
                "include": "true",
                "exclusion_reason": "",
            }
        )
    return rows


def test_manifest_requires_held_out_source(tmp_path):
    rows = make_rows(tmp_path)
    with pytest.raises(ValueError, match="test-source"):
        CURATE.validate_manifest(rows, tmp_path, set())


def test_manifest_accepts_group_safe_source_holdout(tmp_path):
    rows = make_rows(tmp_path)
    included = CURATE.validate_manifest(rows, tmp_path, {"test"})
    assert len(included) == 3


def test_manifest_rejects_group_crossing_splits(tmp_path):
    rows = make_rows(tmp_path)
    rows[0]["biological_group_id"] = "same-person"
    rows[1]["biological_group_id"] = "same-person"
    with pytest.raises(ValueError, match="Biological groups cross splits"):
        CURATE.validate_manifest(rows, tmp_path, {"test"})
