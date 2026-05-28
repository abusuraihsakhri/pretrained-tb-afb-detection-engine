@echo off
echo =======================================================
echo     TB PATHOLOGY INTELLIGENCE - DEEP LEARNING ENGINE
echo =======================================================
echo Injecting Annotated Arrays into YOLOv8 PyTorch Backend...
echo 🛡️ 6GB VRAM Optimization Mode [ENGAGED: Auto-Batch & AMP]

python 02_CODE\scripts\02_train.py --data data.yaml --epochs 150

echo.
echo Training Event Complete. Check runs\detect\train\weights for new best.pt.
pause
