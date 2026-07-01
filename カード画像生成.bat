@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo Card_ID List_JP.pdf からカード画像を作ります。
echo 初回だけ時間がかかります。
echo.

python scripts\extract_card_images.py

echo.
echo OK と出たら、GUIでカード画像が表示されます。
echo.
pause
