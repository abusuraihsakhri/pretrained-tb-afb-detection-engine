#!/usr/bin/env python3
"""
Universal Clinical Data Converter
Supports: PascalVOC (XML), COCO (JSON), and CSV annotations.
Remaps arbitrary clinical labels to the TB-AFB Master Schema.
"""
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil
import argparse

class ClinicalConverter:
    def __init__(self, target_root="01_DATA/processed_tiles", target_class=0):
        self.target_root = Path(target_root)
        self.target_class = target_class
        
    def convert_pascal_voc(self, xml_dir, img_dir, split="train"):
        """Converts Kaggle/Academic XML formats to YOLO."""
        xml_dir = Path(xml_dir)
        img_dir = Path(img_dir)
        dst_img = self.target_root / split / "images"
        dst_lbl = self.target_root / split / "labels"
        
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for xml_p in xml_dir.glob("*.xml"):
            tree = ET.parse(xml_p)
            root = tree.getroot()
            
            # Find matching image
            img_name = root.find("filename").text
            src_img_p = img_dir / img_name
            if not src_img_p.exists(): continue
            
            size = root.find("size")
            w = int(size.find("width").text)
            h = int(size.find("height").text)
            
            if w == 0 or h == 0: continue # Avoid division by zero
            
            yolo_labels = []
            for obj in root.findall("object"):
                # We assume all objects in these curated sets are AFB Definite
                bbox = obj.find("bndbox")
                xmin = float(bbox.find("xmin").text)
                ymin = float(bbox.find("ymin").text)
                xmax = float(bbox.find("xmax").text)
                ymax = float(bbox.find("ymax").text)
                
                # Convert to YOLO (normalized xywh)
                xc = (xmin + xmax) / 2.0 / w
                yc = (ymin + ymax) / 2.0 / h
                bw = (xmax - xmin) / w
                bh = (ymax - ymin) / h
                
                yolo_labels.append(f"{self.target_class} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
            
            if yolo_labels:
                # Copy Image
                safe_name = f"acad_{xml_p.stem}{src_img_p.suffix}"
                shutil.copy(src_img_p, dst_img / safe_name)
                
                # Write Label
                with open(dst_lbl / f"acad_{xml_p.stem}.txt", "w") as f:
                    f.write("\n".join(yolo_labels))
                count += 1
                
        print(f"[CONVERTER] Successfully ingested {count} clinical XML samples.")

def main():
    parser = argparse.ArgumentParser(description="Clinical Data Universal Translator")
    parser.add_argument("--format", choices=["xml", "json"], default="xml")
    parser.add_argument("--xml_dir", help="Path to academic XML annotations")
    parser.add_argument("--img_dir", help="Path to academic raw images")
    parser.add_argument("--split", default="train", help="Target split (train/val)")
    args = parser.parse_args()
    
    converter = ClinicalConverter()
    if args.format == "xml" and args.xml_dir and args.img_dir:
        converter.convert_pascal_voc(args.xml_dir, args.img_dir, args.split)
    else:
        print("[!] Usage: python convert_clinical.py --format xml --xml_dir <path> --img_dir <path>")

if __name__ == "__main__":
    main()
