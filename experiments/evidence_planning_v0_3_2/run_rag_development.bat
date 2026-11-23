@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "RAG_PYTHON=python"
if exist "%~dp0.venv_hotpotqa\Scripts\python.exe" set "RAG_PYTHON=%~dp0.venv_hotpotqa\Scripts\python.exe"
"%RAG_PYTHON%" run_rag.py verify
if errorlevel 1 exit /b 1
"%RAG_PYTHON%" run_rag.py run --config configs/rag_development.json --output results/rag_development_v032
if errorlevel 1 exit /b 1
"%RAG_PYTHON%" run_rag.py report --results results/rag_development_v032
pause
