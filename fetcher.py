#!/usr/bin/env python3
"""fetcher — talk to claude.ai directly so claude-meter needs nothing else.

This is a Python port of what the original ClaudeMeter does:

  1. Get the `sessionKey` cookie (sk-ant-...) for claude.ai — either a key you
     pasted (stored in the macOS Keychain) or, failing that, read straight from
     your browser's cookies.
  2. GET https://claude.ai/api/organizations            -> first org's uuid
  3. GET https://claude.ai/api/organizations/<uuid>/usage
        -> { five_hour, seven_day, seven_day_sonnet } each {utilization, resets_at}

The result is normalized to the same shape the original cached to usage.json,
so the menu bar display code is unchanged.
"""

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# A py2app-bundled Python has no CA bundle of its own, so default cert
# verification fails. Point it at certifi's bundle when available.
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001 — fall back to the system default
    _SSL_CONTEXT = ssl.create_default_context()

DATA_DIR = os.path.expanduser("~/.claude-meter")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

KEYRING_SERVICE = "com.xander.claude-meter"
KEYRING_ACCOUNT = "session-key"

API_BASE = "https://claude.ai/api"

# Browser-like headers, copied from the original, to get past Cloudflare.
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://claude.ai",
    "Origin": "https://claude.ai",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

# Order to try browsers in when reading the cookie automatically.
_BROWSER_ORDER = ["chrome", "chromium", "brave", "edge", "arc", "vivaldi", "opera", "safari", "firefox"]

# Window lengths used as a fallback if the API omits a reset time.
_SESSION_WINDOW = 5 * 60 * 60
_WEEKLY_WINDOW = 7 * 24 * 60 * 60


class AuthError(Exception):
    """No valid session key / the key was rejected (401)."""


class FetchError(Exception):
    """Network or API problem that isn't an auth failure."""


# ---------------------------------------------------------------------------
# Session key
# ---------------------------------------------------------------------------

def _extract_key(raw):
    """Accept a bare `sk-ant-...` value or a Cookie string containing one."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("sk-ant-"):
        return raw
    m = re.search(r"(?i)(?:^|[;\s])sessionKey\s*=\s*([^;\s'\"]+)", raw)
    return m.group(1).strip() if m else None


def manual_key():
    """A key you pasted, stored in the Keychain (or None)."""
    try:
        import keyring
        return _extract_key(keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT))
    except Exception:
        return None


def set_manual_key(value):
    """Validate a pasted key and store it in the Keychain. Returns the key."""
    import keyring
    key = _extract_key(value)
    if not key or not key.startswith("sk-ant-") or len(key) <= 10:
        raise ValueError("That doesn't look like a session key (it should start with sk-ant-).")
    keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, key)
    return key


def clear_manual_key():
    """Forget the pasted key so we fall back to browser cookies."""
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
    except Exception:
        pass


def browser_key():
    """Read the claude.ai `sessionKey` cookie from a local browser (or None)."""
    try:
        import browser_cookie3 as bc
    except Exception:
        return None
    for name in _BROWSER_ORDER:
        loader = getattr(bc, name, None)
        if loader is None:
            continue
        try:
            jar = loader(domain_name="claude.ai")
        except Exception:
            continue
        for cookie in jar:
            if cookie.name == "sessionKey" and cookie.value:
                key = _extract_key(cookie.value)
                if key:
                    return key
    return None


def get_session_key():
    """Pasted key wins; otherwise pull it from the browser."""
    return manual_key() or browser_key()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _api_get(path, key):
    req = urllib.request.Request(
        API_BASE + path, headers={**_HEADERS, "Cookie": f"sessionKey={key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # claude.ai returns 403 (account_session_invalid) for a bad/expired
        # session, and 401 for missing auth — both are auth failures.
        if e.code in (401, 403):
            raise AuthError("Session key invalid or expired") from e
        raise FetchError(f"HTTP {e.code} from {path}") from e
    except urllib.error.URLError as e:
        raise FetchError(str(getattr(e, "reason", e))) from e


def _limit(d, window):
    util = round((d or {}).get("utilization") or 0)
    reset_at = (d or {}).get("resets_at")
    if not reset_at:
        fallback = datetime.now(timezone.utc) + timedelta(seconds=window)
        reset_at = fallback.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"utilization": util, "reset_at": reset_at}


def fetch_usage():
    """Return usage normalized to the original usage.json shape. Raises on failure."""
    key = get_session_key()
    if not key:
        raise AuthError("No session key found")

    orgs = _api_get("/organizations", key)
    if not orgs:
        raise FetchError("No organizations for this account")
    org_id = orgs[0]["uuid"]

    data = _api_get(f"/organizations/{org_id}/usage", key)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "last_updated": now,
        "session_usage": _limit(data.get("five_hour"), _SESSION_WINDOW),
        "weekly_usage": _limit(data.get("seven_day"), _WEEKLY_WINDOW),
    }
    if data.get("seven_day_sonnet"):
        payload["sonnet_usage"] = _limit(data["seven_day_sonnet"], _WEEKLY_WINDOW)
    return payload


# ---------------------------------------------------------------------------
# State file (decouples the network from the UI)
# ---------------------------------------------------------------------------

def read_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_state(payload=None, error=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    state = read_state() or {}
    state["ok"] = error is None
    state["checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if payload is not None:
        state["usage"] = payload          # keep last good usage around on errors
        state.pop("error", None)
    if error is not None:
        state["error"] = error
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def run_once():
    """Fetch and persist. Returns True on success. Never raises."""
    try:
        _write_state(payload=fetch_usage())
        return True
    except AuthError as e:
        _write_state(error=f"auth: {e}")
    except Exception as e:  # noqa: BLE001 — the loop must keep going
        _write_state(error=str(e))
    return False


if __name__ == "__main__":
    # Handy for debugging: `python fetcher.py`
    print(json.dumps(fetch_usage(), indent=2))
