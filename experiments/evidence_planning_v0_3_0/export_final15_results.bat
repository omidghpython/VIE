@echo off
cd /d "%~dp0"
python run.py bundle-final15 --results results\final15_v1 --output final15_results.zip
pause
