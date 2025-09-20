@echo off
echo ================================
echo  Activating Virtual Environment
echo ================================
call app_env\Scripts\activate.bat

echo ================================
echo  Upgrading pip
echo ================================
python -m pip install --upgrade pip

echo ================================
echo  Installing Core Dependencies
echo ================================
python -m pip install numpy opencv-python mediapipe

echo ================================
echo  Installing Whisper + Torch
echo ================================
python -m pip install openai-whisper
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo ================================
echo  Installing FFmpeg (via pip wrapper)
echo ================================
python -m pip install ffmpeg-python

echo.
echo ✅ All dependencies installed successfully!
pause
