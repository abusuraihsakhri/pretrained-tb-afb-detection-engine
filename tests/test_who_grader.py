from pathlib import Path
import importlib.util

MODULE = Path(__file__).parents[1] / "02_CODE/src/tb_afb/inference/who_grader.py"
spec = importlib.util.spec_from_file_location("who_grader", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
WHOGrader = module.WHOGrader


def test_grading_boundaries():
    g = WHOGrader()
    assert g.calculate_grade(0, 100)["grade"] == "Negative"
    assert g.calculate_grade(1, 100)["grade"] == "Scanty"
    assert g.calculate_grade(9, 100)["grade"] == "Scanty"
    assert g.calculate_grade(10, 100)["grade"] == "1+"
    assert g.calculate_grade(99, 100)["grade"] == "1+"
    assert g.calculate_grade(100, 100)["grade"] == "2+"
    assert g.calculate_grade(1001, 100)["grade"] == "3+"


def test_invalid_fields_rejected():
    g = WHOGrader()
    try:
        g.calculate_grade(1, 0)
    except ValueError:
        return
    raise AssertionError("zero fields must be rejected")
