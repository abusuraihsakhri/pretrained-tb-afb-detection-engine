#!/usr/bin/env python3
"""
Public Dataset Ingestion Pipeline
Downloads AFB datasets from Roboflow and remaps labels to the 5-class clinical schema.
"""
import os
import shutil
import argparse
from pathlib import Path
from roboflow import Roboflow

import os
import shutil
import argparse
import yaml
from pathlib import Path
from roboflow import Roboflow

# 🛡️ GLOBAL TB INTELLIGENCE MAPPING
# All known public AFB labels are mapped to our Class 0 (AFB_Definite)
# Our Schema: 0: AFB_Definite, 1: AFB_Probable, 2: AFB_Possible, 3: Debris, 4: RBC
TARGET_CLASS = 0

DATASETS = [
    {"workspace": "harshita-hhmns", "project": "afb-u0hdn", "version": 1},
    {"workspace": "swu-5alfk", "project": "tuberculosis-p8whq", "version": 1},
    {"workspace": "swu-5alfk", "project": "tuberculosis-czyfb", "version": 3},
    {"workspace": "huzaifa-athar", "project": "afb-zpazz", "version": 1},
    {"workspace": "naresuan-university-1yqlq", "project": "technique-for-detecting-acid-fast-bacilli", "version": 15}
]

def map_labels(lbl_p, dst_p, mapping_dict):
    """Remaps labels from local project index to global TB-AFB index."""
    if not lbl_p.exists(): return
    
    with open(lbl_p, "r") as f:
        lines = f.readlines()
    
    with open(dst_p, "w") as f:
        for line in lines:
            parts = line.strip().split()
            if not parts: continue
            
            orig_cls = int(parts[0])
            # Default to TARGET_CLASS (0) as these are all curated AFB datasets
            new_cls = TARGET_CLASS 
            
            f.write(f"{new_cls} {' '.join(parts[1:])}\n")

def ingest_roboflow_dataset(api_key, workspace, project, version, target_root):
    rf = Roboflow(api_key=api_key)
    project_obj = rf.workspace(workspace).project(project)
    
    # Download in YOLOv8 format
    print(f"\n[*] Downloading {project} (v{version})...")
    dataset = project_obj.version(version).download("yolov8")
    
    source_path = Path(dataset.location)
    target_root = Path(target_root)
    
    count = 0
    for split in ['train', 'valid', 'test']:
        # Clinical hygiene split: map 'valid'/'test' to 'val' to keep it simple for YOLO
        target_split = 'val' if split in ['valid', 'test'] else split
        
        src_img_dir = source_path / split / "images"
        src_lbl_dir = source_path / split / "labels"
        
        dst_img_dir = target_root / target_split / "images"
        dst_lbl_dir = target_root / target_split / "labels"
        
        dst_img_dir.mkdir(parents=True, exist_ok=True)
        dst_lbl_dir.mkdir(parents=True, exist_ok=True)
        
        if not src_img_dir.exists(): continue
            
        img_files = list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.png")) + list(src_img_dir.glob("*.jpeg"))
        
        for img_p in img_files:
            lbl_p = src_lbl_dir / f"{img_p.stem}.txt"
            
            # Anti-collision naming
            safe_name = f"pub_{project}_{img_p.name}"
            safe_lbl_name = f"pub_{project}_{img_p.stem}.txt"
            
            # Copy Image
            shutil.copy(img_p, dst_img_dir / safe_name)
            
            # Process and Copy Label
            map_labels(lbl_p, dst_lbl_dir / safe_lbl_name, {})
            count += 1

    print(f"[SUCCESS] Ingested {count} arrays from {project}")
    # Cleanup downloaded raw folder to save space
    shutil.rmtree(source_path)

def get_api_key(cmd_arg):
    if cmd_arg:
        return cmd_arg
        
    env_p = Path(".env")
    if env_p.exists():
        with open(env_p, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ROBOFLOW_API_KEY="):
                    return line.split("=")[1].strip()
    return None

def main():
    parser = argparse.ArgumentParser(description="🚀 ULTIMATE TB-AFB DATA INGESTER")
    parser.add_argument("--key", help="Roboflow API Key (Optional if .env exists)")
    args = parser.parse_args()
    
    api_key = get_api_key(args.key)
    if not api_key:
        print("[🚨 ERROR] Roboflow API Key not found. Please paste it into the .env file.")
        return

    target_data_dir = Path("01_DATA/processed_tiles")
    
    print("="*60)
    print("      TB-AFB PUBLIC DATASET AGGREGATION PIPELINE")
    print("="*60)
    
    for ds in DATASETS:
        try:
            ingest_roboflow_dataset(
                api_key=api_key,
                workspace=ds['workspace'],
                project=ds['project'],
                version=ds['version'],
                target_root=target_data_dir
            )
        except Exception as e:
            print(f"[ERROR] Skipping {ds['project']}: {e}")

    print("\n" + "="*60)
    print("   INGESTION COMPLETE. RUN Start_YOLO_Training.bat TO BEGIN.")
    print("="*60)

if __name__ == "__main__":
    main()
