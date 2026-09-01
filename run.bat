@echo off
setlocal EnableDelayedExpansion
title EasyApply Automator

rem Change to directory of this script
cd /d "%~dp0"

echo ============================================
echo    EasyApply Automator - Control Center
echo ============================================
echo.

rem Check if venv exists
if exist "venv\Scripts\python.exe" goto VENV_READY

rem Find system Python
set "SYS_PYTHON="
where py >nul 2>&1
if not errorlevel 1 set "SYS_PYTHON=py"
if "%SYS_PYTHON%"=="" (
    where python >nul 2>&1
    if not errorlevel 1 set "SYS_PYTHON=python"
)

if "%SYS_PYTHON%"=="" (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.12+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment (venv)
%SYS_PYTHON% -m venv venv
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo       Virtual environment created successfully.

:VENV_READY
echo [1/3] Virtual environment ready.
set "VENV_PYTHON=venv\Scripts\python.exe"

echo [2/3] Checking dependencies
"%VENV_PYTHON%" -m pip install -q --upgrade pip
"%VENV_PYTHON%" -m pip install -q -e .
if errorlevel 1 (
    echo [INFO] Installing dependencies
    "%VENV_PYTHON%" -m pip install -e .
)
echo       Dependencies verified.
echo.

set "ACTION=%~1"
if not "%ACTION%"=="" goto RUN_ACTION

echo Choose an option to run:
echo   [1] Start EasyApply Bot
echo   [2] Start Live Web Dashboard
echo   [3] Run Pytest Suite
echo.
set "CHOICE=1"
set /p "CHOICE=Enter choice 1, 2, or 3 (default 1): "

if "%CHOICE%"=="2" set "ACTION=dashboard"
if "%CHOICE%"=="3" set "ACTION=test"
if "%ACTION%"=="" set "ACTION=bot"

:RUN_ACTION
echo.
echo ============================================
if /i "%ACTION%"=="dashboard" (
    echo [3/3] Launching Live Web Dashboard
    echo ============================================
    "%VENV_PYTHON%" dashboard.py
) else if /i "%ACTION%"=="test" (
    echo [3/3] Running Pytest Suite
    echo ============================================
    "%VENV_PYTHON%" -m pytest
) else (
    echo [3/3] Starting EasyApply Bot
    echo ============================================
    "%VENV_PYTHON%" easy_apply_bot.py
)

echo.
echo ============================================
echo    Process finished.
echo ============================================
pause
