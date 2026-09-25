from pathlib import Path
import importlib.util

MODULE = Path(__file__).parents[1] / "02_CODE/src/tb_afb/inference/who_grader.py"
spec = importlib.util.spec_from_file_location("who_grader", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
WHOGrader = module.WHOGrader


def test_grading_boundaries():
    g = WHOGrader()
    kwargs = {"magnification": 1000, "protocol_confirmed": True}
    assert g.calculate_grade(0, 100, **kwargs)["grade"] == "Negative"
    assert g.calculate_grade(1, 100, **kwargs)["grade"] == "Scanty"
    assert g.calculate_grade(9, 100, **kwargs)["grade"] == "Scanty"
    assert g.calculate_grade(10, 100, **kwargs)["grade"] == "1+"
    assert g.calculate_grade(99, 100, **kwargs)["grade"] == "1+"
    assert g.calculate_grade(100, 100, **kwargs)["grade"] == "2+"
    assert g.calculate_grade(1001, 100, **kwargs)["grade"] == "3+"


def test_invalid_fields_rejected():
    g = WHOGrader()
    try:
        g.calculate_grade(1, 0, magnification=1000, protocol_confirmed=True)
    except ValueError:
        return
    raise AssertionError("zero fields must be rejected")


def test_protocol_confirmation_is_required():
    g = WHOGrader()
    try:
        g.calculate_grade(1, 100, magnification=1000, protocol_confirmed=False)
    except ValueError:
        return
    raise AssertionError("grading without protocol confirmation must be rejected")


def test_insufficient_fields_are_rejected():
    g = WHOGrader()
    try:
        g.calculate_grade(5, 20, magnification=1000, protocol_confirmed=True)
    except ValueError:
        return
    raise AssertionError("low-density grading requires the full field count")
