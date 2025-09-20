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

echo Running dynamic crop pipeline...
python "%ROOT_DIR%tools\dynamic_crop.py"
if errorlevel 1 (
    echo Dynamic crop step failed.
)

echo Generating subtitles...
python "%ROOT_DIR%batch_subtitle.py" --archive
if errorlevel 1 (
    echo Subtitle pipeline encountered errors.
)

echo Starting Flask web app...
python "%ROOT_DIR%app.py"

endlocal