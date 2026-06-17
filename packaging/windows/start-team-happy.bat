@echo off
title Team-Happy
setlocal

rem ============================================================
rem  Team-Happy Windows portable launcher
rem  Target: clean Windows 10/11 x64.
rem ============================================================

cd /d "%~dp0"
set "ROOT=%~dp0"

if not defined LISTEN_PORT set "LISTEN_PORT=1241"
set "TEAM_HAPPY_URL=http://127.0.0.1:%LISTEN_PORT%"

rem Local single-user defaults.
set "AUTH_ENABLED=false"
if not defined ARCREEL_DATA_DIR set "ARCREEL_DATA_DIR=%ROOT%data"
if not defined ARCREEL_PROFILE_DIR set "ARCREEL_PROFILE_DIR=%ROOT%agent_runtime_profile"

if not exist "%ARCREEL_DATA_DIR%" mkdir "%ARCREEL_DATA_DIR%"

echo.
echo ============================================================
echo   Team-Happy Windows Portable
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo.
    echo Install Python 3.12 or newer first:
    echo https://www.python.org/downloads/
    echo.
    echo During install, enable: Add python.exe to PATH
    echo Then close this window and run start-team-happy.bat again.
    echo.
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.12 or newer is required.
    echo Current version:
    python --version
    echo.
    pause
    exit /b 1
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] uv was not found. Installing uv with pip...
    python -m pip install uv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install uv.
        echo Check the network, then try again.
        echo You can also run manually:
        echo python -m pip install uv
        echo.
        pause
        exit /b 1
    )
)

if not exist "%ROOT%frontend\dist\index.html" (
    echo [ERROR] Missing frontend\dist\index.html.
    echo This portable package is incomplete. Please rebuild the package.
    echo.
    pause
    exit /b 1
)

echo [INFO] Syncing Python dependencies.
echo First launch may take several minutes.
uv --directory "%ROOT%" sync --locked --no-dev
if errorlevel 1 (
    echo.
    echo [ERROR] Python dependency sync failed.
    echo Check the network, then try again.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Team-Happy is starting
echo.
echo   URL:       %TEAM_HAPPY_URL%
echo   Data dir:  %ARCREEL_DATA_DIR%
echo   Auth:      local no-login mode
echo.
echo   Keep this window open while using Team-Happy.
echo   Close this window to stop Team-Happy.
echo ============================================================
echo.

start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$url=$env:TEAM_HAPPY_URL; $port=[int]$env:LISTEN_PORT; for($i=0; $i -lt 90; $i++){ try { $c=New-Object Net.Sockets.TcpClient('127.0.0.1',$port); $c.Close(); Start-Process $url; exit 0 } catch { Start-Sleep -Seconds 1 } }; Start-Process $url"

uv --directory "%ROOT%" run uvicorn server.app:app --host 127.0.0.1 --port %LISTEN_PORT%

echo.
echo Team-Happy has stopped.
pause
