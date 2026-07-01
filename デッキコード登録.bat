@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ポケカ公式サイトのデッキコードを入力してください。
echo 例: 4GGxYc-KmW2Iv-8c4c8c
echo.
set /p DECK_CODE=デッキコード: 

if "%DECK_CODE%"=="" (
  echo.
  echo デッキコードが空です。もう一度やり直してください。
  echo.
  pause
  exit /b 1
)

echo.
echo デッキを確認しています...
python scripts\import_deck_code.py %DECK_CODE%

echo.
echo OK と出た場合は、GUIでそのデッキを選べます。
echo NG または ERROR と出た場合は、公式サイト側でデッキを直してください。
echo.
pause
