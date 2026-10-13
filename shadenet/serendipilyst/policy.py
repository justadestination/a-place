"""Operator limits on the sheet, read from the ops console settings.

- ``serendipilyst.listings_open``: when closed, nothing new goes up.
- ``serendipilyst.max_listings_per_steward``: places plus offers per Steward.
- ``serendipilyst.listing_ttl_days``: a place or offer not renewed drops off.

A listing is a listed place (personal flag or node) or a live offer
(personal offer or business flag). Renewing means saving it again.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from shadenet.serendipilyst.store import FlagError, FlagStore

_DEFAULTS = {
    "serendipilyst.listings_open": True,
    "serendipilyst.listing_ttl_days": 30,
    "serendipilyst.max_listings_per_steward": 5,
}


def setting(key: str) -> Any:
    try:
        from shadenet.ops import settings
        return settings.get(key)
    except Exception:  # the package also runs without the ops console
        return _DEFAULTS[key]


def live_since() -> str:
    """Listings stamped before this are past their lifetime."""
    days = int(setting("serendipilyst.listing_ttl_days"))
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def fresh(stamp: str | None) -> bool:
    return bool(stamp) and str(stamp) >= live_since()


def count_live(store: FlagStore, controller: str) -> int:
    since = live_since()
    places = store.query_one(
        """
        SELECT
          (SELECT COUNT(*) FROM personal_flags
            WHERE owner = ? AND status = 'active' AND listed = 1 AND listed_at >= ?)
        + (SELECT COUNT(*) FROM personal_flags
            WHERE owner = ? AND status = 'active' AND offer_title IS NOT NULL AND offered_at >= ?)
        + (SELECT COUNT(*) FROM business_nodes
            WHERE controller = ? AND status = 'active' AND listed = 1 AND listed_at >= ?)
        + (SELECT COUNT(*) FROM business_flags f JOIN business_nodes n ON n.id = f.node_id
            WHERE n.controller = ? AND f.status = 'active' AND n.status = 'active' AND f.updated_at >= ?)
        AS live
        """,
        (controller, since) * 4,
    )
    return int(places["live"]) if places else 0


def admit(store: FlagStore, controller: str, *, adding: int) -> None:
    """Refuse a write that would add ``adding`` live listings past the limits."""
    if adding <= 0:
        return
    if not bool(setting("serendipilyst.listings_open")):
        raise FlagError("listings_closed", "The sheet isn't taking new listings right now.")
    limit = int(setting("serendipilyst.max_listings_per_steward"))
    if count_live(store, controller) + adding > limit:
        raise FlagError(
            "limit_reached",
            f"That's {limit} live listings already. Pull one before you put up another.",
        )
