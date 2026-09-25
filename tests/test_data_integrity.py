import importlib.util
import sys
from pathlib import Path


MODULE = Path(__file__).parents[1] / "02_CODE/scripts/check_data_integrity.py"
SPEC = importlib.util.spec_from_file_location("check_data_integrity", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def make_dataset(root: Path) -> None:
    for split in ("train", "val", "test"):
        (root / split / "images").mkdir(parents=True)
        (root / split / "labels").mkdir(parents=True)
        stem = f"safe_{split}"
        (root / split / "images" / f"{stem}.png").write_bytes(split.encode())
        (root / split / "labels" / f"{stem}.txt").write_text(
            "0 0.5 0.5 0.1 0.1\n", encoding="utf-8"
        )


def test_valid_dataset_passes(tmp_path):
    make_dataset(tmp_path)
    report = AUDIT.audit_dataset(
        tmp_path, decode_images=False, quarantined_sources=set()
    )
    assert report.passed
    assert report.total_images == 3
    assert report.total_boxes == 3


def test_cross_split_duplicate_fails(tmp_path):
    make_dataset(tmp_path)
    duplicate = b"same-image"
    (tmp_path / "train/images/safe_train.png").write_bytes(duplicate)
    (tmp_path / "test/images/safe_test.png").write_bytes(duplicate)
    report = AUDIT.audit_dataset(
        tmp_path, decode_images=False, quarantined_sources=set()
    )
    assert not report.passed
    assert len(report.cross_split_duplicate_groups) == 1


def test_zero_width_box_fails(tmp_path):
    make_dataset(tmp_path)
    (tmp_path / "val/labels/safe_val.txt").write_text(
        "0 0.5 0.5 0 0.1\n", encoding="utf-8"
    )
    report = AUDIT.audit_dataset(
        tmp_path, decode_images=False, quarantined_sources=set()
    )
    assert not report.passed
    assert report.splits["val"]["invalid_annotations"] > 0


def test_quarantined_source_fails(tmp_path):
    make_dataset(tmp_path)
    old_image = tmp_path / "train/images/safe_train.png"
    old_label = tmp_path / "train/labels/safe_train.txt"
    old_image.rename(tmp_path / "train/images/pub_afb-detect_example.png")
    old_label.rename(tmp_path / "train/labels/pub_afb-detect_example.txt")
    report = AUDIT.audit_dataset(tmp_path, decode_images=False)
    assert not report.passed
    assert any("quarantined sources" in error for error in report.errors)
