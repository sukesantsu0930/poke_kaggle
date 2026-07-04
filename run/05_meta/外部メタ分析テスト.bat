@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"
echo Running small external meta analysis smoke test...
echo Output will be written under research\episode_deck_analysis\runs\
uv run python scripts\run_episode_analysis_protocol.py --stage all --limit 5
echo.
echo Finished. Press any key to close.
pause > nul

