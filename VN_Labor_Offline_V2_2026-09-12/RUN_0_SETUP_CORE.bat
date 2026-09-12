@echo off
chcp 65001 >nul
py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U pip
pip install -e .
echo Core setup complete.
pause
