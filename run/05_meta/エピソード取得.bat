@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"
echo Downloading public Kaggle episodes...
echo Output will be written under research\episode_deck_analysis\runs\
uv run python scripts\run_episode_analysis_protocol.py --stage download --limit 1000
echo.
echo Finished. Press any key to close.
pause > nul

