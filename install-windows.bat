@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%app_env"

if not exist "%VENV_DIR%" (
    echo Creating virtual environment in app_env...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo Unable to activate the virtual environment.
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
pip install --upgrade openai-whisper opencv-python numpy flask watchdog tqdm

if errorlevel 1 (
    echo Dependency installation failed.
    exit /b 1
)

echo.
echo Installation complete. Remember to keep FFmpeg available in PATH.
echo.
endlocal