@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -m vn_labor_offline.cli load-neo4j --config config/pipeline.yaml
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo ERROR: Neo4j load failed. Review the error above.
pause
exit /b 1
