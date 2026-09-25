from typing import Dict, Any


class WHOGrader:
    """Research implementation of conventional AFB smear-count categories.

    The grader does not infer microscopic fields from whole-slide area. Grading is
    only allowed when the caller confirms an appropriate acquisition and sampling
    protocol. The output is not a species identification or a TB diagnosis.
    """

    def calculate_grade(
        self,
        afb_count: int,
        fields_examined: int,
        *,
        magnification: int,
        protocol_confirmed: bool,
    ) -> Dict[str, Any]:
        if afb_count < 0:
            raise ValueError("AFB count cannot be negative.")
        if fields_examined <= 0:
            raise ValueError("fields_examined must be a positive integer.")
        if not protocol_confirmed:
            raise ValueError(
                "Smear grading requires explicit confirmation of the field-sampling protocol."
            )
        if magnification != 1000:
            raise ValueError("This grading implementation requires 1000x oil-immersion fields.")

        afb_per_field = afb_count / fields_examined
        afb_per_100_fields = afb_per_field * 100.0

        if afb_count == 0 and fields_examined >= 100:
            grade = "Negative"
        elif fields_examined >= 100 and afb_count < 10:
            grade = "Scanty"
        elif fields_examined >= 100 and afb_per_100_fields < 100:
            grade = "1+"
        elif fields_examined >= 50 and afb_per_field <= 10:
            grade = "2+"
        elif fields_examined >= 20 and afb_per_field > 10:
            grade = "3+"
        else:
            raise ValueError(
                "Insufficient examined fields for the observed AFB density; "
                "continue the validated microscopy sampling protocol."
            )

        return {
            "grade": grade,
            "afb_count": afb_count,
            "fields_examined": fields_examined,
            "magnification": magnification,
            "protocol_confirmed": protocol_confirmed,
            "afb_per_field": afb_per_field,
            "afb_per_100_fields": afb_per_100_fields,
            "report_string": (
                f"Research AFB category {grade} "
                f"({afb_count} AFB / {fields_examined} fields at {magnification}x)"
            ),
        }
