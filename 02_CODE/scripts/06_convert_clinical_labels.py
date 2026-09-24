#!/usr/bin/env python3
"""Convert Pascal VOC AFB annotations to a single-class YOLO dataset."""
import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


class ClinicalConverter:
    def __init__(self, target_root="01_DATA/processed_tiles", afb_names=None):
        self.target_root = Path(target_root)
        self.afb_names = {x.lower() for x in (afb_names or {"afb", "bacillus", "acid-fast bacillus"})}

    def convert_pascal_voc(self, xml_dir, img_dir, split="train"):
        if split not in {"train", "val", "test"}:
            raise ValueError("split must be train, val, or test")
        xml_dir, img_dir = Path(xml_dir), Path(img_dir)
        dst_img = self.target_root / split / "images"
        dst_lbl = self.target_root / split / "labels"
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)

        count = 0
        for xml_path in xml_dir.glob("*.xml"):
            root = ET.parse(xml_path).getroot()
            filename = root.findtext("filename")
            if not filename:
                continue
            src = img_dir / filename
            if not src.is_file():
                continue
            size = root.find("size")
            width, height = int(size.findtext("width", "0")), int(size.findtext("height", "0"))
            if width <= 0 or height <= 0:
                continue

            labels = []
            for obj in root.findall("object"):
                name = (obj.findtext("name") or "").strip().lower()
                if name not in self.afb_names:
                    continue
                box = obj.find("bndbox")
                xmin, ymin = float(box.findtext("xmin")), float(box.findtext("ymin"))
                xmax, ymax = float(box.findtext("xmax")), float(box.findtext("ymax"))
                if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
                    continue
                xc, yc = (xmin + xmax) / (2 * width), (ymin + ymax) / (2 * height)
                bw, bh = (xmax - xmin) / width, (ymax - ymin) / height
                labels.append(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

            stem = f"acad_{xml_path.stem}"
            shutil.copy2(src, dst_img / f"{stem}{src.suffix.lower()}")
            (dst_lbl / f"{stem}.txt").write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
            count += 1
        print(f"Converted {count} images, including valid negative fields.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml-dir", required=True)
    parser.add_argument("--img-dir", required=True)
    parser.add_argument("--split", choices=["train", "val", "test"], default="train")
    parser.add_argument("--afb-name", action="append", dest="afb_names")
    args = parser.parse_args()
    ClinicalConverter(afb_names=args.afb_names).convert_pascal_voc(args.xml_dir, args.img_dir, args.split)


if __name__ == "__main__":
    main()
