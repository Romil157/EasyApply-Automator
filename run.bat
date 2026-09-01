@echo off
setlocal enabledelayedexpansion
title EasyApply Automator

:: Change to the directory where this bat file is located
cd /d "%~dp0"

echo ============================================
echo    EasyApply Automator - Control Center
echo ============================================
echo.

:: Detect Python executable (python, py, or existing venv)
set "PYTHON_CMD="
if exist "venv\Scripts\python.exe" (
    set "PYTHON_CMD=venv\Scripts\python.exe"
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py"
    ) else (
        where python >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=python"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python is not installed or not found in PATH.
    echo Download Python 3.12+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment (venv)...
    %PYTHON_CMD% -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo       Done.
    set "PYTHON_CMD=venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=venv\Scripts\python.exe"
    echo [1/3] Virtual environment verified.
)

:: Verify/Install dependencies
echo [2/3] Installing/verifying dependencies...
"%PYTHON_CMD%" -m pip install -q --upgrade pip
"%PYTHON_CMD%" -m pip install -q -e .
if %errorlevel% neq 0 (
    echo [WARNING] Retrying install with standard pip...
    "%PYTHON_CMD%" -m pip install -e .
)
echo       Done.
echo.

:: Check for command line argument or show interactive menu
set "ACTION=%~1"
if "%ACTION%"=="" (
    echo Choose an action to run:
    echo  [1] Start EasyApply Bot
    echo  [2] Start Live Web Dashboard
    echo  [3] Run Test Suite (pytest)
    echo.
    set /p "CHOICE=Enter choice [1, 2, or 3] (default 1): "
    if "!CHOICE!"=="2" (
        set "ACTION=dashboard"
    ) else if "!CHOICE!"=="3" (
        set "ACTION=test"
    ) else (
        set "ACTION=bot"
    )
)

echo.
echo ============================================
if /i "%ACTION%"=="dashboard" (
    echo [3/3] Launching Live Web Dashboard...
    echo ============================================
    "%PYTHON_CMD%" "dashboard.py"
) else if /i "%ACTION%"=="test" (
    echo [3/3] Running Pytest Suite...
    echo ============================================
    "%PYTHON_CMD%" -m pytest
) else (
    echo [3/3] Starting EasyApply Bot...
    echo ============================================
    "%PYTHON_CMD%" "easy_apply_bot.py"
)

echo.
echo ============================================
echo    Execution finished.
echo ============================================
pause

