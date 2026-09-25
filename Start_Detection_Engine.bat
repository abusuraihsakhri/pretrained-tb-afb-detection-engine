@echo off
setlocal
echo =======================================================
echo     TB-AFB RESEARCH INFERENCE
echo =======================================================

echo [System Check] Validating the research environment...
python -c "import torch, ultralytics, fastapi, cv2, pydantic" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Missing runtime dependencies.
    echo Installing the pinned historical runtime snapshot...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Dependency Installation Failed. Check your Python/PIP installation.
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies Installed.
) else (
    echo [OK] Runtime environment verified.
)

echo Starting the local research API on 127.0.0.1 only...
start "TB_AFB_Research_API" cmd /c "python -m uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001 --no-server-header"

echo Waiting for the local service...
timeout /t 3 >nul

echo Opening the research interface...
start http://127.0.0.1:8001/ui/
exit /b 0
