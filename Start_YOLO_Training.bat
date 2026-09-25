@echo off
echo =======================================================
echo     TB-AFB AUDITED DEVELOPMENT TRAINING
echo =======================================================
echo The dataset audit must pass before training can start.

python 02_CODE\scripts\02_train.py --data data.yaml --epochs 150

echo.
echo Development training finished. A locked test evaluation is still required.
pause
