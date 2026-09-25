@echo off
color 0A
echo ====================================================================
echo       TB-AFB RESEARCH PIPELINE
echo ====================================================================
echo.
echo [*] Initializing complete end-to-end pipeline...
echo [*] Strict data validation is required before development training.
echo.

python 02_CODE\scripts\00_master_auto_run.py

echo.
echo ====================================================================
echo                   PIPELINE EXECUTION FINISHED
echo ====================================================================
pause
