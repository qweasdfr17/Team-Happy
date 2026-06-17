@echo off
chcp 65001 >nul
title Team-Happy
setlocal enabledelayedexpansion

:: ============================================================
::  Team-Happy 便携启动脚本 (Windows)
::  纯文本 UTF-8 编码，不要用记事本另存为 ANSI
:: ============================================================

:: 1. 定位发布包根目录（本 bat 所在目录）
cd /d "%~dp0"
set "ROOT=%~dp0"

:: 2. 数据目录——所有项目、数据库、配置都在这里，换电脑拷贝整个目录即可
if not defined ARCREEL_DATA_DIR (
    set "ARCREEL_DATA_DIR=%ROOT%data"
)
if not exist "%ARCREEL_DATA_DIR%" mkdir "%ARCREEL_DATA_DIR%"

:: 3. 免登录模式（本地单机使用）
set "AUTH_ENABLED=false"

:: 4. 端口
if not defined LISTEN_PORT set "LISTEN_PORT=1241"

:: 5. 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python。
    echo   请安装 Python 3.12+  https://www.python.org/downloads/
    echo   安装时勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: 6. 检查 uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 未找到 uv，尝试用 pip 安装...
    pip install uv --quiet 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] 安装 uv 失败。请手动安装:
        echo   pip install uv
        pause
        exit /b 1
    )
)

:: 7. 检查前端构建产物
if not exist "%ROOT%frontend\dist\index.html" (
    echo [WARN] 未找到前端构建产物 (frontend/dist/)
    echo   如果是首次启动，请先在项目根执行: cd frontend ^&^& pnpm build
    echo   继续使用后端 API 模式启动（前端页面不可用）...
)

:: 8. 同步依赖（首次慢，后续秒过）
echo [INFO] 同步 Python 依赖...
uv --directory "%ROOT%" sync --quiet 2>nul

:: 9. 启动
echo.
echo ============================================================
echo   Team-Happy 启动中...
echo   免登录模式: 已启用
echo   数据目录:    %ARCREEL_DATA_DIR%
echo   访问地址:    http://127.0.0.1:%LISTEN_PORT%
echo   关闭方式:    关掉此窗口即停止服务
echo ============================================================
echo.

:: 10. 打开浏览器
start "" "http://127.0.0.1:%LISTEN_PORT%"

:: 11. 启动后端（单端口同时服务 API + 前端 SPA）
uv --directory "%ROOT%" run uvicorn server.app:app --host 127.0.0.1 --port %LISTEN_PORT%

:: 12. 退出提示
echo.
echo Team-Happy 已停止。
pause
