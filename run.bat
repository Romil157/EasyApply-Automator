@echo off
title EasyApply Automator

:: Change to the directory where this bat file is located
cd /d "%~dp0"

echo ============================================
echo    EasyApply Automator - Setup ^& Run
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
    echo       Done.
) else (
    echo [1/3] Virtual environment already exists. Skipping.
)

:: Install dependencies using the virtual environment's pip
echo [2/3] Installing/verifying dependencies...
"venv\Scripts\python.exe" -m pip install -r "requirements.txt"
echo       Done.

:: Run the bot using the virtual environment's python
echo [3/3] Starting the bot...
echo.
echo ============================================
"venv\Scripts\python.exe" "easy_apply_bot.py"

:: Keep window open if bot exits
echo.
echo ============================================
echo    Bot has stopped.
echo ============================================
pause
