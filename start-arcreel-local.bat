@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
for %%I in ("%ROOT%.") do set "ROOT=%%~fI"
set "LISTEN_PORT=1242"
set "LISTEN_HOST=127.0.0.1"
set "URL=http://127.0.0.1:%LISTEN_PORT%/app/projects"

echo ========================================
echo   ArcReel local launcher
echo ========================================
echo Root: %ROOT%
echo URL:  %URL%
echo.

if not exist "%ROOT%\server\app.py" (
  echo [ERROR] server\app.py not found.
  echo This launcher must stay in the ArcReel project root.
  pause
  exit /b 1
)

if exist "%ROOT%\.env" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%\.env") do (
    if /I "%%A"=="AUTH_USERNAME" set "AUTH_USERNAME=%%B"
    if /I "%%A"=="AUTH_PASSWORD" set "AUTH_PASSWORD=%%B"
  )
) else (
  echo [WARN] .env not found. Authentication may use server defaults.
)

where uv >nul 2>&1
if errorlevel 1 (
  echo [ERROR] uv was not found in PATH.
  echo Install uv first, then run this launcher again.
  pause
  exit /b 1
)

echo Cleaning old service on port %LISTEN_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(Get-NetTCPConnection -LocalPort %LISTEN_PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique); foreach ($procId in $ports) { if ($procId -and $procId -ne $PID) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } }" >nul 2>nul

echo Starting server. Keep the new server window open.
start "ArcReel Server %LISTEN_PORT%" powershell -NoExit -NoProfile -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%'; $env:LISTEN_PORT='%LISTEN_PORT%'; $env:LISTEN_HOST='%LISTEN_HOST%'; uv run --no-dev uvicorn server.app:app --host %LISTEN_HOST% --port %LISTEN_PORT%"

echo Waiting for startup...
timeout /t 8 /nobreak >nul

echo Opening browser...
start "" "%URL%"

echo.
if defined AUTH_USERNAME echo Username: %AUTH_USERNAME%
if defined AUTH_PASSWORD echo Password: %AUTH_PASSWORD%
echo.
echo You may close this launcher window. Do not close the server window.
timeout /t 5 /nobreak >nul
