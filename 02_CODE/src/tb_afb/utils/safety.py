import shutil
from pathlib import Path
import sys

def check_disk_space(path=".", min_gb=5.0):
    """
    🛡️ SAFETY CONTROL: Prevents Disk-Full crashes during massive clinical training runs.
    """
    total, used, free = shutil.disk_usage(path)
    free_gb = free / (2**30)
    
    if free_gb < min_gb:
        print(f"\n[🚨 DISK CRITICAL]: Only {free_gb:.2f} GB remaining on disk.")
        print(f"Neural Engine paused to prevent data corruption. Clear space and restart.")
        return False
    
    print(f"[✅ DISK SAFE]: {free_gb:.2f} GB free.")
    return True
