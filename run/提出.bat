@echo off
cd /d "%~dp0\.."

echo.
echo Kaggle submission builder
echo.
echo This builds a submission zip from one agent and one deck.
echo Competition: pokemon-tcg-ai-battle
echo.

set "DEFAULT_AGENT=agents\cubchoo_ogerpon_rb"
set "DEFAULT_DECK=decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv"
set "DEFAULT_MESSAGE=cubchoo_ogerpon_rb + winrate_1_cubchoo_ogerpon"

set /p AGENT="Agent [%DEFAULT_AGENT%]: "
if "%AGENT%"=="" set "AGENT=%DEFAULT_AGENT%"

set /p DECK="Deck [%DEFAULT_DECK%]: "
if "%DECK%"=="" set "DECK=%DEFAULT_DECK%"

set /p MESSAGE="Message [%DEFAULT_MESSAGE%]: "
if "%MESSAGE%"=="" set "MESSAGE=%DEFAULT_MESSAGE%"

echo.
echo Agent  : %AGENT%
echo Deck   : %DECK%
echo Message: %MESSAGE%
echo.

python scripts\prepare_submission.py --agent "%AGENT%" --deck "%DECK%" --message "%MESSAGE%"
if errorlevel 1 (
  echo.
  echo FAILED while building submission zip.
  echo.
  pause
  exit /b 1
)

echo.
echo Submit to Kaggle now?
echo This runs:
echo kaggle competitions submit -c pokemon-tcg-ai-battle -f [built zip] -m "%MESSAGE%"
echo.
set /p DO_SUBMIT="Type SUBMIT to upload, or press Enter to stop here: "
if /I not "%DO_SUBMIT%"=="SUBMIT" (
  echo.
  echo Not submitted. The zip was created under submissions\YYYY-MM-DD.
  echo.
  pause
  exit /b 0
)

python scripts\prepare_submission.py --agent "%AGENT%" --deck "%DECK%" --message "%MESSAGE%" --submit
if errorlevel 1 (
  echo.
  echo FAILED while submitting to Kaggle.
  echo Check Kaggle login/API token.
  echo.
  pause
  exit /b 1
)

echo.
echo DONE.
echo.
pause
