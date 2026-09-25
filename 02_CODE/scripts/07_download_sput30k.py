#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

def download_id_sput30k():
    print("=======================================================")
    print("      ID-SPUT30K DATASET DOWNLOADER (31,300 Patches)")
    print("=======================================================")
    
    target_dir = Path("01_DATA/raw_academic/ID-SPUT30K")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # The Google Drive Folder ID for ID-SPUT30K
    gdrive_folder_id = "1gpvcFE_GBaNFrtUlz07ec4ButMa59y8T"
    
    print(f"[*] Starting download to {target_dir.resolve()}")
    print("[!] Note: This is an ~11GB dataset with 31,000 files.")
    print("[!] Depending on your internet speed, this will take some time.")
    
    # Run gdown to download the folder securely into the target directory
    try:
        subprocess.run(
            ["gdown", "--folder", gdrive_folder_id, "-O", str(target_dir), "--remaining-ok"], 
            check=True
        )
        print("\n[SUCCESS] ID-SPUT30K Download Complete!")
        print("-> Next step: Run 'python 02_CODE/scripts/06_convert_clinical_labels.py' to process the XML files.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Download interrupted or failed: {e}")
        print("If Google Drive is blocking the download (rate limit), you might need to download it manually via your browser from:")
        print("https://drive.google.com/drive/folders/1gpvcFE_GBaNFrtUlz07ec4ButMa59y8T")

if __name__ == "__main__":
    download_id_sput30k()
