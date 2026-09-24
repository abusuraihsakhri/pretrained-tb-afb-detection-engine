from typing import Dict, Any


class WHOGrader:
    """AFB smear grading from observed bacilli and explicitly examined fields.

    The grader does not infer microscopic fields from whole-slide area. Grading is
    only meaningful when the acquisition/sampling protocol supplies the number of
    examined fields.
    """

    def calculate_grade(self, afb_count: int, fields_examined: int) -> Dict[str, Any]:
        if afb_count < 0:
            raise ValueError("AFB count cannot be negative.")
        if fields_examined <= 0:
            raise ValueError("fields_examined must be a positive integer.")

        afb_per_field = afb_count / fields_examined
        afb_per_100_fields = afb_per_field * 100.0

        if afb_count == 0:
            grade = "Negative"
        elif fields_examined >= 100 and afb_count < 10:
            grade = "Scanty"
        elif afb_per_100_fields < 100:
            grade = "1+"
        elif afb_per_field <= 10:
            grade = "2+"
        else:
            grade = "3+"

        return {
            "grade": grade,
            "afb_count": afb_count,
            "fields_examined": fields_examined,
            "afb_per_field": afb_per_field,
            "afb_per_100_fields": afb_per_100_fields,
            "report_string": f"{grade} ({afb_count} AFB / {fields_examined} fields)",
        }
