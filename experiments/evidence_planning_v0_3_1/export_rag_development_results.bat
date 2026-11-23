@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "RAG_PYTHON=python"
if exist "%~dp0.venv_hotpotqa\Scripts\python.exe" set "RAG_PYTHON=%~dp0.venv_hotpotqa\Scripts\python.exe"
"%RAG_PYTHON%" run_rag.py bundle --results results/rag_development_v031 --output rag_development_v031_results.zip
pause
