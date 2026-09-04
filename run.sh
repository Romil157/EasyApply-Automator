#!/usr/bin/env bash

# Change to the directory where this script is located
cd "$(dirname "$0")"

echo "============================================"
echo "   EasyApply Automator - Control Center"
echo "============================================"
echo

# Check if python3 is installed
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is not installed or not in PATH."
    echo "Please install Python 3.12+."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment (venv)..."
    python3 -m venv venv
    echo "      Done."
else
    echo "[1/3] Virtual environment verified."
fi

# Install dependencies
echo "[2/3] Installing/verifying dependencies..."
./venv/bin/python3 -m pip install -q --upgrade pip
./venv/bin/python3 -m pip install -q -e . || ./venv/bin/python3 -m pip install -e .
echo "      Done."
echo

ACTION="$1"
LEVEL="$2"
if [ -z "$ACTION" ]; then
    echo "Choose an action to run:"
    echo " [1] Start EasyApply Bot"
    echo " [2] Start Live Web Dashboard"
    echo " [3] Run Test Suite (pytest)"
    echo
    read -p "Enter choice [1, 2, or 3] (default 1): " CHOICE
    case "$CHOICE" in
        2) ACTION="dashboard" ;;
        3) ACTION="test" ;;
        *) ACTION="bot" ;;
    esac

    if [ "$ACTION" = "bot" ]; then
        echo
        echo "Select Target Role Type:"
        echo "  [1] Internship Roles Only"
        echo "  [2] Full-Time & Entry-Level Roles"
        echo "  [3] Both (Internship & Full-Time) [Default]"
        echo
        read -p "Enter choice [1, 2, or 3] (default 3): " LEVEL_CHOICE
        case "$LEVEL_CHOICE" in
            1) LEVEL="1" ;;
            2) LEVEL="2" ;;
            *) LEVEL="3" ;;
        esac
    fi
fi

echo
echo "============================================"
if [ "$ACTION" = "dashboard" ]; then
    echo "[3/3] Launching Live Web Dashboard..."
    echo "============================================"
    ./venv/bin/python3 dashboard.py
elif [ "$ACTION" = "test" ]; then
    echo "[3/3] Running Pytest Suite..."
    echo "============================================"
    ./venv/bin/python3 -m pytest
else
    echo "[3/3] Starting EasyApply Bot..."
    echo "============================================"
    if [ -n "$LEVEL" ]; then
        ./venv/bin/python3 easy_apply_bot.py --level "$LEVEL"
    else
        ./venv/bin/python3 easy_apply_bot.py
    fi
fi

echo
echo "============================================"
echo "   Execution finished."
echo "============================================"

