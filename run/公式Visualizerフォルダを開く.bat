@echo off
cd /d "%~dp0\.."

echo Official Visualizer notebook is prepared locally.
echo.
echo Local loader:
echo notebooks\official_visualizer\visualizer.html
echo.
echo Replay JSON created by this project:
echo experiments\visualizer\latest_replay.json
echo.

start "" "notebooks\official_visualizer\visualizer.html"
explorer "experiments\visualizer"

echo.
echo Choose latest_replay.json in the browser.

pause
