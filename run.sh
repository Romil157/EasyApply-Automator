#!/usr/bin/env bash

# Change to the directory where this script is located
cd "$(dirname "$0")"

echo "============================================"
echo "   EasyApply Automator - Setup & Run"
echo "============================================"
echo

# Check if python3 is installed
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is not installed or not in PATH."
    echo "Please install Python 3."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv venv
    echo "      Done."
else
    echo "[1/3] Virtual environment already exists. Skipping."
fi

# Install dependencies using python -m pip
echo "[2/3] Installing/verifying dependencies..."
./venv/bin/python3 -m pip install -r requirements.txt
echo "      Done."

# Run the bot
echo "[3/3] Starting the bot..."
echo
echo "============================================"
./venv/bin/python3 easy_apply_bot.py

echo
echo "============================================"
echo "   Bot has stopped."
echo "============================================"
