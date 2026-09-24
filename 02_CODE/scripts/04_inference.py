#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir.parent / "src"))

from tb_afb.inference.sliding_window import SlidingWindowInference
from tb_afb.inference.who_grader import WHOGrader
from tb_afb.models.yolo_detector import YOLOAFBDetector


def resolve_existing_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def main():
    parser = argparse.ArgumentParser(description="TB-AFB research inference")
    parser.add_argument("--model", required=True, help="Trained AFB best.pt checkpoint")
    parser.add_argument("--wsi", required=True, help="Slide or microscopy image")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--fields-examined", type=int, default=None,
                        help="Optional observed field count; required for smear grading")
    args = parser.parse_args()

    detector = YOLOAFBDetector()
    detector.load_checkpoint(resolve_existing_path(args.model))
    engine = SlidingWindowInference(detector, confidence_threshold=args.conf)
    result = engine.process_slide(resolve_existing_path(args.wsi))

    print(f"Detections: {result['total_detections']}")
    print(f"Tiles processed: {result['tiles_processed']}")
    print(f"Processing time: {result['processing_time']:.2f} s")

    if args.fields_examined is not None:
        report = WHOGrader().calculate_grade(result["total_detections"], args.fields_examined)
        print(f"Research smear grade: {report['report_string']}")
    else:
        print("Smear grade: not calculated (provide --fields-examined).")


if __name__ == "__main__":
    main()
