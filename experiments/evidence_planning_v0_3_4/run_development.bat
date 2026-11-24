@echo off
cd /d "%~dp0"
python run.py verify
if errorlevel 1 goto end
python run.py run --output results\development_v1 --max-new-calls 20
if errorlevel 1 goto end
python run.py report --results results\development_v1
:end
pause
