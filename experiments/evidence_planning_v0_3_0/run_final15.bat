@echo off
cd /d "%~dp0"
python run.py verify
if errorlevel 1 goto end
python run.py freeze-final15 --output results\final15_v1
if errorlevel 1 goto end
python run.py run-final15 --output results\final15_v1
:end
pause
