@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist "%~dp0.venv_hotpotqa\Scripts\activate.bat" (
  echo Run restore_environment_windows.bat first.
  pause
  exit /b 1
)
call "%~dp0.venv_hotpotqa\Scripts\activate.bat"
if errorlevel 1 exit /b 1
cmd /k
