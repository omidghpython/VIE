@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
python run.py verify
if errorlevel 1 exit /b 1
python run_rag.py verify
if errorlevel 1 exit /b 1
python -m unittest discover -s tests -v
pause
