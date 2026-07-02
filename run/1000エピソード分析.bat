@echo off
cd /d "%~dp0\.."
echo Running 1000 episode analysis protocol...
echo Output will be written under research\episode_deck_analysis\runs\
python scripts\run_episode_analysis_protocol.py --limit 1000
echo.
echo Finished. Press any key to close.
pause > nul
