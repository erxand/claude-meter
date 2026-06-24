#!/usr/bin/env python3
"""claude-meter — a dead-simple, self-contained macOS menu bar readout of your
Claude 5-hour session.

It fetches usage straight from claude.ai (see fetcher.py) — no dependency on the
original ClaudeMeter app — and shows:

  • the % of your 5-hour session you've used — colored green / yellow / red
  • how long until the session resets (countdown)

Menu bar looks like:  29% · 2h 9m   with "29%" colored
(green under 50%, yellow 50–80%, red 80%+). The dropdown shows the exact reset
time, a usage bar, and when it last refreshed.
"""

import threading
from datetime import datetime, timezone

import rumps
from AppKit import (
    NSColor,
    NSForegroundColorAttributeName,
    NSMutableAttributedString,
)

import fetcher

REPAINT_SECONDS = 15   # how often the menu bar re-renders (cheap, local)
FETCH_SECONDS = 60     # how often we hit claude.ai (matches the original's minimum)


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


def compute_display(usage, now=None):
    """Turn a usage payload into everything the menu needs."""
    now = now or datetime.now(timezone.utc)
    session = usage["session_usage"]

    pct = int(round(session["utilization"]))
    reset_utc = datetime.fromisoformat(session["reset_at"])
    reset_local = reset_utc.astimezone()
    countdown = _fmt_countdown((reset_utc - now).total_seconds())

    filled = round(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)

    updated = datetime.fromisoformat(usage["last_updated"]).astimezone()

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
        self.note_item = rumps.MenuItem("")  # errors / hints; hidden when empty
        self.menu = [
            self.reset_item,
            self.used_item,
            self.bar_item,
            None,
            self.updated_item,
            self.note_item,
            None,
            rumps.MenuItem("Refresh now", callback=self.refresh_now),
            rumps.MenuItem("Set session key…", callback=self.set_key),
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        # Background thread does the network; the UI only ever reads the local
        # state file, so the menu never blocks on claude.ai.
        self._wake = threading.Event()
        self._fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._fetch_thread.start()

        # Timers: a quick one-shot to paint as soon as the run loop is up, then
        # a steady repaint to tick the countdown and pick up fresh fetches.
        self._timer = rumps.Timer(self.repaint, REPAINT_SECONDS)
        self._timer.start()
        self._boot = rumps.Timer(self._boot_paint, 0.5)
        self._boot.start()
        self.repaint(None)

    # -- background fetching ------------------------------------------------

    def _fetch_loop(self):
        while True:
            fetcher.run_once()
            self._wake.wait(timeout=FETCH_SECONDS)
            self._wake.clear()

    def refresh_now(self, _):
        self._wake.set()  # wake the fetch loop immediately

    # -- painting -----------------------------------------------------------

    def _boot_paint(self, sender):
        sender.stop()
        self.repaint(sender)

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

    def repaint(self, _):
        state = fetcher.read_state()

        if not state or not state.get("usage"):
            # Nothing fetched yet, or only an error so far.
            err = (state or {}).get("error")
            needs_key = err and ("No session key" in err or err.startswith("auth"))
            self.title = "⚠ key" if needs_key else "…"
            self.reset_item.title = (
                "No session key yet — choose “Set session key…” below"
                if needs_key else "Fetching usage from claude.ai…"
            )
            self.used_item.title = ""
            self.bar_item.title = ""
            self.updated_item.title = ""
            self.note_item.title = self._hint_for(err) if err else ""
            return

        view = compute_display(state["usage"])
        self._set_bar_title(view["title"], view["pct_str"], view["pct"])
        self.reset_item.title = view["reset_line"]
        self.used_item.title = view["used_line"]
        self.bar_item.title = view["bar_line"]
        self.updated_item.title = view["updated_line"]

        if state.get("ok"):
            self.note_item.title = ""
        else:
            # Showing stale-but-last-known data; flag why it isn't updating.
            self.note_item.title = self._hint_for(state.get("error"))

    @staticmethod
    def _hint_for(error):
        error = error or ""
        if "No session key" in error:
            return "⚠️ No session key — open “Set session key…”"
        if error.startswith("auth"):
            return "⚠️ Session expired — open “Set session key…”"
        return f"⚠️ {error}"

    # -- session key --------------------------------------------------------

    def set_key(self, _):
        window = rumps.Window(
            message=(
                "Paste your claude.ai sessionKey (starts with sk-ant-).\n\n"
                "Leave it blank and click Save to forget a stored key and read "
                "it from your browser cookies instead."
            ),
            title="Claude Meter — Session Key",
            default_text="",
            ok="Save",
            cancel="Cancel",
            dimensions=(360, 24),
        )
        response = window.run()
        if not response.clicked:
            return
        text = response.text.strip()
        try:
            if text:
                fetcher.set_manual_key(text)
                rumps.notification("Claude Meter", "Session key saved", "Refreshing…")
            else:
                fetcher.clear_manual_key()
                rumps.notification("Claude Meter", "Stored key cleared", "Using browser cookies.")
        except Exception as e:  # noqa: BLE001
            rumps.alert("Couldn't save key", str(e))
            return
        self.refresh_now(None)


if __name__ == "__main__":
    ClaudeMeter().run()
