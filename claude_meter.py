#!/usr/bin/env python3
"""claude-meter — a dead-simple macOS menu bar readout of your Claude 5-hour session.

It reads ~/.claudemeter/usage.json (kept fresh by the original ClaudeMeter app:
https://github.com/eddmann/ClaudeMeter) and shows two things:

  • the exact wall-clock time your 5-hour session resets
  • the % of that session you've used

The menu bar shows e.g.  🟢 26% · 8:09 PM
The dropdown shows the countdown, a little usage bar, and the last-updated time.
"""

import json
import os
from datetime import datetime, timezone

import rumps

USAGE_FILE = os.path.expanduser("~/.claudemeter/usage.json")
REFRESH_SECONDS = 30  # how often we re-read the file and tick the countdown


# ---------------------------------------------------------------------------
# Pure formatting helpers (no GUI) so the display logic is easy to reason about.
# ---------------------------------------------------------------------------

def _fmt_clock(dt_local):
    """8:09 PM — strip the leading zero from the hour."""
    return dt_local.strftime("%-I:%M %p")


def _fmt_countdown(seconds):
    """A short '2h 25m' / '14m' / 'now'."""
    mins = int(seconds // 60)
    if mins <= 0:
        return "now"
    h, m = divmod(mins, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def compute_display(data, now=None):
    """Turn the raw usage.json dict into everything the menu needs.

    Returns a dict with: title, reset_line, used_line, bar_line, updated_line.
    """
    now = now or datetime.now(timezone.utc)
    session = data["session_usage"]

    pct = int(round(session["utilization"]))
    reset_utc = datetime.fromisoformat(session["reset_at"])
    reset_local = reset_utc.astimezone()
    countdown = _fmt_countdown((reset_utc - now).total_seconds())

    dot = "🟢" if pct < 75 else "🟡" if pct < 90 else "🔴"

    filled = round(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)

    updated = datetime.fromisoformat(data["last_updated"]).astimezone()

    return {
        "title": f"{dot} {pct}% · {_fmt_clock(reset_local)}",
        "reset_line": f"Resets at {_fmt_clock(reset_local)}   ({countdown} left)",
        "used_line": f"Used {pct}% of 5-hour session",
        "bar_line": f"{bar}  {pct}%",
        "updated_line": f"Updated {_fmt_clock(updated)}",
    }


# ---------------------------------------------------------------------------
# Menu bar app
# ---------------------------------------------------------------------------

class ClaudeMeter(rumps.App):
    def __init__(self):
        super().__init__("Claude Meter", title="⏳ …", quit_button=None)
        self.reset_item = rumps.MenuItem("")
        self.used_item = rumps.MenuItem("")
        self.bar_item = rumps.MenuItem("")
        self.updated_item = rumps.MenuItem("")
        self.menu = [
            self.reset_item,
            self.used_item,
            self.bar_item,
            None,
            self.updated_item,
            None,
            rumps.MenuItem("Refresh now", callback=self.refresh),
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self.refresh(None)

    @rumps.timer(REFRESH_SECONDS)
    def _tick(self, _):
        self.refresh(None)

    def refresh(self, _):
        try:
            with open(USAGE_FILE) as f:
                data = json.load(f)
            view = compute_display(data)
        except FileNotFoundError:
            self.title = "⚪ no data"
            self.reset_item.title = "No ~/.claudemeter/usage.json found"
            self.used_item.title = "Is the ClaudeMeter app running?"
            self.bar_item.title = ""
            self.updated_item.title = ""
            return
        except Exception as e:  # noqa: BLE001 — keep the menu bar alive no matter what
            self.title = "⚠️ error"
            self.reset_item.title = f"Could not read usage: {e}"
            self.used_item.title = ""
            self.bar_item.title = ""
            self.updated_item.title = ""
            return

        self.title = view["title"]
        self.reset_item.title = view["reset_line"]
        self.used_item.title = view["used_line"]
        self.bar_item.title = view["bar_line"]
        self.updated_item.title = view["updated_line"]


if __name__ == "__main__":
    ClaudeMeter().run()
