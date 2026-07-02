@echo off
cd /d "%~dp0\.."

echo.
echo Creating a local replay JSON for the official Kaggle Visualiser.
echo.
echo Output:
echo   experiments\visualizer\latest_replay.json
echo   experiments\visualizer\latest_agent_log.json
echo.

python scripts\export_visualizer_json.py --output experiments\visualizer\latest_replay.json --agent-log experiments\visualizer\latest_agent_log.json
if errorlevel 1 (
  echo.
  echo FAILED.
  echo Please send this screen to Suketomo.
  echo.
  pause
  exit /b 1
)

echo.
echo DONE.
echo Open the official Kaggle notebook and load the JSON above.
echo https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
echo.
pause
