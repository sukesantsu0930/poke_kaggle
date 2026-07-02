@echo off
cd /d "%~dp0\.."

echo.
echo Starting manual play GUI.
echo When the browser opens, select decks and start.
echo.

start "" "http://127.0.0.1:8765"
python scripts\manual_play_server.py --port 8765

echo.
pause
