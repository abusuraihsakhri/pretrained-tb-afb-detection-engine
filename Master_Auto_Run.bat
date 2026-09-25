@echo off
color 0A
echo ====================================================================
echo       TB PATHOLOGY INTELLIGENCE - MASTER AUTO-ORCHESTRATOR
echo ====================================================================
echo.
echo [*] Initializing complete end-to-end pipeline...
echo [*] Features active: Disk Protection, VRAM Auto-Scaling, Memory GC
echo.

python 02_CODE\scripts\00_master_auto_run.py

echo.
echo ====================================================================
echo                   PIPELINE EXECUTION FINISHED
echo ====================================================================
pause
