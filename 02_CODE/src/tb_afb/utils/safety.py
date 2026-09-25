import shutil
from pathlib import Path
import sys

def check_disk_space(path=".", min_gb=5.0):
    """Prevent a development run from starting with insufficient disk space."""
    total, used, free = shutil.disk_usage(path)
    free_gb = free / (2**30)
    
    if free_gb < min_gb:
        print(f"\n[DISK CRITICAL]: Only {free_gb:.2f} GB remaining on disk.")
        print("Training stopped to avoid incomplete artifacts. Clear space and retry.")
        return False
    
    print(f"[DISK CHECK]: {free_gb:.2f} GB free.")
    return True
