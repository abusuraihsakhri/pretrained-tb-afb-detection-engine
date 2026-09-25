#!/usr/bin/env python3
"""
Master Orchestrator Pipeline
============================
    Automates data ingestion, strict validation, cache cleanup, and development training.
"""
import os
import sys
import time
import subprocess
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "02_CODE" / "scripts"
RAW_ACADEMIC_DIR = BASE_DIR / "01_DATA" / "raw_academic"
PROCESSED_TILES_DIR = BASE_DIR / "01_DATA" / "processed_tiles"

def log_step(msg):
    print("\n" + "="*70)
    print(f"🚀 {msg}")
    print("="*70)

def clear_cache_and_memory():
    """Aggressively purges YOLO caches and python GC to free memory and disk space."""
    print("[*] Performing deep cache sweep...")
    for cache_file in PROCESSED_TILES_DIR.rglob("*.cache"):
        try:
            cache_file.unlink()
            print(f"    - Purged: {cache_file.name}")
        except Exception as e:
            pass
            
    # Force OS to flush file system buffers (simulated via gc for python scopes)
    import gc
    gc.collect()

def run_with_retry(cmd_list, max_retries=3, cwd=str(BASE_DIR)):
    """Runs a subprocess command with exponential backoff on failure."""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] Executing: {' '.join(cmd_list)}")
            result = subprocess.run(cmd_list, cwd=cwd, check=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"[🚨 ERROR] Command failed with exit code: {e.returncode}")
            if attempt < max_retries:
                wait_time = 5 * attempt
                print(f"[*] Retrying in {wait_time} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print(f"[FATAL] Max retries reached for: {' '.join(cmd_list)}. Halting pipeline.")
                return False
        except Exception as e:
            print(f"[FATAL] Unexpected crash: {e}")
            return False

def check_disk_space(min_gb=15.0):
    """Fails fast if disk space is dangerously low."""
    total, used, free = shutil.disk_usage(BASE_DIR)
    free_gb = free / (2**30)
    if free_gb < min_gb:
        print(f"[FATAL] Disk space critically low ({free_gb:.2f} GB). Need at least {min_gb} GB.")
        return False
    return True

def auto_pipeline():
    # 1. System Check
    log_step("SYSTEM AND DISK HEALTH CHECK")
    if not check_disk_space(min_gb=10.0):
        sys.exit(1)
        
    clear_cache_and_memory()

    # 2. Public Roboflow Ingestion (Optional Check)
    log_step("CHECKING PUBLIC DATA (ROBOFLOW)")
    
    train_images_dir = PROCESSED_TILES_DIR / "train" / "images"
    existing_images = len(list(train_images_dir.glob("*.jpg"))) if train_images_dir.exists() else 0
    
    env_file = BASE_DIR / ".env"
    if existing_images > 4000:
        print(f"[*] Detected {existing_images} research images. Skipping redundant download.")
    elif env_file.exists():
        print("[*] Environment variables detected. Running public ingestion sync...")
        run_with_retry(["python", str(SCRIPTS_DIR / "05_ingest_public_data.py")], max_retries=2)
    else:
        print("[*] No .env file. Skipping Roboflow public datasets.")
        
    clear_cache_and_memory()

    # [REMOVED ID-SPUT30K PHASE DUE TO GATED ACADEMIC ANNOTATIONS]

    clear_cache_and_memory()

    # 4. Development training. The training entry point blocks on audit failure.
    log_step("INITIATING AUDITED DEVELOPMENT TRAINING")
    print("[*] Starting the YOLO development run.")
    
    # We run the train script locally so we don't rely on cmd.exe's batch context
    success = run_with_retry([
        "python", str(SCRIPTS_DIR / "02_train.py"),
        "--data", "data.yaml", 
        "--epochs", "150"
    ], max_retries=3)
    
    if success:
        log_step("DEVELOPMENT TRAINING COMPLETE. LOCKED TEST EVALUATION IS STILL REQUIRED.")
    else:
        print("\n[FATAL] Pipeline failed during PyTorch optimization.")
        sys.exit(1)

if __name__ == "__main__":
    auto_pipeline()
