@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"

echo Running proposal evaluation: cubchoo_ogerpon
echo Output will be written under experiments\proposals\cubchoo_ogerpon\
echo.

uv run python scripts\run_proposal.py --proposal proposals\cubchoo_ogerpon --games 20 --max-steps 500

echo.
echo Finished. Press any key to close.
pause > nul

