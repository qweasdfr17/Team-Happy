@echo off
title Team-Happy LAN
setlocal

rem ============================================================
rem  Team-Happy LAN launcher
rem  Use this only on a trusted local network / same Wi-Fi.
rem ============================================================

cd /d "%~dp0"

if not defined LISTEN_PORT set "LISTEN_PORT=1241"
set "LISTEN_HOST=0.0.0.0"
set "AUTH_ENABLED=true"
set "AUTH_USERNAME=admin"
set "TEAM_HAPPY_LAN_MODE=true"
set "TEAM_HAPPY_URL=http://127.0.0.1:%LISTEN_PORT%"

echo.
echo ============================================================
echo   Team-Happy LAN Mode
echo ============================================================
echo.
echo This mode allows other devices on the same Wi-Fi/LAN to access Team-Happy.
echo Login is enabled automatically. Default username: admin
echo If no password is configured, Team-Happy will generate one in .env.
echo.
echo Do not expose this LAN mode directly to the public internet.
echo.

call "%~dp0start-team-happy.bat"
