"""American Traditional flash for a public flag.

The look is the TacksForSnacks default: bold black ink, crimson, burnt rust,
gold, and parchment. A person can name one part ("paint it black") or set
field, charge, motto, line, ribbon, and fly. The Synapse homeserver, the
Matrix room, and the tackbot's kick and ban commands are not part of this
package. The Steward speaks for the flag.

A flag is on the WorldSum sheet only when it is listed, and a listed flag
names one place from ``web/js/data/worldsum.js``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shadenet.serendipilyst.intents import parse_profile_clause
from shadenet.serendipilyst.store import FlagError

# Keep this set identical to PLACES in web/js/data/worldsum.js.
PLACES = frozenset({
    "square",
    "rail",
    "dark-pool",
    "lot",
    "north-gate",
    "far-lake",
    "long-water",
    "narrows",
    "three-pools",
    "east-water",
})

FIELDS = frozenset({"crimson", "rust", "gold", "ink", "parchment"})
CHARGES = frozenset({"dagger", "anchor", "acorn", "rose", "none"})
LINES = frozenset({"heavy", "fine"})
FLIES = frozenset({"swallowtail", "notched", "banner"})
MOTTO_LIMIT = 24
ORDER_LIMIT = 200

# Longer phrases first. "the square" is the courthouse, not the banner fly.
_PLACE_ALIASES = (
    ("courthouse square", "square"),
    ("railroad square", "rail"),
    ("dark pool", "dark-pool"),
    ("north gate", "north-gate"),
    ("far lake", "far-lake"),
    ("long water", "long-water"),
    ("three pools", "three-pools"),
    ("east water", "east-water"),
    ("the narrows", "narrows"),
    ("narrows", "narrows"),
    ("the lot", "lot"),
    ("the square", "square"),
    ("the rail", "rail"),
)
_PLACE_NAMES = {
    "square": "Courthouse Square",
    "rail": "Railroad Square",
    "dark-pool": "Dark Pool",
    "lot": "The Lot",
    "north-gate": "North Gate",
    "far-lake": "Far Lake",
    "long-water": "Long Water",
    "narrows": "The Narrows",
    "three-pools": "Three Pools",
    "east-water": "East Water",
}
_COLORS = (
    ("rust", ("burnt rust", "rust", "orange"), "Burnt rust. Heavy, and it holds."),
    ("crimson", ("crimson", "red"), "Crimson. It reads from the trail."),
    ("parchment", ("parchment", "paper"), "Parchment. The black line is the whole point."),
    ("ink", ("black", "ink"), "Painted black."),
    ("gold", ("gold",), "Gold. Don't thin it out."),
)
_CHARGES = (
    ("dagger", ("dagger and rose", "dagger"), "Dagger and rose. That's a flag."),
    ("anchor", ("anchor",), "Anchor. It holds."),
    ("acorn", ("acorn",), "Acorn. That's the mark."),
    ("rose", ("rose",), "Just the rose."),
    ("none", ("no charge", "field only", "plain", "bare"), "No charge. The field has to carry it."),
)


def clean_place(value: str | None) -> str:
    place = (value or "").strip()
    if place and place not in PLACES:
        raise FlagError("schema_invalid", "place_id is not on the WorldSum sheet")
    return place


def _word(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _ribbon(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def clean_appearance(value: Any) -> str | None:
    """Return stored JSON, or None when the flag has no flash yet.

    Line, ribbon, and fly are optional. A heavy line, a ribbon, and no fly
    choice are the ordinary flag, so those defaults are left out of the JSON.
    """
    if value is None or value == "":
        return None
    if not isinstance(value, dict):
        raise FlagError("schema_invalid", "appearance must be an object")
    extra = set(value) - {"field", "charge", "motto", "line", "ribbon", "fly"}
    if extra:
        raise FlagError(
            "schema_invalid",
            "appearance takes field, charge, motto, line, ribbon, and fly",
        )
    field = str(value.get("field") or "parchment").strip().lower()
    charge = str(value.get("charge") or "none").strip().lower()
    motto = str(value.get("motto") or "").strip()
    if field not in FIELDS:
        raise FlagError("schema_invalid", "field must be crimson, rust, gold, ink, or parchment")
    if charge not in CHARGES:
        raise FlagError("schema_invalid", "charge must be dagger, anchor, acorn, rose, or none")
    if len(motto) > MOTTO_LIMIT:
        raise FlagError("schema_invalid", f"motto is longer than {MOTTO_LIMIT} characters")
    packed = {"field": field, "charge": charge, "motto": motto}
    if "line" in value and value.get("line") not in (None, ""):
        line = str(value.get("line")).strip().lower()
        if line not in LINES:
            raise FlagError("schema_invalid", "line must be heavy or fine")
        if line != "heavy":
            packed["line"] = line
    if "ribbon" in value and not _ribbon(value.get("ribbon")):
        packed["ribbon"] = False
    if "fly" in value and value.get("fly") not in (None, ""):
        fly = str(value.get("fly")).strip().lower()
        if fly not in FLIES:
            raise FlagError("schema_invalid", "fly must be swallowtail, notched, or banner")
        packed["fly"] = fly
    return json.dumps(packed, separators=(",", ":"))


def _flash_clause(clause: str) -> bool:
    low = clause.lower().strip()
    if re.match(r"motto\b", low):
        return True
    if _color_in(low) or _charge_in(low) or _place_in(low):
        return True
    hints = (
        "fine", "thin", "heavy", "thick", "bold", "ribbon",
        "swallowtail", "swallow tail", "notched", "notch", "banner",
        "list", "pull", "unlist",
    )
    return any(_word(low, hint) for hint in hints)


def _spoken_clauses(text: str) -> list[str]:
    """A comma inside an intent sentence is part of the sentence."""
    parts = _clauses(text)
    merged: list[str] = []
    index = 0
    while index < len(parts):
        clause = parts[index]
        try:
            profile = parse_profile_clause(clause)
        except FlagError:
            merged.append(clause)
            index += 1
            continue
        sentence = (profile or {}).get("sentence") or ""
        end = index + 1
        while sentence and sentence[-1] not in ".!?" and end < len(parts) and not _flash_clause(parts[end]):
            sentence = f"{sentence}, {parts[end]}"
            end += 1
        merged.append(clause if end == index + 1 else ", ".join(parts[index:end]))
        index = end
    return merged


def _clauses(text: str) -> list[str]:
    protected = re.sub(r"dagger and rose", "dagger_and_rose", text, flags=re.IGNORECASE)
    parts = re.split(r"\s*(?:,|\band\b)\s*", protected, flags=re.IGNORECASE)
    return [part.replace("dagger_and_rose", "dagger and rose").strip() for part in parts if part.strip()]


def _color_in(clause: str) -> tuple[str, str] | None:
    found = None
    for field, phrases, line in _COLORS:
        for phrase in phrases:
            if _word(clause, phrase):
                if found and found[0] != field:
                    raise FlagError("schema_invalid", "one field at a time")
                found = (field, line)
                break
    return found


def _charge_in(clause: str) -> tuple[str, str] | None:
    for charge, phrases, line in _CHARGES:
        if any(_word(clause, phrase) for phrase in phrases):
            return charge, line
    return None


def _place_in(clause: str) -> str | None:
    for phrase, place_id in _PLACE_ALIASES:
        if _word(clause, phrase):
            return place_id
    return None


def _apply_clause(clause: str, look: dict[str, Any], effect: dict[str, Any], notes: list[str]) -> bool:
    profile = parse_profile_clause(clause)
    if profile:
        bucket = effect.setdefault("profile", {"intents": [], "good_at": None, "enjoy": None, "refuse": None})
        if profile["field"] == "intent":
            bucket["intents"].append({"kind": profile["kind"], "sentence": profile["sentence"]})
        else:
            bucket[profile["field"]] = profile["sentence"]
        notes.append(profile["reply"])
        return True
    low = clause.lower()
    motto = re.match(r"motto\s*[:\-]?\s*(.+)$", clause.strip(), flags=re.IGNORECASE)
    if motto:
        text = motto.group(1).strip().strip("\"'")
        if len(text) > MOTTO_LIMIT:
            raise FlagError("schema_invalid", f"motto is longer than {MOTTO_LIMIT} characters")
        look["motto"] = text
        notes.append(f"Motto {text}.")
        return True
    hit = False
    color = _color_in(low)
    if color:
        look["field"] = color[0]
        notes.append(color[1])
        hit = True
    charge = _charge_in(low)
    if charge:
        look["charge"] = charge[0]
        notes.append(charge[1])
        hit = True
    if _word(low, "fine") or _word(low, "thin"):
        look["line"] = "fine"
        notes.append("Fine line.")
        hit = True
    elif _word(low, "heavy") or _word(low, "thick") or _word(low, "bold"):
        look["line"] = "heavy"
        notes.append("Heavy line.")
        hit = True
    if any(_word(low, phrase) for phrase in ("no ribbon", "ribbon off", "without a ribbon", "without the ribbon")):
        look["ribbon"] = False
        notes.append("Ribbon off.")
        hit = True
    elif _word(low, "ribbon"):
        look["ribbon"] = True
        notes.append("Ribbon on.")
        hit = True
    place = _place_in(low)
    if _word(low, "swallowtail") or _word(low, "swallow tail"):
        look["fly"] = "swallowtail"
        notes.append("Swallowtail.")
        hit = True
    elif _word(low, "notched") or _word(low, "notch"):
        look["fly"] = "notched"
        notes.append("Notched.")
        hit = True
    elif _word(low, "banner"):
        look["fly"] = "banner"
        notes.append("Banner.")
        hit = True
    if place:
        effect["place_id"] = place
        hit = True
    pull = any(_word(low, phrase) for phrase in ("pull it", "pull the", "take it down", "take it off", "unlist"))
    listing = low == "list" or low.startswith("list ") or any(
        _word(low, phrase) for phrase in ("list it", "list this", "plant it", "hang it", "put it up", "put it on")
    )
    if pull and listing:
        raise FlagError("schema_invalid", "list it or pull it, not both")
    if pull:
        effect["listed"] = False
        notes.append("Pulled. The place is off the map.")
        hit = True
    elif listing:
        effect["listed"] = True
        where = _PLACE_NAMES.get(effect.get("place_id") or "", "")
        notes.append(f"Listed at {where}." if where else "Listed.")
        hit = True
    elif place:
        notes.append(f"{_PLACE_NAMES[place]}. Still off the map until you list it.")
    return hit


def apply_order(text: str, appearance: dict | None = None) -> dict[str, Any]:
    """Change only the parts a person named. The rest of the flag stays.

    ``listed`` and ``place_id`` are None when the order did not mention them.
    """
    said = (text or "").strip()
    if not said:
        raise FlagError("schema_invalid", "tell the Steward what to paint")
    if len(said) > ORDER_LIMIT:
        raise FlagError("schema_invalid", f"that order is longer than {ORDER_LIMIT} characters")
    base = appearance or {}
    look: dict[str, Any] = {
        "field": str(base.get("field") or "parchment").strip().lower(),
        "charge": str(base.get("charge") or "none").strip().lower(),
        "motto": str(base.get("motto") or "").strip(),
        "line": str(base.get("line") or "heavy").strip().lower(),
        "ribbon": True if "ribbon" not in base else _ribbon(base.get("ribbon")),
        "fly": str(base.get("fly") or "").strip().lower(),
    }
    effect: dict[str, Any] = {"listed": None, "place_id": None}
    notes: list[str] = []
    for clause in _spoken_clauses(said):
        if not _apply_clause(clause, look, effect, notes):
            raise FlagError(
                "schema_invalid",
                "tell the Steward a field, a charge, a motto, or paint it black",
            )
    packed = {"field": look["field"], "charge": look["charge"], "motto": look["motto"]}
    if look["line"] != "heavy":
        packed["line"] = look["line"]
    if look["ribbon"] is False:
        packed["ribbon"] = False
    if look["fly"]:
        packed["fly"] = look["fly"]
    return {
        "appearance": packed,
        "listed": effect["listed"],
        "place_id": effect["place_id"],
        "reply": " ".join(notes),
        "profile": effect.get("profile"),
    }


def _flag_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def omitted_listing(payload: dict) -> tuple[bool | None, str | None, str | None]:
    """Return listing fields for one write.

    ``listed`` and ``place_id`` are None when an order is present and the
    payload left them out, so the current flag keeps its place on the sheet.
    """
    raw = payload.get("order")
    order = raw.strip() if isinstance(raw, str) and raw.strip() else None
    if "listed" in payload:
        listed: bool | None = _flag_bool(payload.get("listed"), False)
    elif order:
        listed = None
    else:
        listed = False
    if "place_id" in payload:
        place: str | None = payload.get("place_id") or ""
    elif "placeId" in payload:
        place = payload.get("placeId") or ""
    elif order:
        place = None
    else:
        place = ""
    return listed, place, order


def settle_flash(
    *,
    listed: bool | None,
    place_id: str | None,
    appearance: dict | None,
    order: str | None,
    current_listed: bool = False,
    current_place: str | None = None,
    current_appearance: dict | None = None,
) -> tuple[bool, str, str | None, dict | None]:
    """Resolve one write's place and flash.

    Without an order, the write replaces both. An order changes only the
    parts it names. When the order lists and names no place, the caller's
    place is kept, then the place already on the flag.
    """
    said = (order or "").strip()
    heard = None
    if said:
        base = appearance if appearance is not None else current_appearance
        heard = apply_order(said, base if isinstance(base, dict) else None)
        appearance = heard["appearance"]
    if heard is not None and heard["listed"] is not None:
        on_map = bool(heard["listed"])
    elif listed is not None:
        on_map = _flag_bool(listed, False)
    else:
        on_map = bool(current_listed)
    if heard is not None and heard["place_id"]:
        chosen = heard["place_id"]
    elif place_id:
        chosen = place_id
    elif heard is not None:
        chosen = current_place or ""
    else:
        chosen = place_id or ""
    place = clean_place(chosen if isinstance(chosen, str) else "")
    require_listed_place(on_map, place)
    return on_map, place, clean_appearance(appearance), heard.get("profile") if heard else None


def require_listed_place(listed: bool, place: str) -> None:
    if listed and not place:
        raise FlagError("schema_invalid", "a listed flag needs a WorldSum place")
