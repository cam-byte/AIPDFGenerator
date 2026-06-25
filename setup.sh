#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "==> Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  echo "ERROR: Homebrew not found. Install it first: https://brew.sh"
  exit 1
fi

echo "==> Installing poppler (pdf2image dependency)..."
brew install poppler

echo "==> Checking Chromium..."
if [ ! -f "/Applications/Chromium.app/Contents/MacOS/Chromium" ]; then
  echo "WARNING: Chromium not found at /Applications/Chromium.app"
  echo "  Download it from https://www.chromium.org/getting-involved/download-chromium/"
  echo "  Or the app will still work — just open http://127.0.0.1:5000 manually in any browser."
fi

echo "==> Creating Python virtual environment..."
python3 -m venv env

echo "==> Installing Python dependencies..."
./env/bin/pip install --upgrade pip -q
./env/bin/pip install -r requirements.txt

echo ""
echo "Done. Run the app with: ./run.sh"
echo "Then enter your Anthropic API key in the Settings panel."
