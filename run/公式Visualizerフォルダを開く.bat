@echo off
cd /d "%~dp0\.."

echo Official Visualizer notebook is prepared locally.
echo.
echo Folder:
echo notebooks\official_visualizer
echo.
echo Replay JSON created by this project:
echo experiments\visualizer\latest_replay.json
echo.

explorer "notebooks\official_visualizer"

echo The official Kaggle page will also be opened.
start "" "https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view"

pause
