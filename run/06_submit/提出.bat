@echo off
cd /d "%~dp0\..\.."

echo.
echo Starting Kaggle submission workflow.
echo.
echo Browser:
echo http://127.0.0.1:8767
echo.

start "" "http://127.0.0.1:8767"
uv run python scripts\submission_workflow_server.py --port 8767

echo.
pause
