@echo off
cd /d "%~dp0\..\.."

echo.
echo Generating local card images from Card_ID List_JP.pdf.
echo This is needed only once.
echo Please do not close this window until you see "DONE".
echo.

uv run python scripts\extract_card_images.py
if errorlevel 1 (
  echo.
  echo FAILED.
  echo Please send this screen to Suketomo.
  echo.
  pause
  exit /b 1
)

echo.
echo DONE.
echo Card images are ready. You can now start the GUI.
echo.
pause
