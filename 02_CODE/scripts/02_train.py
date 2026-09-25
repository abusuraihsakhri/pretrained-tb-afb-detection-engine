#!/usr/bin/env python3
"""
Pipeline Trainer Script 
Protected against Command Injection and Directory Traversal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
import os

import yaml

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_pinned_base_checkpoint(project_root: Path) -> tuple[Path, str]:
    """Require and verify the exact pretrained initialization checkpoint."""
    checkpoint = project_root / "yolov8n.pt"
    sidecar = project_root / "yolov8n.pt.sha256"
    if not checkpoint.is_file() or not sidecar.is_file():
        raise FileNotFoundError(
            "Pinned base checkpoint or yolov8n.pt.sha256 is missing; "
            "automatic model downloads are not allowed for a reproducible run."
        )
    parts = sidecar.read_text(encoding="utf-8").split()
    if not parts:
        raise ValueError("yolov8n.pt.sha256 is empty")
    expected = parts[0].lower()
    actual = sha256_file(checkpoint)
    if actual != expected:
        raise ValueError(
            f"Base checkpoint SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return checkpoint, actual


def resolve_dataset_root(yaml_path: Path) -> Path:
    config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "path" not in config:
        raise ValueError("data.yaml must declare a dataset path")
    dataset_root = Path(str(config["path"]))
    if not dataset_root.is_absolute():
        dataset_root = yaml_path.parent / dataset_root
    return dataset_root.resolve()


def require_valid_dataset(dataset_root: Path) -> tuple[Path, str]:
    project_root = Path(__file__).resolve().parents[2]
    audit_script = Path(__file__).with_name("check_data_integrity.py")
    report_path = project_root / "06_LOGS" / "audits" / "pretrain_integrity.json"
    subprocess.run(
        [
            sys.executable,
            str(audit_script),
            "--dataset-root",
            str(dataset_root),
            "--json-report",
            str(report_path),
        ],
        cwd=project_root,
        check=True,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not report.get("passed"):
        raise RuntimeError("Dataset audit did not pass; training is blocked.")
    return report_path, sha256_file(report_path)


def git_commit(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"

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
        print(f"Training configuration: {yaml_path}")

        dataset_root = resolve_dataset_root(yaml_path)
        audit_report, dataset_version = require_valid_dataset(dataset_root)
        print(f"Dataset audit passed: {audit_report}")
        
        project_root = Path(__file__).resolve().parents[2]
        base_checkpoint, base_checkpoint_hash = require_pinned_base_checkpoint(project_root)
        print(f"Pinned base checkpoint verified: {base_checkpoint.name} ({base_checkpoint_hash})")
        audit = AuditLogger(log_dir=Path("06_LOGS/training"), user_id="CLI_AUTO")
        audit.log_training_start(
            config_hash=sha256_file(yaml_path),
            data_version=dataset_version,
            git_commit=git_commit(project_root),
        )
        
        # 🛡️ CLEANUP: Remove old YOLO caches to ensure new public data is indexed
        for cache_file in Path("01_DATA/processed_tiles").rglob("*.cache"):
            try:
                cache_file.unlink()
                print(f"[*] Cleared cache: {cache_file.name}")
            except OSError as exc:
                print(f"[WARN] Could not remove cache {cache_file}: {exc}")

        # 🛡️ VRAM PRE-FLIGHT: Empty GPU cache and log device headroom
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"[*] GPU Active: {gpu_name} ({vram_gb:.2f} GB VRAM)")
            print(f"[*] Memory Guard: expandable_segments=True | AMP=FP16 | batch={args.batch} | cache=False")

        # Build Model 
        detector = YOLOAFBDetector(
            model_size="n", num_classes=1, base_checkpoint=base_checkpoint
        )
        detector.build_model()
        
        # Train securely
        best_pt = detector.train(data_yaml=yaml_path, epochs=args.epochs, batch_size=args.batch)
        print(f"Training completed. Development checkpoint: {best_pt}")

        models_dir = Path("03_MODELS")
        models_dir.mkdir(exist_ok=True)
        if best_pt and Path(best_pt).exists():
            shutil.copy2(best_pt, models_dir / "best.pt")
            checkpoint_hash = sha256_file(models_dir / "best.pt")
            (models_dir / "best.pt.sha256").write_text(
                f"{checkpoint_hash}  best.pt\n", encoding="utf-8"
            )
            print(f"[*] Staged development weights to: {models_dir / 'best.pt'}")

            # Stage plots and evaluation curves
            run_dir = Path(best_pt).parent.parent
            eval_dir = Path("06_LOGS/training/latest")
            eval_dir.mkdir(parents=True, exist_ok=True)
            for fname in ["results.png", "confusion_matrix.png", "confusion_matrix_normalized.png",
                          "BoxPR_curve.png", "BoxF1_curve.png", "BoxP_curve.png",
                          "BoxR_curve.png", "results.csv", "args.yaml"]:
                src_file = run_dir / fname
                if src_file.exists():
                    shutil.copy2(src_file, eval_dir / fname)
            print(f"[*] Staged development curves and run metadata to: {eval_dir}")
        
    except Exception as e:
         print(f"[SECURITY/TRAIN FAILURE]: {e}", file=sys.stderr)
         sys.exit(1)

if __name__ == "__main__":
    main()
