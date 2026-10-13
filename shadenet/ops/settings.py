"""Declarative registry of every operator-tunable setting, grouped by console tab.

Adding a setting = one Setting(...) line here; the console renders the control.
Other modules read values with settings.get("tab.key").

`wired=False` means the value is stored and editable but nothing reads it yet.
The console labels those "stored only" so nobody mistakes them for live
controls. Flip to True in the same change that makes the app honour it.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from shadenet.ops import now_iso, read_json, write_json

_FILE = "settings.json"


@dataclass(frozen=True)
class Setting:
    key: str                      # "<tab>.<name>"
    label: str
    type: str                     # bool | int | text | choice
    default: Any
    help: str = ""
    choices: tuple = ()
    min: int | None = None
    max: int | None = None
    dangerous: bool = False       # needs TOTP step-up to change
    wired: bool = False           # does the app read it yet?

    @property
    def tab(self) -> str:
        return self.key.split(".", 1)[0]


TABS = [
    {"id": "overview", "label": "Overview"},
    {"id": "logs", "label": "Logs"},
    {"id": "errors", "label": "Errors"},
    {"id": "metrics", "label": "Metrics"},
    {"id": "nightcal", "label": "NightCal"},
    {"id": "umwelt", "label": "Umwelt Horizons"},
    {"id": "serendipilyst", "label": "SerendipiLyst"},
    {"id": "steward", "label": "Stewards"},
    {"id": "chat", "label": "Chat"},
    {"id": "agegate", "label": "21+ Gate"},
    {"id": "accounts", "label": "Account Recovery"},
    {"id": "venues", "label": "Venue Succession"},
    {"id": "flags", "label": "Feature Flags"},
    {"id": "security", "label": "Security"},
    {"id": "opsteward", "label": "Operator Steward"},
    {"id": "audit", "label": "Audit Trail"},
]

SETTINGS: list[Setting] = [
    # NightCal
    Setting("nightcal.default_scope", "Default listing scope", "choice", "nights",
            "What the calendar shows before a visitor picks.", choices=("nights", "all")),
    Setting("nightcal.days_ahead", "Days ahead to publish", "int", 45, "Horizon for calendar + feeds.", min=7, max=180),
    Setting("nightcal.show_needs_review", "Show unreviewed events", "bool", False,
            "Publish low-confidence scraped events before an operator reviews them."),
    Setting("nightcal.search_enabled", "Site search", "bool", True, "Header search and /api/search."),
    # Umwelt Horizons
    Setting("umwelt.submissions_open", "Article/letter submissions open", "bool", True),
    Setting("umwelt.auto_publish", "Auto-publish newsroom cycle", "bool", False,
            "Publish newsroom drafts without an editor pass.", dangerous=True),
    Setting("umwelt.cycle_mock_mode", "Newsroom cycle in mock mode", "bool", True,
            "Run the newsroom pipeline without calling external models."),
    # SerendipiLyst
    Setting("serendipilyst.listings_open", "Accept new listings", "bool", True,
            "Closed = no new places on the sheet and no new offers. Live ones stay.", wired=True),
    Setting("serendipilyst.listing_ttl_days", "Listing lifetime (days)", "int", 30,
            "A place or offer not renewed in this many days drops off the sheet.", min=1, max=180, wired=True),
    Setting("serendipilyst.max_listings_per_steward", "Max live listings per Steward", "int", 5,
            "Places plus offers, counted across the Steward's flags and nodes.", min=1, max=100, wired=True),
    # Stewards
    Setting("steward.activation_open", "New Steward activation", "bool", True,
            "Pause to stop new Stewards being issued (existing ones keep working)."),
    Setting("steward.default_pacing", "Default pacing", "choice", "adaptive", choices=("adaptive", "calm", "eager")),
    Setting("steward.a2a_mail", "Agent-to-agent mail", "bool", True),
    Setting("steward.plus_ones", "+1 attendance tallies", "bool", True),
    # Chat
    Setting("chat.enabled", "Downtown Night Chat", "bool", True),
    Setting("chat.slow_mode_seconds", "Slow mode (seconds between posts)", "int", 0, min=0, max=600),
    # 21+ gate
    Setting("agegate.mode", "Gate mode", "choice", "enforce",
            "enforce = block unverified writes; monitor = allow but log; off = no gate.",
            choices=("enforce", "monitor", "off"), dangerous=True),
    Setting("agegate.challenge_ttl_seconds", "Challenge lifetime (seconds)", "int", 300, min=30, max=3600),
    # Account recovery
    Setting("accounts.recovery_open", "Accept recovery requests", "bool", True),
    Setting("accounts.recovery_delay_hours", "Recovery waiting period (hours)", "int", 24,
            "Time between approval and the account being handed over; the owner can cancel meanwhile.",
            min=0, max=336, dangerous=True, wired=True),
    Setting("accounts.notify_existing_devices", "Notify existing devices on recovery", "bool", True,
            "Gives the real owner a chance to cancel a fraudulent recovery during the waiting period."),
    # Venue succession
    Setting("venues.min_custodians", "Minimum custodians per venue", "int", 2,
            "Venues below this show as at-risk.", min=1, max=10, wired=True),
    Setting("venues.succession_delay_hours", "Succession waiting period (hours)", "int", 72, min=0, max=720,
            dangerous=True, wired=True),
    # Security
    Setting("security.api_rate_per_sec", "Public API sustained rate (req/s per IP)", "int", 1, min=1, max=100),
    Setting("security.submission_rate_per_min", "Write rate (per minute per IP)", "int", 30, min=1, max=600),
    Setting("security.maintenance_mode", "Maintenance mode", "bool", False,
            "Public site read-only; writes return 503.", dangerous=True),
]

_BY_KEY = {s.key: s for s in SETTINGS}

# Environment-backed values: shown read-only (they need a restart to change).
ENV_VISIBLE = ["NIGHTCAL_HOST", "NIGHTCAL_PORT", "NIGHTCAL_DB", "SHADENET_DOMAIN", "SHADENET_LOG_FILE",
               "SHADENET_OPS_ALLOW_CIDRS", "MATRIX_HOMESERVER_URL", "SHADENET_DEV_MODE"]
ENV_SECRET = ["NIGHTCAL_BEARER", "MATRIX_ACCESS_TOKEN", "CHAT_PSEUDONYM_SALT"]


def _stored() -> dict[str, Any]:
    return read_json(_FILE, {"values": {}, "history": []})


def get(key: str) -> Any:
    s = _BY_KEY[key]
    return _stored()["values"].get(key, s.default)


def coerce(s: Setting, raw: Any) -> Any:
    if s.type == "bool":
        if isinstance(raw, bool):
            return raw
        if str(raw).lower() in ("1", "true", "on", "yes"):
            return True
        if str(raw).lower() in ("0", "false", "off", "no"):
            return False
        raise ValueError(f"{s.key} expects on/off")
    if s.type == "int":
        v = int(raw)
        if (s.min is not None and v < s.min) or (s.max is not None and v > s.max):
            raise ValueError(f"{s.key} must be between {s.min} and {s.max}")
        return v
    if s.type == "choice":
        if raw not in s.choices:
            raise ValueError(f"{s.key} must be one of {', '.join(s.choices)}")
        return raw
    v = str(raw)
    if len(v) > 2000:
        raise ValueError(f"{s.key} is too long")
    return v


def lookup(key: str) -> Setting:
    if key not in _BY_KEY:
        raise KeyError(f"unknown setting {key!r}")
    return _BY_KEY[key]


def set_value(key: str, raw: Any, actor: str) -> dict:
    s = lookup(key)
    value = coerce(s, raw)
    data = _stored()
    old = data["values"].get(key, s.default)
    data["values"][key] = value
    data["history"] = (data.get("history", []) + [{"ts": now_iso(), "key": key, "old": old, "new": value, "by": actor}])[-500:]
    write_json(_FILE, data)
    return {"key": key, "old": old, "value": value}


def listing(tab: str = "") -> dict:
    values = _stored()["values"]
    rows = []
    for s in SETTINGS:
        if tab and s.tab != tab:
            continue
        row = asdict(s)
        row["choices"] = list(s.choices)
        row["value"] = values.get(s.key, s.default)
        row["modified"] = s.key in values
        rows.append(row)
    env = {k: os.environ.get(k, "") for k in ENV_VISIBLE}
    env.update({k: ("set" if os.environ.get(k) else "unset") for k in ENV_SECRET})
    return {"tabs": TABS, "settings": rows, "env": env}
