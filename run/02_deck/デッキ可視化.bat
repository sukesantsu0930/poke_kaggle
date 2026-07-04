@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"

echo.
echo Deck CSV visualizer
echo.
echo Enter deck CSV path.
echo If empty, the Cubchoo / Ogerpon candidate deck is used.
echo.

set /p DECK_CSV=Deck CSV: 
if "%DECK_CSV%"=="" set DECK_CSV=decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv

uv run python scripts\render_deck_html.py "%DECK_CSV%" --open

echo.
pause
