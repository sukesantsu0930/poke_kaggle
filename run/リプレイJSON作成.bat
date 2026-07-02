@echo off
cd /d "%~dp0\.."

echo.
echo Creating a local replay JSON for the official Kaggle Visualiser.
echo.
echo Output:
echo   experiments\visualizer\latest_replay.json
echo   experiments\visualizer\latest_agent_log.json
echo.

set "DEFAULT_AGENT0=agents\cubchoo_ogerpon_rb"
set "DEFAULT_DECK0=decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv"
set "DEFAULT_AGENT1=agents\cubchoo_ogerpon_rb"
set "DEFAULT_DECK1=decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv"

set /p AGENT0="Agent 0 [%DEFAULT_AGENT0%]: "
if "%AGENT0%"=="" set "AGENT0=%DEFAULT_AGENT0%"

set /p DECK0="Deck 0 [%DEFAULT_DECK0%]: "
if "%DECK0%"=="" set "DECK0=%DEFAULT_DECK0%"

set /p AGENT1="Agent 1 [%DEFAULT_AGENT1%]: "
if "%AGENT1%"=="" set "AGENT1=%DEFAULT_AGENT1%"

set /p DECK1="Deck 1 [%DEFAULT_DECK1%]: "
if "%DECK1%"=="" set "DECK1=%DEFAULT_DECK1%"

echo.
echo Agent 0: %AGENT0%
echo Deck 0 : %DECK0%
echo Agent 1: %AGENT1%
echo Deck 1 : %DECK1%
echo.

python scripts\export_visualizer_json.py --agent0 "%AGENT0%" --deck0 "%DECK0%" --agent1 "%AGENT1%" --deck1 "%DECK1%" --output experiments\visualizer\latest_replay.json --agent-log experiments\visualizer\latest_agent_log.json
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
