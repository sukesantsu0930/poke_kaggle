@echo off
cd /d "%~dp0\..\.."
echo Running meta analysis for the latest episode run...
echo This uses the newest folder under research\episode_deck_analysis\runs\
uv run python scripts\run_episode_analysis_protocol.py --stage analyze --run-dir latest --limit 1000
echo.
echo Finished. Press any key to close.
pause > nul

