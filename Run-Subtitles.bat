@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === Change to your project folder (works even if launched from elsewhere)
cd /d "C:\Users\Khalida\OneDrive\Desktop\AI-clip-creator-main" || (
  echo [ERROR] Project folder not found.
  pause & exit /b 1
)

rem === Use the venv's Python directly (no need to activate)
set PY="C:\Users\Khalida\OneDrive\Desktop\AI-clip-creator-main\app_env\Scripts\python.exe"
if not exist %PY% (
  echo [ERROR] Virtual env Python not found at:
  echo        %PY%
  pause & exit /b 1
)

rem === Ensure Whisper is available in the venv (installs only if missing)
%PY% -m pip show openai-whisper >nul 2>&1 || (
  echo [INFO] Installing Whisper into the virtual environment...
  %PY% -m pip install -U openai-whisper || (
    echo [ERROR] Failed to install Whisper.
    pause & exit /b 1
  )
)

rem === Run the batch subtitle script
echo [INFO] Starting subtitle pipeline...
%PY% batch_subtitle.py
set RC=%ERRORLEVEL%

echo.
if %RC% NEQ 0 (
  echo [ERROR] Pipeline exited with code %RC%.
) else (
  echo [OK] All done.
)

echo.
pause
endlocal
