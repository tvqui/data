@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
docker compose up -d neo4j
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo ERROR: Neo4j startup failed. Review the error above.
pause
exit /b 1
