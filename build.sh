#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
elif [ -f "../requirements.txt" ]; then
    pip install -r ../requirements.txt
fi

# Install Chromium browser binary (without requiring root/sudo permissions)
playwright install chromium
