@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set HF_HUB_DISABLE_XET=1
set "HF_HOME=%~dp0.cache\huggingface"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" scripts\prepare_dense_model.py
if errorlevel 1 goto failed
set HF_HUB_OFFLINE=1
".venv\Scripts\python.exe" -m vn_labor_offline.cli dense --config config/pipeline.yaml
if errorlevel 1 goto failed
echo Dense rebuild and technical validation complete.
pause
exit /b 0
:failed
echo ERROR: Dense rebuild failed. Review the error above.
pause
exit /b 1
