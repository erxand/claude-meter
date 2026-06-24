# claude-meter

A dead-simple, self-contained macOS menu bar app that shows your Claude
**5-hour session** at a glance:

- the **% of the session you've used**, colored by how close you are
- how long until the session **resets** (and the exact reset time in the menu)

```
26% · 2h 25m           ← menu bar (the "26%" is colored)
─────────────────────────
Resets at 8:09 PM   (2h 25m left)
Used 26% of 5-hour session
███░░░░░░░  26%
─────────────────────────
Updated 1:44 PM
Refresh now
Set session key…
Quit
```

The percentage is **green under 50%, yellow 50–80%, red 80%+**.

## How it works

It talks to claude.ai directly — it does **not** depend on the original
[ClaudeMeter](https://github.com/eddmann/ClaudeMeter) app. The data flow is a
straight port of what ClaudeMeter does (see `fetcher.py`):

1. Get your `sessionKey` cookie for claude.ai — either a key you pasted (stored
   in the macOS Keychain) or read straight from your browser's cookies.
2. `GET https://claude.ai/api/organizations` → your org id.
3. `GET https://claude.ai/api/organizations/<org>/usage` → the 5-hour / weekly /
   Sonnet limits, each with `utilization` and `resets_at`.

A background thread fetches every 60s and writes `~/.claude-meter/state.json`;
the menu bar reads that file, so the UI never blocks on the network.

## Install

```bash
./build_app.sh
```

This builds **`/Applications/Claude Meter.app`** — a real, double-clickable menu
bar app with its own bundled Python venv (so it doesn't depend on this source
folder). Then:

```bash
open "/Applications/Claude Meter.app"
```

A menu bar item appears; there's no dock icon.

> Prefer not to build an app? `./run.sh` runs it straight from this folder
> (creates a local `.venv` on first run). Same behavior, just from a terminal.

## Getting a session key

The app tries to read the `sessionKey` cookie from your browsers automatically
(Chrome, Chromium, Brave, Edge, Arc, Vivaldi, Opera, Safari, Firefox). For
Chrome-family browsers macOS will ask permission to read the “Chrome Safe
Storage” key the first time — click **Always Allow**.

If auto-detection doesn't work, set it manually:

1. In your browser open **claude.ai** while logged in.
2. DevTools → **Application → Cookies → https://claude.ai** → copy the value of
   the `sessionKey` cookie (it starts with `sk-ant-`).
3. Menu bar → **Set session key…** → paste → Save.

Clearing the field in that dialog forgets the stored key and goes back to using
browser cookies.

## Start automatically at login

Drag **Claude Meter.app** into **System Settings → General → Login Items**, or:

```bash
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/Claude Meter.app", hidden:true}'
```

## Credits

Modeled on [eddmann/ClaudeMeter](https://github.com/eddmann/ClaudeMeter) (MIT) —
the API flow and headers come from its source. This is a personal, stripped-down
take focused on just the 5-hour session.

## License

MIT
