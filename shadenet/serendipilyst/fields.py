"""Field checks shared by every record in the package.

``KEEP`` marks a field the write left out. A left-out field keeps its
stored value. An empty string or empty list clears it.
"""

from __future__ import annotations

import re
from typing import Any

from shadenet.serendipilyst.store import FlagError

KEEP: Any = type("Keep", (), {"__repr__": lambda self: "KEEP", "__bool__": lambda self: False})()

SENTENCE_LIMIT = 160
_A2A = re.compile(r"^a2a://agent/[A-Za-z0-9_.:-]{1,80}$")
_TAG = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
# A dot between two digits is a decimal point, not the end of a sentence.
_STOP = re.compile(r"(?<!\d)[.!?]|[.!?](?!\d)")


# Payload names the command engine accepts, mapped to the names the records use.
ALIASES = {
    "displayName": "display_name", "counterpartName": "counterpart_name",
    "offerTitle": "offer_title", "offerBody": "offer_body", "linkPostings": "link_postings",
    "placeId": "place_id", "goodAt": "good_at", "venueId": "venue_id", "nodeId": "node_id",
    "flagId": "flag_id", "roomId": "room_id", "obligationId": "obligation_id", "id": "flag_id",
}


def canon(payload: dict[str, Any]) -> dict[str, Any]:
    return {ALIASES.get(key, key): value for key, value in payload.items()}


def given(value: Any) -> bool:
    return value is not KEEP


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value is KEEP:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def actor(value: str) -> str:
    """Only a Steward acts. A relay address can receive, never write."""
    if not _A2A.match(value or ""):
        raise FlagError("scope_denied", "actor must be an a2a://agent/ address")
    return value


def text(value: Any, label: str, limit: int, *, required: bool = False) -> str:
    said = str(value or "").strip()
    if required and not said:
        raise FlagError("schema_invalid", f"{label} is required")
    if len(said) > limit:
        raise FlagError("schema_invalid", f"{label} is longer than {limit} characters")
    return said


def strings(values: Any, label: str, limit: int, item_limit: int) -> list[str]:
    if not values:
        return []
    if not isinstance(values, list):
        raise FlagError("schema_invalid", f"{label} must be a list")
    out: list[str] = []
    for raw in values:
        item = str(raw).strip()
        if not item:
            continue
        if len(item) > item_limit:
            raise FlagError("schema_invalid", f"{label} entry is too long")
        if item not in out:
            out.append(item)
    if len(out) > limit:
        raise FlagError("schema_invalid", f"at most {limit} {label}")
    return out


def skills(values: Any) -> list[str]:
    """Lowercase tags, leading ``#`` dropped, duplicates removed."""
    tags: list[str] = []
    for raw in strings(values, "skills", 12, 32):
        tag = raw.lstrip("#").lower()
        if not _TAG.fullmatch(tag):
            raise FlagError("schema_invalid", f"skill tag {raw!r} is not a short label")
        if tag not in tags:
            tags.append(tag)
    return tags


def one_sentence(value: Any, *, what: str = "an intent") -> str:
    """One sentence, at most 160 characters. ``1.5`` is a number, not two sentences."""
    said = " ".join(str(value or "").strip().strip("\"'").split())
    if not said:
        raise FlagError("schema_invalid", f"{what} needs a sentence")
    if len(said) > SENTENCE_LIMIT:
        raise FlagError("schema_invalid", f"that sentence is longer than {SENTENCE_LIMIT} characters")
    stops = [match.start() for match in _STOP.finditer(said)]
    if len(stops) > 1 or (stops and stops[-1] != len(said) - 1):
        raise FlagError("schema_invalid", "one sentence")
    return said


# Contact and payment details belong in the inbox, never on a public record.
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<![\w.])\+?\(?\d(?:[\s().-]*\d){9,14}(?![\w.])")
_PLAIN_NUMBER = re.compile(r"^\s*\d*\.?\d+\s*$")
_XMR = re.compile(r"\b[48][1-9A-HJ-NP-Za-km-z]{94}(?:[1-9A-HJ-NP-Za-km-z]{11})?\b")
_FORBIDDEN_KEYS = {
    "price", "fee", "fees", "escrow", "payment", "currency", "stripe",
    "legalname", "email", "phone", "phonenumber", "wallet", "address_xmr",
}


def _key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def leaks(value: Any) -> str | None:
    """Name the first payment or contact detail found, or None.

    Keys are compared without case or separators, so ``Email`` and
    ``phone_number`` are caught. Text is scanned for mail addresses, phone
    numbers, and Monero addresses.
    """
    if isinstance(value, dict):
        for name, item in value.items():
            if _key(str(name)) in _FORBIDDEN_KEYS:
                return "payment or legal-identity field"
            found = leaks(item)
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = leaks(item)
            if found:
                return found
        return None
    if isinstance(value, str):
        if _PLAIN_NUMBER.match(value):
            return None  # an amount like 0.0000000000001 is not a phone number
        if _EMAIL.search(value):
            return "mail address"
        if _XMR.search(value):
            return "wallet address"
        if _PHONE.search(value):
            return "phone number"
    return None
