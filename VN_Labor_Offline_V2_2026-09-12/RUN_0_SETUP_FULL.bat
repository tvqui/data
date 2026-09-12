@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".python312\python.exe" (
  ".python312\python.exe" -m venv .venv
) else (
  py -3.12 -m venv .venv
)
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -U pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -e ".[full]"
if errorlevel 1 goto failed
echo Full setup complete.
pause
exit /b 0
:failed
echo ERROR: Full setup failed. Review the error above.
pause
exit /b 1
