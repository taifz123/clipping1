@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === Change to your project folder
cd /d "C:\Users\Khalida\OneDrive\Desktop\AI-clip-creator-main" || (
  echo [ERROR] Project folder not found.
  pause & exit /b 1
)

rem === Path to your venv’s Python
set PY="C:\Users\Khalida\OneDrive\Desktop\AI-clip-creator-main\app_env\Scripts\python.exe"
if not exist %PY% (
  echo [ERROR] Virtual env Python not found:
  echo        %PY%
  pause & exit /b 1
)

rem === Start the web app
echo [INFO] Launching the AI Clip Creator web app...
start "" %PY% main.py

rem === Give the server a few seconds to start
timeout /t 5 >nul

rem === Auto-open browser (default browser)
start http://127.0.0.1:5000

echo.
echo [OK] Web app started. Your browser should open automatically.
echo.
pause
endlocal
