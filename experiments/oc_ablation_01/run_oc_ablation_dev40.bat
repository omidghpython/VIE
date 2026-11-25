@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY=python"
if exist ".venv_hotpotqa\Scripts\python.exe" set "PY=.venv_hotpotqa\Scripts\python.exe"
if defined HOTPOTQA_PYTHON set "PY=%HOTPOTQA_PYTHON%"
"%PY%" run_pair.py run
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
