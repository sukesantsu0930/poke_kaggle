@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"

echo.
echo Deck CSV visualizer
echo.
echo Enter deck CSV path.
echo If empty, the Dragapult Dusknoir fleet deck is used.
echo.

set /p DECK_CSV=Deck CSV: 
if "%DECK_CSV%"=="" set DECK_CSV=decks\fleet\dragapult_dusknoir_paper.csv

uv run python scripts\render_deck_html.py "%DECK_CSV%" --open

echo.
pause
