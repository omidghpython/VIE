@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a saved result ZIP onto this BAT file.
  pause
  exit /b 1
)
python run_diagnostic.py "%~1" --output "%~dp0role_identity_report.json"
echo.
pause
