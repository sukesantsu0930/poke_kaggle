@echo off
cd /d "%~dp0\.."

echo.
echo Paste a Pokemon Card official deck code.
echo Example: 4GGxYc-KmW2Iv-8c4c8c
echo.
set /p DECK_CODE=Deck code: 

if "%DECK_CODE%"=="" (
  echo.
  echo Deck code is empty. Please try again.
  echo.
  pause
  exit /b 1
)

echo.
echo Checking deck code...
python scripts\import_deck_code.py %DECK_CODE%

echo.
echo If you see OK, the deck can be selected in the GUI.
echo If you see NG or ERROR, edit the deck on the official site and try again.
echo.
pause
