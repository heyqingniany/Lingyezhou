@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -c requirements-windows.lock.txt --index-url https://pypi.org/simple
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" scripts\check_runtime.py
if errorlevel 1 goto :failed
echo Setup complete. Double-click start.cmd to launch.
pause
exit /b 0
:failed
echo Setup failed. Review the error above.
pause
exit /b 1
