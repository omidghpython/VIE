@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "RAG_PYTHON=python"
if exist "%~dp0.venv_hotpotqa\Scripts\python.exe" set "RAG_PYTHON=%~dp0.venv_hotpotqa\Scripts\python.exe"
if defined HOTPOTQA_PYTHON set "RAG_PYTHON=%HOTPOTQA_PYTHON%"
"%RAG_PYTHON%" tools\prepare_official_final15.py %*
if errorlevel 1 goto failed

pause
exit /b 0
:failed
set "RAG_EXIT=%ERRORLEVEL%"
echo Failed. Preserve this folder and read the error above; no substitute dataset is used.
pause
exit /b %RAG_EXIT%
