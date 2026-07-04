@echo off
cd /d "%~dp0\..\.."

echo Running proposal evaluation: dragapult_ex
echo Output will be written under experiments\proposals\dragapult_ex\
echo.

uv run python scripts\run_proposal.py --proposal proposals\dragapult_ex --games 20 --max-steps 500

echo.
echo Finished. Press any key to close.
pause > nul

