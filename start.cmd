@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Runtime not found. Run setup.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo Startup failed. Check logs\lingyezhou.log for details.
    pause
    exit /b 1
)
