@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not defined HF_HOME set "HF_HOME=%~dp0.cache\huggingface"
if not defined EASYOCR_MODULE_PATH set "EASYOCR_MODULE_PATH=%~dp0.cache\easyocr"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -m vn_labor_offline.cli all --config config/pipeline.yaml
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo ERROR: Offline pipeline failed. Check setup and the error above.
pause
exit /b 1
