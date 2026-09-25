@echo off
echo =======================================================
echo     TB-AFB RESEARCH WSI TILE EXTRACTOR
echo =======================================================
echo.
set /p wsi_path="Enter the absolute path to a de-identified research WSI: "

echo.
echo Starting local tile extraction...
echo.

python 02_CODE\scripts\01_extract_tiles.py --wsi "%wsi_path%"

echo.
echo Extraction finished.
echo Research tiles were written to 01_DATA\raw_tiles\.
pause
