@echo off
chcp 65001 >nul
call .venv\Scripts\activate.bat
ollama pull qwen3:4b
vn-labor-offline enrich --config config/pipeline.yaml --mode ollama
pause
