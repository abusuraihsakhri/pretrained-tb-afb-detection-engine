import importlib.util
from pathlib import Path

import pytest


MODULE = Path(__file__).parents[1] / "02_CODE/scripts/05_ingest_public_data.py"
SPEC = importlib.util.spec_from_file_location("ingest_public_data", MODULE)
INGEST = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INGEST)


def test_remap_label_keeps_only_declared_afb_classes(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text(
        "0 0.5 0.5 0.1 0.1\n2 0.4 0.4 0.1 0.1\n",
        encoding="utf-8",
    )
    INGEST.remap_label(source, destination, {0})
    assert destination.read_text(encoding="utf-8") == "0 0.5 0.5 0.1 0.1\n"


def test_remap_label_rejects_polygon_truncation(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text(
        "0 0.1 0.1 0.9 0.1 0.9 0.9 0.1 0.9\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="expected YOLO detection format"):
        INGEST.remap_label(source, destination, {0})


def test_remap_label_rejects_out_of_bounds_box(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("0 0.95 0.5 0.2 0.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside image bounds"):
        INGEST.remap_label(source, destination, {0})
