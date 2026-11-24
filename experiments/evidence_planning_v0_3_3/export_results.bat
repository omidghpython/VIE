@echo off
cd /d "%~dp0"
python run.py bundle-results --results results\development_v1 --output evidence_planning_results.zip
pause
