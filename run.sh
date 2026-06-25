#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -f "./env/bin/python3" ]; then
  echo "ERROR: Virtual environment not found. Run ./setup.sh first."
  exit 1
fi

pkill Chromium 2>/dev/null || true
pkill -f "python3 app.py" 2>/dev/null || true

./env/bin/python3 app.py
