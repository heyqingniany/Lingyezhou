@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm packaging\lingyezhou.spec
if errorlevel 1 exit /b 1
echo Build complete: dist\Lingyezhou\Lingyezhou.exe
echo Distribute the entire Lingyezhou folder. Model weights are downloaded separately.
