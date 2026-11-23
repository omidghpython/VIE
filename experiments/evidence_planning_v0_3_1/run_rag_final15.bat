@echo off
cd /d "%~dp0"
python run_rag.py verify
if errorlevel 1 exit /b 1
python run_rag.py run --config configs/rag_final15.json --output results/rag_final15
if errorlevel 1 exit /b 1
python run_rag.py report --results results/rag_final15
pause
