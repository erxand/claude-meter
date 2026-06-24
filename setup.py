"""py2app build script.

Build a real, self-contained Claude Meter.app:

    python setup.py py2app

The resulting bundle has its own identity (com.xander.claude-meter) and a native
launcher stub, so macOS treats it as a proper menu bar (accessory) app — which a
hand-rolled wrapper around a symlinked venv python does not.
"""

from setuptools import setup

OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "Claude Meter",
        "CFBundleDisplayName": "Claude Meter",
        "CFBundleIdentifier": "com.xander.claude-meter",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": True,            # menu bar only, no dock icon
        "LSMinimumSystemVersion": "11.0",
        "NSHumanReadableCopyright": "MIT",
    },
    "packages": ["rumps", "browser_cookie3", "keyring", "certifi"],
    "includes": [
        "keyring.backends.macOS",
        "keyring.backends.chainer",
        "keyring.backends.fail",
    ],
}

setup(
    app=["claude_meter.py"],
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
