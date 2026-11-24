@echo off
cd /d "%~dp0"
python run.py export-review --results results\final15_v1\decisions --output review\final15_v1
pause
