@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"

echo Running all proposal evaluations.
echo Output will be written under experiments\proposals\
echo.

uv run python scripts\run_proposal.py --proposal proposals\dragapult_ex --games 20 --max-steps 500
if errorlevel 1 goto failed

uv run python scripts\run_proposal.py --proposal proposals\cubchoo_ogerpon --games 20 --max-steps 500
if errorlevel 1 goto failed

echo.
echo DONE.
echo Finished. Press any key to close.
pause > nul
exit /b 0

:failed
echo.
echo FAILED.
echo Please send this screen to Suketomo.
pause
exit /b 1

