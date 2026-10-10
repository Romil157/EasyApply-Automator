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
"%VENV_PYTHON%" -c "import easy_apply_automator, flask, selenium, yaml, bs4" >nul 2>&1
if errorlevel 1 (
    echo       Dependencies missing or uninitialized. Installing project...
    "%VENV_PYTHON%" -m pip install -q --upgrade pip
    "%VENV_PYTHON%" -m pip install -e .
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)
echo       Dependencies verified.
echo.

set "FIRST=%~1"
set "ACTION="
set "LEVEL="
set "EXTRA_ARGS="

rem Interactive mode when no arguments supplied
if "%FIRST%"=="" goto INTERACTIVE

rem Help flags
if "%FIRST%"=="-h" goto SHOW_HELP
if "%FIRST%"=="--help" goto SHOW_HELP
if /i "%FIRST%"=="help" goto SHOW_HELP
if "%FIRST%"=="/?" goto SHOW_HELP

rem Dedicated reinstall/update command
if /i "%FIRST%"=="install" goto RUN_INSTALL
if /i "%FIRST%"=="update" goto RUN_INSTALL

rem Direct bot flags starting with -
set "FIRST_CHAR=%FIRST:~0,1%"
if "%FIRST_CHAR%"=="-" (
    set "ACTION=bot"
    set "EXTRA_ARGS=%*"
    goto RUN_ACTION
)

rem Option 1 or bot
if "%FIRST%"=="1" goto PARSE_BOT_ARGS
if /i "%FIRST%"=="bot" goto PARSE_BOT_ARGS

rem Option 2 or dashboard
if "%FIRST%"=="2" goto PARSE_DASHBOARD_ARGS
if /i "%FIRST%"=="dashboard" goto PARSE_DASHBOARD_ARGS

rem Option 3 or test
if "%FIRST%"=="3" goto PARSE_TEST_ARGS
if /i "%FIRST%"=="test" goto PARSE_TEST_ARGS
if /i "%FIRST%"=="pytest" goto PARSE_TEST_ARGS

echo [WARNING] Unrecognized action: %FIRST%
echo Defaulting to EasyApply Bot with arguments: %*
set "ACTION=bot"
set "EXTRA_ARGS=%*"
goto RUN_ACTION

:PARSE_BOT_ARGS
set "ACTION=bot"
shift
set "SECOND=%~1"
if "%SECOND%"=="1" (
    set "LEVEL=1"
    shift
) else if "%SECOND%"=="2" (
    set "LEVEL=2"
    shift
) else if "%SECOND%"=="3" (
    set "LEVEL=3"
    shift
)
:COLLECT_BOT_ARGS
if not "%~1"=="" (
    set "EXTRA_ARGS=!EXTRA_ARGS! %1"
    shift
    goto COLLECT_BOT_ARGS
)
goto RUN_ACTION

:PARSE_DASHBOARD_ARGS
set "ACTION=dashboard"
shift
:COLLECT_DASHBOARD_ARGS
if not "%~1"=="" (
    set "EXTRA_ARGS=!EXTRA_ARGS! %1"
    shift
    goto COLLECT_DASHBOARD_ARGS
)
goto RUN_ACTION

:PARSE_TEST_ARGS
set "ACTION=test"
shift
:COLLECT_TEST_ARGS
if not "%~1"=="" (
    set "EXTRA_ARGS=!EXTRA_ARGS! %1"
    shift
    goto COLLECT_TEST_ARGS
)
goto RUN_ACTION

:INTERACTIVE
echo Choose an option to run:
echo   [1] Start EasyApply Bot
echo   [2] Start Live Web Dashboard
echo   [3] Run Pytest Suite
echo.
set "CHOICE=1"
set /p "CHOICE=Enter choice 1, 2, or 3 (default 1): "
if defined CHOICE set "CHOICE=!CHOICE: =!"
if "!CHOICE!"=="" set "CHOICE=1"

