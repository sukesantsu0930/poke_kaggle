@echo off
chcp 65001 >nul
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"
echo.
echo JSON ファイルを公式ビジュアライザで開きます。
echo（対戦を新規生成せず、手元の JSON をそのまま再生します）
echo.
set "DEFAULT_JSON=research\dusknoir_replaysebuilt_vs_marnie_seed1.json"
set /p JSONFILE="JSON path [%DEFAULT_JSON%]: "
if "%JSONFILE%"=="" set "JSONFILE=%DEFAULT_JSON%"
uv run python scriptsisualize_json_file.py "%JSONFILE%"
echo.
pause
