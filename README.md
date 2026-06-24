# claude-meter

A dead-simple macOS menu bar readout of your Claude **5-hour session**. It shows
exactly two things:

- the **exact wall-clock time** your session resets
- the **% of the session you've used**

```
🟢 26% · 2h 25m        ← menu bar
─────────────────────────
Resets at 8:09 PM   (2h 25m left)
Used 26% of 5-hour session
███░░░░░░░  26%
─────────────────────────
Updated 1:44 PM
Refresh now
Quit
```

The menu bar dot is 🟢 under 75%, 🟡 under 90%, 🔴 at/above 90%.

## How it works

This is intentionally tiny. It does **not** talk to Claude's API or scrape any
cookies. Instead it piggybacks on the excellent
[ClaudeMeter](https://github.com/eddmann/ClaudeMeter) by Edd Mann, which already
runs in the background and keeps `~/.claudemeter/usage.json` up to date:

```json
{
  "session_usage": { "reset_at": "2026-06-24T20:09:59Z", "utilization": 26 }
}
```

claude-meter just reads that file every 30 seconds and renders the session info
the way I want it. So you need the original ClaudeMeter app installed and running.

## Run

```bash
./run.sh
```

First run creates a local `.venv` and installs [`rumps`](https://github.com/jaredks/rumps).
After that it just launches. A menu bar item appears; there's no dock icon.

## Start automatically at login (optional)

Create `~/Library/LaunchAgents/com.xander.claude-meter.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.xander.claude-meter</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/xander/other-code/claude-meter/run.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
```

Then `launchctl load ~/Library/LaunchAgents/com.xander.claude-meter.plist`.

## Credits

Usage data and the `~/.claudemeter/usage.json` format come from
[eddmann/ClaudeMeter](https://github.com/eddmann/ClaudeMeter) (MIT). This is just
a personal, stripped-down UI on top of it.

## License

MIT
