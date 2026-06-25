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

echo "==> Creating SchemaForm.app on Desktop..."
cat <<APPLESCRIPT | osacompile -o ~/Desktop/SchemaForm.app
on launchApp()
    tell application "System Events"
        if exists (processes whose name is "Chromium") then
            do shell script "pkill Chromium 2>/dev/null"
        end if
        if exists (processes whose name contains "Python") then
            do shell script "pkill -f 'python3 app.py' 2>/dev/null"
        end if
    end tell
    delay 1
    do shell script "cd $DIR && ./env/bin/python3 app.py > /dev/null 2>&1 &"
end launchApp

on run
    launchApp()
end run

on reopen
    launchApp()
end reopen
APPLESCRIPT

echo "==> Setting app icon..."
if [ -f "$DIR/logo.png" ]; then
  ICONSET=$(mktemp -d)
  sips -z 16 16     "$DIR/logo.png" --out "$ICONSET/icon_16x16.png"     &>/dev/null
  sips -z 32 32     "$DIR/logo.png" --out "$ICONSET/icon_16x16@2x.png"  &>/dev/null
  sips -z 32 32     "$DIR/logo.png" --out "$ICONSET/icon_32x32.png"      &>/dev/null
  sips -z 64 64     "$DIR/logo.png" --out "$ICONSET/icon_32x32@2x.png"  &>/dev/null
  sips -z 128 128   "$DIR/logo.png" --out "$ICONSET/icon_128x128.png"    &>/dev/null
  sips -z 256 256   "$DIR/logo.png" --out "$ICONSET/icon_128x128@2x.png" &>/dev/null
  sips -z 256 256   "$DIR/logo.png" --out "$ICONSET/icon_256x256.png"    &>/dev/null
  sips -z 512 512   "$DIR/logo.png" --out "$ICONSET/icon_256x256@2x.png" &>/dev/null
  sips -z 512 512   "$DIR/logo.png" --out "$ICONSET/icon_512x512.png"    &>/dev/null
  mv "$ICONSET" "${ICONSET}.iconset"
  iconutil -c icns "${ICONSET}.iconset" --output /tmp/schemaform.icns 2>/dev/null && \
    cp /tmp/schemaform.icns ~/Desktop/SchemaForm.app/Contents/Resources/applet.icns && \
    touch ~/Desktop/SchemaForm.app
  rm -rf "${ICONSET}.iconset" /tmp/schemaform.icns
fi

echo ""
echo "Done! SchemaForm.app is on your Desktop."
echo "Open it to launch the app, then enter your Anthropic API key in the Settings panel."
