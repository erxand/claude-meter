#!/usr/bin/env bash
# Build "Claude Meter.app" — a real, double-clickable macOS menu bar app.
#
# The bundle carries its own Python venv (with all deps) in Contents/Resources,
# so once built it doesn't depend on this source folder. It does rely on the
# python3 used to create the venv staying installed (Homebrew python is fine).
#
# Usage:
#   ./build_app.sh                      # installs to /Applications
#   ./build_app.sh ~/Applications       # installs somewhere else
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-/Applications}"
APP="$DEST/Claude Meter.app"

echo "Building $APP …"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# App code
cp "$SRC/claude_meter.py" "$SRC/fetcher.py" "$APP/Contents/Resources/"

# Self-contained venv with the dependencies
python3 -m venv "$APP/Contents/Resources/venv"
"$APP/Contents/Resources/venv/bin/pip" install -q --upgrade pip
"$APP/Contents/Resources/venv/bin/pip" install -q -r "$SRC/requirements.txt"

# Launcher
cat > "$APP/Contents/MacOS/claude-meter" <<'SH'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
RES="$DIR/../Resources"
exec "$RES/venv/bin/python" "$RES/claude_meter.py"
SH
chmod +x "$APP/Contents/MacOS/claude-meter"

# Info.plist — LSUIElement hides the dock icon (menu bar only)
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Claude Meter</string>
  <key>CFBundleDisplayName</key><string>Claude Meter</string>
  <key>CFBundleIdentifier</key><string>com.xander.claude-meter</string>
  <key>CFBundleExecutable</key><string>claude-meter</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHumanReadableCopyright</key><string>MIT</string>
</dict>
</plist>
PLIST

# Ad-hoc codesign so macOS treats it as a stable identity (lets Keychain/Chrome
# decryption remember "Always Allow"). Harmless if codesign is unavailable.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "Done: $APP"
echo "Open it with:  open \"$APP\""
