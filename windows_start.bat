@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "WEB_DIR=%SCRIPT_DIR%web"
set "PID_FILE=%WEB_DIR%\.polyai.pid"
set "LOG_FILE=%WEB_DIR%\.polyai.log"
set "PORT=8080"

if not exist "%WEB_DIR%\app.py" (
    echo ❌ 找不到 web\app.py
    pause
    exit /b 1
)

set "CMD=%~1"
if "%CMD%"=="" set "CMD=start"

if /i "%CMD%"=="start"   goto do_start
if /i "%CMD%"=="stop"    goto do_stop
if /i "%CMD%"=="restart" goto do_restart
if /i "%CMD%"=="status"  goto do_status
if /i "%CMD%"=="log"     goto do_log
if /i "%CMD%"=="install" goto do_install
goto usage

:check_dependencies
set "DEPS_OK=1"
set "MISSING_PY="
set "MISSING_OPT="

where python >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 python，请先安装 Python 3.8+
    echo    下载地址: https://www.python.org/downloads/
    echo    安装时请勾选 "Add Python to PATH"
    set "DEPS_OK=0"
    goto :eof
)

python -c "import flask" 2>nul
if errorlevel 1 set "MISSING_PY=!MISSING_PY! flask"

python -c "import requests" 2>nul
if errorlevel 1 set "MISSING_PY=!MISSING_PY! requests"

if not "!MISSING_PY!"=="" (
    echo ❌ 缺少必要 Python 包:!MISSING_PY!
    echo.
    set /p "ANSWER=是否一键安装? [Y/n] "
    if "!ANSWER!"=="" set "ANSWER=Y"
    if /i "!ANSWER!"=="Y" (
        echo ⏳ 正在安装:!MISSING_PY!
        python -m pip install!MISSING_PY!
        if errorlevel 1 (
            echo ❌ 安装失败，请手动执行: pip install!MISSING_PY!
            set "DEPS_OK=0"
            goto :eof
        )
        echo ✅ 必要包安装完成
    ) else (
        echo 请手动安装: pip install!MISSING_PY!
        set "DEPS_OK=0"
        goto :eof
    )
)

python -c "from PyPDF2 import PdfReader" 2>nul
if errorlevel 1 set "MISSING_OPT=!MISSING_OPT! PyPDF2"

python -c "import docx" 2>nul
if errorlevel 1 set "MISSING_OPT=!MISSING_OPT! python-docx"

python -c "import openpyxl" 2>nul
if errorlevel 1 set "MISSING_OPT=!MISSING_OPT! openpyxl"

if not "!MISSING_OPT!"=="" (
    echo ⚠️  以下可选包未安装（文件解析功能需要）:!MISSING_OPT!
    echo.
    set /p "ANSWER2=是否安装可选包? [y/N] "
    if "!ANSWER2!"=="" set "ANSWER2=N"
    if /i "!ANSWER2!"=="Y" (
        echo ⏳ 正在安装:!MISSING_OPT!
        python -m pip install!MISSING_OPT!
        if errorlevel 1 (
            echo ⚠️  部分可选包安装失败，不影响基本功能
        ) else (
            echo ✅ 可选包安装完成
        )
    )
)
goto :eof

:do_install
echo 🔧 PolyAI Chat 一键安装依赖
echo ==============================
call :check_dependencies
if "!DEPS_OK!"=="1" (
    echo.
    echo ✅ 所有依赖已就绪
)
goto :eof

:do_start
call :check_dependencies
if "!DEPS_OK!"=="0" (
    pause
    exit /b 1
)

call :check_running
if defined RUNNING_PID (
    echo ⚠️  PolyAI Chat 已在运行 ^(PID: !RUNNING_PID!^)
    echo 📎 访问: http://localhost:%PORT%
    echo 🛑 关闭: %~nx0 stop
    goto :eof
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo ⚠️  端口 %PORT% 被占用 ^(PID: %%a^)，正在释放...
    taskkill /PID %%a /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

cd /d "%WEB_DIR%"
echo. > "%LOG_FILE%"
start /b "" python app.py >>"%LOG_FILE%" 2>&1

timeout /t 2 /nobreak >nul

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo %%a> "%PID_FILE%"
    echo ✅ PolyAI Chat 已启动 ^(PID: %%a^)
    echo 📎 访问: http://localhost:%PORT%
    echo 📋 日志: %~nx0 log
    echo 🛑 关闭: %~nx0 stop
    start "" http://localhost:%PORT%
    goto :eof
)

del /f /q "%PID_FILE%" 2>nul
echo ❌ 启动失败，最近日志:
if exist "%LOG_FILE%" (
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 20"
)
pause
exit /b 1

:do_stop
call :check_running
if not defined RUNNING_PID (
    echo ℹ️  PolyAI Chat 未在运行
    del /f /q "%PID_FILE%" 2>nul
    goto :eof
)
echo ⏳ 正在关闭 PolyAI Chat ^(PID: !RUNNING_PID!^)...
taskkill /PID !RUNNING_PID! /F >nul 2>&1
timeout /t 1 /nobreak >nul
del /f /q "%PID_FILE%" 2>nul
echo ✅ PolyAI Chat 已关闭
goto :eof

:do_restart
call :do_stop
timeout /t 1 /nobreak >nul
call :do_start
goto :eof

:do_status
call :check_running
if defined RUNNING_PID (
    echo ✅ PolyAI Chat 运行中 ^(PID: !RUNNING_PID!^)
    echo 📎 访问: http://localhost:%PORT%
) else (
    echo ⭕ PolyAI Chat 未运行
)
goto :eof

:do_log
if not exist "%LOG_FILE%" (
    echo ℹ️  暂无日志
    goto :eof
)
powershell -Command "Get-Content '%LOG_FILE%' -Tail 50"
goto :eof

:check_running
set "RUNNING_PID="
if not exist "%PID_FILE%" goto :eof
set /p RUNNING_PID=<"%PID_FILE%"
if "!RUNNING_PID!"=="" (
    del /f /q "%PID_FILE%" 2>nul
    goto :eof
)
tasklist /FI "PID eq !RUNNING_PID!" 2>nul | findstr /i "python" >nul
if errorlevel 1 (
    set "RUNNING_PID="
    del /f /q "%PID_FILE%" 2>nul
)
goto :eof

:usage
echo 用法: %~nx0 [start^|stop^|restart^|status^|log^|install]
echo.
echo   start    启动 PolyAI Chat（默认，可双击运行）
echo   stop     关闭 PolyAI Chat
echo   restart  重启 PolyAI Chat
echo   status   查看运行状态
echo   log      查看最近日志
echo   install  检测并安装所有依赖
echo.
echo 双击直接运行等同于 start 命令。
pause
exit /b 1
