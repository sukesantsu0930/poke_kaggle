@echo off
cd /d "%~dp0\.."

echo Starting replay JSON / official visualizer workflow.
echo.
echo Browser:
echo http://127.0.0.1:8766

start "" "http://127.0.0.1:8766"
python scripts\visualizer_workflow_server.py --port 8766

echo.
pause
