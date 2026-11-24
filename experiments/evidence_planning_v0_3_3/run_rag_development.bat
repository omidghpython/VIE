@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "RAG_PYTHON=python"
if exist "%~dp0.venv_hotpotqa\Scripts\python.exe" set "RAG_PYTHON=%~dp0.venv_hotpotqa\Scripts\python.exe"
"%RAG_PYTHON%" run_rag.py verify
if errorlevel 1 goto failed
"%RAG_PYTHON%" run_rag.py run --config configs/rag_development.json --output results/rag_development_v033
if errorlevel 1 goto failed
echo.
echo Run returned. Inspect the saved statuses and report; answers are not automatically correct.
echo Results: results\rag_development_v033
echo Console log: results\rag_development_v033\console.log
pause
exit /b 0
:failed
set "RAG_EXIT=%ERRORLEVEL%"
echo Run incomplete. Read the error above; saved records are preserved.
pause
exit /b %RAG_EXIT%
