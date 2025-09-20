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

echo Starting Flask web server...
python "%ROOT_DIR%app.py"

endlocal