@echo off
setlocal
echo =======================================================
echo     TB-AFB RESEARCH ANNOTATION QUEUE
echo =======================================================

echo [System Check] Validating the research environment...
python -c "import torch, ultralytics, fastapi, cv2, pydantic" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Missing Critical ML Dependencies.
    echo Allocating and Installing requirements natively...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Dependency Installation Failed. Check your Python/PIP installation.
        pause
        exit /b 1
    )
    echo [SUCCESS] Tensor Dependencies Installed.
) else (
    echo [OK] Runtime environment verified.
)

if "%TB_AFB_API_TOKEN%"=="" echo [WARNING] TB_AFB_API_TOKEN is not set. Queue submission will remain disabled.
echo Starting the local research API on 127.0.0.1 only...
start "TB_AFB_Research_API" cmd /c "python -m uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001 --no-server-header"

echo Waiting for the local service...
timeout /t 3 >nul

echo Opening the research annotation queue...
start http://127.0.0.1:8001/ui/annotate.html
exit /b 0
