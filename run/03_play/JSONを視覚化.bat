@echo off
cd /d "%~dp0\..\.."
set "UV_CACHE_DIR=%CD%\.uv-cache"

echo.
echo Open local JSON replays in the official Visualiser.
echo (Replays existing JSON files. Does NOT run a new battle.)
echo Keep entering JSON names to visualise one after another.
echo Press Enter on an empty line (or type q) to quit.

:loop
echo.
echo Available replays in research\chandelure_replays :
dir /b "research\chandelure_replays\*.json" 2>nul | findstr /v /i "agentlog"
echo.
echo Available replays in research\dusknoir_replays :
dir /b "research\dusknoir_replays\*.json" 2>nul | findstr /v /i "agentlog"
echo.

rem set /p keeps the previous value on empty input, so reset first (empty = quit).
set "JSONFILE="
set /p JSONFILE="JSON path (Enter/q = quit): "
if not defined JSONFILE goto :eof
if /i "%JSONFILE%"=="q" goto :eof

rem Allow entering just the file name (resolve it under either replay folder).
if not exist "%JSONFILE%" if exist "research\chandelure_replays\%JSONFILE%" set "JSONFILE=research\chandelure_replays\%JSONFILE%"
if not exist "%JSONFILE%" if exist "research\dusknoir_replays\%JSONFILE%" set "JSONFILE=research\dusknoir_replays\%JSONFILE%"

if not exist "%JSONFILE%" (
  echo.
  echo NOT FOUND: %JSONFILE%
  goto :loop
)

echo.
echo Opening: %JSONFILE%
uv run python "scripts\visualize_json_file.py" "%JSONFILE%"
if errorlevel 1 (
  echo.
  echo FAILED.
  echo Please send this screen to Suketomo.
)
goto :loop
