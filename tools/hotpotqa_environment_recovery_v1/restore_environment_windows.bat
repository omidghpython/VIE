@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
py -3.13 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if not errorlevel 1 (
  set "HOTPOT_BOOTSTRAP=py -3.13"
  goto bootstrap_ready
)
py -3.12 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if not errorlevel 1 (
  set "HOTPOT_BOOTSTRAP=py -3.12"
  goto bootstrap_ready
)
py -3.11 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if not errorlevel 1 (
  set "HOTPOT_BOOTSTRAP=py -3.11"
  goto bootstrap_ready
)
py -3.10 -c "import struct; assert struct.calcsize('P')==8" >nul 2>&1
if not errorlevel 1 (
  set "HOTPOT_BOOTSTRAP=py -3.10"
  goto bootstrap_ready
)
python -c "import sys,struct; assert (3,10) <= sys.version_info[:2] <= (3,13) and struct.calcsize('P')==8" >nul 2>&1
if errorlevel 1 (
  echo Install 64-bit Python 3.13 from python.org first, then rerun this file.
  pause
  exit /b 1
)
set "HOTPOT_BOOTSTRAP=python"
:bootstrap_ready
%HOTPOT_BOOTSTRAP% "%~dp0restore_environment.py" --project "%~dp0." %*
set "HOTPOT_RESTORE_EXIT=%ERRORLEVEL%"
if not "%HOTPOT_RESTORE_EXIT%"=="0" echo Setup did not complete. Read the error above; no experiment was started.
pause
exit /b %HOTPOT_RESTORE_EXIT%
