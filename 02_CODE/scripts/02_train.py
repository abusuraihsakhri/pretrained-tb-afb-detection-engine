#!/usr/bin/env python3
"""
Pipeline Trainer Script 
Protected against Command Injection and Directory Traversal.
"""
import argparse
from pathlib import Path
import sys
import shutil
import os

# 🛡️ 6GB VRAM SAFETY: Prevent CUDA memory fragmentation over long multi-epoch runs
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Ensure local packages are resolvable
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import torch
from tb_afb.models.yolo_detector import YOLOAFBDetector
from tb_afb.utils.logger import AuditLogger
from tb_afb.utils.safety import check_disk_space

def secure_yaml_resolution(base_dir: Path, yaml_path: str) -> Path:
    """Blocks directory traversal patterns for YAML payloads."""
    base_dir = base_dir.resolve()
    requested_path = (base_dir / yaml_path).resolve()
    
    # 🛡️ SECURITY REMEDIATION: Strict relative path verification prevents sibling prefix bypass
    try:
        if not requested_path.is_relative_to(base_dir):
            raise PermissionError("Path traversal pattern matching denied for YAML configs.")
    except AttributeError:
        if os.path.commonpath([str(requested_path), str(base_dir)]) != str(base_dir):
            raise PermissionError("Path traversal pattern matching denied for YAML configs.")
            
    if not requested_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {requested_path}")
    return requested_path

def main():
    parser = argparse.ArgumentParser(description="Secure YOLO Training Orchestrator")
    parser.add_argument("--data", required=True, type=str, help="Path to data.yaml")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()
    
    # 🛡️ SAFETY CHECK: Ensure we don't crash the OS during massive ingestion
    if not check_disk_space(min_gb=10.0):
        sys.exit(1)

    safe_root = Path("02_CODE").resolve()
    
    try:
        yaml_path = secure_yaml_resolution(safe_root, args.data)
        print(f"Executing secure training isolated to: {yaml_path}")
        
        # Initialize Logger securely
        audit = AuditLogger(log_dir=Path("06_LOGS/training"), user_id="CLI_AUTO")
        audit.log_training_start(config_hash="TESTING_HASH", data_version="V1", git_commit="N/A")
        
        # 🛡️ CLEANUP: Remove old YOLO caches to ensure new public data is indexed
        for cache_file in Path("01_DATA/processed_tiles").rglob("*.cache"):
            try:
                cache_file.unlink()
                print(f"[*] Cleared cache: {cache_file.name}")
            except: pass

        # 🛡️ VRAM PRE-FLIGHT: Empty GPU cache and log device headroom
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"[*] GPU Active: {gpu_name} ({vram_gb:.2f} GB VRAM)")
            print(f"[*] Memory Guard: expandable_segments=True | AMP=FP16 | batch={args.batch} | cache=False")

        # Build Model 
        detector = YOLOAFBDetector(model_size="n", num_classes=1)
        detector.build_model()
        
        # Train securely
        best_pt = detector.train(data_yaml=yaml_path, epochs=args.epochs, batch_size=args.batch)
        print(f"Training successfully completed. Best checkpoint: {best_pt}")

        models_dir = Path("03_MODELS")
        models_dir.mkdir(exist_ok=True)
        if best_pt and Path(best_pt).exists():
            shutil.copy2(best_pt, models_dir / "best.pt")
            shutil.copy2(best_pt, Path("best.pt"))
            print(f"[*] Staged fine-tuned weights to: {models_dir / 'best.pt'} and root best.pt")

            # Stage plots and evaluation curves
            run_dir = Path(best_pt).parent.parent
            eval_dir = Path("06_LOGS/training/latest")
            eval_dir.mkdir(parents=True, exist_ok=True)
            for fname in ["results.png", "confusion_matrix.png", "confusion_matrix_normalized.png", 
                          "PR_curve.png", "F1_curve.png", "results.csv"]:
                src_file = run_dir / fname
                if src_file.exists():
                    shutil.copy2(src_file, eval_dir / fname)
            print(f"[*] Staged evaluation curves and confusion matrix to: {eval_dir}")
        
    except Exception as e:
         print(f"[SECURITY/TRAIN FAILURE]: {e}", file=sys.stderr)
         sys.exit(1)

if __name__ == "__main__":
    main()
