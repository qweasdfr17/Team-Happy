@echo off
title Team-Happy
setlocal

rem ============================================================
rem  Team-Happy Windows portable launcher
rem  Target: clean Windows 10/11 x64.
rem ============================================================

cd /d "%~dp0"
for %%I in ("%~dp0.") do set "ROOT=%%~fI"

if not defined LISTEN_PORT set "LISTEN_PORT=1241"
set "TEAM_HAPPY_URL=http://127.0.0.1:%LISTEN_PORT%"

rem Local single-user defaults.
set "AUTH_ENABLED=false"
if not defined ARCREEL_DATA_DIR set "ARCREEL_DATA_DIR=%ROOT%\data"
if not defined ARCREEL_PROFILE_DIR set "ARCREEL_PROFILE_DIR=%ROOT%\agent_runtime_profile"
set "UV_LINK_MODE=copy"

if not exist "%ARCREEL_DATA_DIR%" mkdir "%ARCREEL_DATA_DIR%"
set "LOG_DIR=%ARCREEL_DATA_DIR%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "START_LOG=%LOG_DIR%\start-team-happy.log"

echo ============================================================ > "%START_LOG%"
echo Team-Happy launcher log >> "%START_LOG%"
echo Root: %ROOT% >> "%START_LOG%"
echo Started: %DATE% %TIME% >> "%START_LOG%"
echo ============================================================ >> "%START_LOG%"

echo.
echo ============================================================
echo   Team-Happy Windows Portable
echo ============================================================
echo.

set "UV_CMD=uv"
where uv >nul 2>&1
if errorlevel 1 (
    set "PYTHON_CMD="
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"

    if not defined PYTHON_CMD (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=python"
    )

    if not defined PYTHON_CMD (
        echo [ERROR] Python was not found.
        echo.
        echo Install Python 3.12 with PowerShell:
        echo winget install -e --id Python.Python.3.12
        echo.
        echo Or download from:
        echo https://www.python.org/downloads/
        echo.
        echo During manual install, enable: Add python.exe to PATH
        echo Then close this window and run start-team-happy.bat again.
        echo.
        echo ERROR: Python was not found. >> "%START_LOG%"
        pause
        exit /b 1
    )

    echo [INFO] Python command for uv install: %PYTHON_CMD%
    echo Python command for uv install: %PYTHON_CMD% >> "%START_LOG%"
    %PYTHON_CMD% --version
    %PYTHON_CMD% --version >> "%START_LOG%" 2>&1

    echo [INFO] uv was not found. Installing uv with pip...
    echo Installing uv with pip... >> "%START_LOG%"
    %PYTHON_CMD% -m pip install uv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install uv.
        echo Check the network, then try again.
        echo Details: %START_LOG%
        echo.
        echo ERROR: pip install uv failed. >> "%START_LOG%"
        pause
        exit /b 1
    )
)

where uv >nul 2>&1
if errorlevel 1 (
    if not defined PYTHON_CMD (
        echo.
        echo [ERROR] uv is not available, and no Python command is available to run it.
        echo Details: %START_LOG%
        echo.
        echo ERROR: uv unavailable and PYTHON_CMD empty. >> "%START_LOG%"
        pause
        exit /b 1
    )
    %PYTHON_CMD% -m uv --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] uv was installed, but it cannot be found.
        echo Try closing this window and running start-team-happy.bat again.
        echo Details: %START_LOG%
        echo.
        echo ERROR: uv is unavailable after installation. >> "%START_LOG%"
        pause
        exit /b 1
    )
    set "UV_CMD=%PYTHON_CMD% -m uv"
)

echo [INFO] uv command: %UV_CMD%
echo uv command: %UV_CMD% >> "%START_LOG%"
%UV_CMD% --version
%UV_CMD% --version >> "%START_LOG%" 2>&1

if not exist "%ROOT%\frontend\dist\index.html" (
    echo [ERROR] Missing frontend\dist\index.html.
    echo This portable package is incomplete. Please rebuild the package.
    echo Details: %START_LOG%
    echo.
    echo ERROR: Missing frontend\dist\index.html. >> "%START_LOG%"
    pause
    exit /b 1
)

echo [INFO] Syncing Python dependencies.
echo [INFO] First launch may take several minutes.
echo Running uv sync... >> "%START_LOG%"
%UV_CMD% --directory "%ROOT%" sync --locked --no-dev
if errorlevel 1 (
    echo.
    echo [ERROR] Python dependency sync failed.
    echo Check the network, then try again.
    echo Details: %START_LOG%
    echo.
    echo ERROR: uv sync failed. >> "%START_LOG%"
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

echo Starting uvicorn... >> "%START_LOG%"
start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$url=$env:TEAM_HAPPY_URL; $port=[int]$env:LISTEN_PORT; for($i=0; $i -lt 90; $i++){ try { $c=New-Object Net.Sockets.TcpClient('127.0.0.1',$port); $c.Close(); Start-Process $url; exit 0 } catch { Start-Sleep -Seconds 1 } }; Start-Process $url"

%UV_CMD% --directory "%ROOT%" run uvicorn server.app:app --host 127.0.0.1 --port %LISTEN_PORT%

echo.
echo Team-Happy has stopped.
echo Team-Happy stopped: %DATE% %TIME% >> "%START_LOG%"
pause
