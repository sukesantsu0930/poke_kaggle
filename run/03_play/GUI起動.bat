@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"

echo.
echo Starting manual play GUI.
echo When the browser opens, select decks and start.
echo.

start "" "http://127.0.0.1:8765"
uv run python scripts\manual_play_server.py --port 8765

echo.
pause
