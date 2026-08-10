#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
elif [ -f "../requirements.txt" ]; then
    pip install -r ../requirements.txt
fi

# Force Playwright to embed browsers inside python packages directory so Render retains them at runtime
export PLAYWRIGHT_BROWSERS_PATH=0
playwright install
