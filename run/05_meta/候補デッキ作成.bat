@echo off
cd /d "%~dp0\..\.."
echo Building candidate decks from the latest episode run...
echo This uses the newest folder under research\episode_deck_analysis\runs\
uv run python scripts\run_episode_analysis_protocol.py --stage build-decks --run-dir latest --limit 1000
uv run python scripts\run_episode_analysis_protocol.py --stage next-actions --run-dir latest --limit 1000
echo.
echo Finished. Press any key to close.
pause > nul