if "!CHOICE!"=="2" (
    set "ACTION=dashboard"
    goto RUN_ACTION
)
if /i "!CHOICE!"=="dashboard" (
    set "ACTION=dashboard"
    goto RUN_ACTION
)
if "!CHOICE!"=="3" (
    set "ACTION=test"
    goto RUN_ACTION
)
if /i "!CHOICE!"=="test" (
    set "ACTION=test"
    goto RUN_ACTION
)
if /i "!CHOICE!"=="pytest" (
    set "ACTION=test"
    goto RUN_ACTION
)

set "ACTION=bot"
echo.
echo Select Target Role Type:
echo   [1] Internship Roles Only
echo   [2] Full-Time and Entry-Level Roles
echo   [3] Both (Internship and Full-Time) [Default]
echo.
set "LEVEL=3"
set /p "LEVEL=Enter choice 1, 2, or 3 (default 3): "
if defined LEVEL set "LEVEL=!LEVEL: =!"
if not "!LEVEL!"=="1" if not "!LEVEL!"=="2" set "LEVEL=3"
goto RUN_ACTION

:SHOW_HELP
echo ==============================================================
echo    EasyApply Automator - Usage Guide
echo ==============================================================
echo.
echo   run.bat [ACTION] [OPTIONS]
echo.
echo Actions:
echo   1, bot [LEVEL] [FLAGS]    Start EasyApply Bot (LEVEL: 1, 2, or 3)
echo   2, dashboard [FLAGS]      Start Live Web Dashboard
echo   3, test, pytest [FLAGS]   Run Pytest suite
echo   install, update           Reinstall/update project dependencies
echo.
echo Direct Bot Flags:
echo   run.bat --dry-run         Simulate application without final submit
echo   run.bat --headless        Run Chrome headlessly
echo   run.bat --level 1         Run internship-focused search directly
echo.
echo Interactive:
echo   run.bat                   Launch interactive menu selection
echo.
exit /b 0

:RUN_INSTALL
echo [3/3] Reinstalling and updating dependencies...
"%VENV_PYTHON%" -m pip install -q --upgrade pip
"%VENV_PYTHON%" -m pip install -e ".[dev]"
echo Dependencies successfully updated.
goto FINISH

:RUN_ACTION
echo.
echo ============================================
if /i "!ACTION!"=="dashboard" (
    echo [3/3] Launching Live Web Dashboard
    echo ============================================
    if not "!EXTRA_ARGS!"=="" (
        "%VENV_PYTHON%" dashboard.py !EXTRA_ARGS!
    ) else (
        "%VENV_PYTHON%" dashboard.py
    )
) else if /i "!ACTION!"=="test" (
    echo [3/3] Running Pytest Suite
    echo ============================================
    "%VENV_PYTHON%" -c "import pytest" >nul 2>&1
    if errorlevel 1 (
        echo       Installing test dependencies...
        "%VENV_PYTHON%" -m pip install -q -e ".[dev]"
    )
    if not "!EXTRA_ARGS!"=="" (
        "%VENV_PYTHON%" -m pytest !EXTRA_ARGS!
    ) else (
        "%VENV_PYTHON%" -m pytest
    )
) else (
    echo [3/3] Starting EasyApply Bot
    echo ============================================
    if not "!LEVEL!"=="" (
        if not "!EXTRA_ARGS!"=="" (
            "%VENV_PYTHON%" easy_apply_bot.py --level !LEVEL! !EXTRA_ARGS!
        ) else (
            "%VENV_PYTHON%" easy_apply_bot.py --level !LEVEL!
        )
    ) else (
        if not "!EXTRA_ARGS!"=="" (
            "%VENV_PYTHON%" easy_apply_bot.py !EXTRA_ARGS!
        ) else (
            "%VENV_PYTHON%" easy_apply_bot.py
        )
    )
)

:FINISH
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo ============================================
echo    Process finished.
echo ============================================
if not defined CI pause
exit /b !EXIT_CODE!
