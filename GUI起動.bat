@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo 手動プレイGUIを起動します。
echo ブラウザが開いたら、デッキを選んで開始してください。
echo.

start "" "http://127.0.0.1:8765"
python scripts\manual_play_server.py --port 8765

echo.
pause
