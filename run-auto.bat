@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%app_env"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo Virtual environment not found. Run install-windows.bat first.
    exit /b 1
)

echo Launching auto pipeline watcher...
start "Clip Watcher" cmd /k python "%ROOT_DIR%tools\auto_pipeline.py"

echo Launching web dashboard...
start "AI Clip Creator" cmd /k python "%ROOT_DIR%app.py"

endlocal