@echo off
cd /d "%~dp0"
python run_rag.py bundle --results results/rag_final15 --output rag_final15_results.zip
pause
