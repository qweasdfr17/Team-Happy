@echo off
chcp 65001 >nul
title Team-Happy
setlocal

rem ============================================================
rem  Team-Happy Windows portable launcher
rem  Target: clean Windows 10/11 x64, no Git/Node/pnpm/WSL needed.
rem ============================================================

cd /d "%~dp0"
set "ROOT=%~dp0"

if not defined LISTEN_PORT set "LISTEN_PORT=1241"
set "TEAM_HAPPY_URL=http://127.0.0.1:%LISTEN_PORT%"

rem Local single-user package defaults.
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
    echo [错误] 没有找到 Python。
    echo.
    echo 请先安装 Python 3.12 或更高版本：
    echo https://www.python.org/downloads/
    echo.
    echo 安装时一定要勾选 "Add Python to PATH"，安装完成后再双击本文件。
    echo.
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 版本过低。Team-Happy 需要 Python 3.12 或更高版本。
    echo 当前版本：
    python --version
    echo.
    echo 请安装 Python 3.12+，并勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] 未找到 uv，正在通过 pip 自动安装...
    python -m pip install uv
    if errorlevel 1 (
        echo.
        echo [错误] uv 安装失败。请检查网络后重试，或手动执行：
        echo python -m pip install uv
        echo.
        pause
        exit /b 1
    )
)

if not exist "%ROOT%frontend\dist\index.html" (
    echo [错误] 缺少前端页面文件：frontend\dist\index.html
    echo.
    echo 这个发布包不完整。请使用 packaging\windows\build-portable.ps1 重新生成。
    echo.
    pause
    exit /b 1
)

echo [INFO] 同步 Python 依赖。首次启动需要下载依赖，可能需要几分钟...
uv --directory "%ROOT%" sync --locked --no-dev
if errorlevel 1 (
    echo.
    echo [错误] Python 依赖同步失败。请检查网络后重试。
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Team-Happy 正在启动
echo.
echo   访问地址:  %TEAM_HAPPY_URL%
echo   数据目录:  %ARCREEL_DATA_DIR%
echo   登录模式:  本地免登录
echo.
echo   关闭方式:  关闭这个黑色窗口即可停止 Team-Happy
echo ============================================================
echo.

start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$url=$env:TEAM_HAPPY_URL; $port=[int]$env:LISTEN_PORT; for($i=0; $i -lt 90; $i++){ try { $c=New-Object Net.Sockets.TcpClient('127.0.0.1',$port); $c.Close(); Start-Process $url; exit 0 } catch { Start-Sleep -Seconds 1 } }; Start-Process $url"

uv --directory "%ROOT%" run uvicorn server.app:app --host 127.0.0.1 --port %LISTEN_PORT%

echo.
echo Team-Happy 已停止。
pause
