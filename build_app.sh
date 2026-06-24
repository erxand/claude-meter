#!/usr/bin/env bash
# Build "Claude Meter.app" with py2app and install it to /Applications.
#
# py2app produces a real bundle with a native launcher and its own identity
# (com.xander.claude-meter), so macOS treats it as a proper menu bar / accessory
# app. A hand-rolled wrapper around a symlinked venv python does NOT work — the
# process adopts python's bundle identity and the status item never renders.
#
# Usage:  ./build_app.sh
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
cd "$SRC"

# Build venv with runtime deps + py2app
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt py2app

# Build
rm -rf build dist
.venv/bin/python setup.py py2app

# Install to /Applications
rm -rf "/Applications/Claude Meter.app"
cp -R "dist/Claude Meter.app" "/Applications/Claude Meter.app"

echo
echo "Installed: /Applications/Claude Meter.app"
echo "Launch it:  open \"/Applications/Claude Meter.app\""
