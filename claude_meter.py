#!/usr/bin/env python3
"""claude-meter — a dead-simple macOS menu bar readout of your Claude 5-hour session.

It reads ~/.claudemeter/usage.json (kept fresh by the original ClaudeMeter app:
https://github.com/eddmann/ClaudeMeter) and shows two things:

  • the % of your 5-hour session you've used — colored green / yellow / red
  • how long until the session resets (countdown)

The menu bar shows e.g.  29% · 2h 9m   with the "29%" colored:
green under 50%, yellow 50–80%, red 80%+.
The dropdown shows the exact reset time, a usage bar, and the last-updated time.
"""

import json
import os
from datetime import datetime, timezone

import rumps
from AppKit import (
    NSColor,
    NSForegroundColorAttributeName,
    NSMutableAttributedString,
)

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
    """Turn the raw usage.json dict into everything the menu needs."""
    now = now or datetime.now(timezone.utc)
    session = data["session_usage"]

    pct = int(round(session["utilization"]))
    reset_utc = datetime.fromisoformat(session["reset_at"])
    reset_local = reset_utc.astimezone()
    countdown = _fmt_countdown((reset_utc - now).total_seconds())

    filled = round(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)

    updated = datetime.fromisoformat(data["last_updated"]).astimezone()

    pct_str = f"{pct}%"
    return {
        "pct": pct,
        "pct_str": pct_str,
        "title": f"{pct_str} · {countdown}",
        "reset_line": f"Resets at {_fmt_clock(reset_local)}   ({countdown} left)",
        "used_line": f"Used {pct}% of 5-hour session",
        "bar_line": f"{bar}  {pct}%",
        "updated_line": f"Updated {_fmt_clock(updated)}",
    }


def _color_for(pct):
    """Green under 50%, yellow 50–80%, red 80%+."""
    if pct < 50:
        return NSColor.systemGreenColor()
    if pct < 80:
        return NSColor.systemYellowColor()
    return NSColor.systemRedColor()


# ---------------------------------------------------------------------------
# Menu bar app
# ---------------------------------------------------------------------------

class ClaudeMeter(rumps.App):
    def __init__(self):
        super().__init__("Claude Meter", title="…", quit_button=None)
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
        # Re-read on a timer. A quick one-shot paints the colored title shortly
        # after launch (the status item button doesn't exist until the run loop
        # is up, so the __init__ refresh below can only fill the dropdown).
        self._timer = rumps.Timer(self.refresh, REFRESH_SECONDS)
        self._timer.start()
        self._boot = rumps.Timer(self._boot_paint, 0.5)
        self._boot.start()
        self.refresh(None)

    def _boot_paint(self, sender):
        sender.stop()
        self.refresh(sender)

    def _set_bar_title(self, text, pct_str, pct):
        """Set the menu bar title with just the percentage colored."""
        try:
            button = self._nsapp.nsstatusitem.button()
        except AttributeError:
            button = None
        if button is None:
            self.title = text  # run loop not up yet — plain fallback
            return
        attr = NSMutableAttributedString.alloc().initWithString_(text)
        attr.addAttribute_value_range_(
            NSForegroundColorAttributeName, _color_for(pct), (0, len(pct_str))
        )
        button.setAttributedTitle_(attr)

    def refresh(self, _):
        try:
            with open(USAGE_FILE) as f:
                data = json.load(f)
            view = compute_display(data)
        except FileNotFoundError:
            self.title = "no data"
            self.reset_item.title = "No ~/.claudemeter/usage.json found"
            self.used_item.title = "Is the ClaudeMeter app running?"
            self.bar_item.title = ""
            self.updated_item.title = ""
            return
        except Exception as e:  # noqa: BLE001 — keep the menu bar alive no matter what
            self.title = "error"
            self.reset_item.title = f"Could not read usage: {e}"
            self.used_item.title = ""
            self.bar_item.title = ""
            self.updated_item.title = ""
            return

        self._set_bar_title(view["title"], view["pct_str"], view["pct"])
        self.reset_item.title = view["reset_line"]
        self.used_item.title = view["used_line"]
        self.bar_item.title = view["bar_line"]
        self.updated_item.title = view["updated_line"]


if __name__ == "__main__":
    ClaudeMeter().run()
