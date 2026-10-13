"""American Traditional flash for a public flag, and the order that paints it.

The look is bold black ink, crimson, burnt rust, gold, and parchment. A flag
sets field, charge, motto, line, ribbon, and fly. The explicit controls are
the main way to set them. An order ("paint it black, list it at the square")
is the shortcut: it changes only the parts it names.

A flag is on the WorldSum sheet only when it is listed, and a listed flag
names one place from ``web/js/data/worldsum.js``.

``web/components/worldsum/pennant.js`` carries the same order grammar.
``tests/data/order_vectors.json`` holds the cases both must agree on.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shadenet.serendipilyst.fields import KEEP, as_bool, given
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

# A clause made only of these words is a flash order, even inside a longer
# sentence ("selling an amp and crimson"). "red wine" is not: "wine" isn't here.
_FLASH_WORDS = frozenset(
    "a an the it its with no on off at in to field line fly ribbon charge only "
    "crimson red rust burnt orange gold ink black parchment paper "
    "dagger rose anchor acorn plain bare "
    "fine thin heavy thick bold swallowtail swallow tail notched notch banner "
    "courthouse railroad square rail dark pool lot north gate far lake long water narrows three pools east "
    "list unlist pull".split()
)
# A clause that starts with one of these is an order, not the rest of a sentence.
_COMMAND = re.compile(
    r"^(?:motto\b|list\b|unlist\b|pull\b|paint\b|make it\b|hang it\b|plant it\b|put it\b|"
    r"take it\b|no ribbon\b|ribbon\b)",
    re.I,
)
_MOTTO = re.compile(r"^motto\s*[:\-]?\s*(.+)$", re.I)


def clean_place(value: str | None) -> str:
    place = (value or "").strip()
    if place and place not in PLACES:
        raise FlagError("schema_invalid", "place_id is not on the WorldSum sheet")
    return place


def _word(said: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", said) is not None


def clean_appearance(value: Any) -> str | None:
    """Return stored JSON, or None when the flag has no flash.

    A heavy line, a ribbon, and no fly choice are the ordinary flag, so
    those defaults are left out of the JSON.
    """
    if value is None or value == "" or value == {}:
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
    packed: dict[str, Any] = {"field": field, "charge": charge, "motto": motto}
    if value.get("line") not in (None, ""):
        line = str(value.get("line")).strip().lower()
        if line not in LINES:
            raise FlagError("schema_invalid", "line must be heavy or fine")
        if line != "heavy":
            packed["line"] = line
    if "ribbon" in value and not as_bool(value.get("ribbon"), True):
        packed["ribbon"] = False
    if value.get("fly") not in (None, ""):
        fly = str(value.get("fly")).strip().lower()
        if fly not in FLIES:
            raise FlagError("schema_invalid", "fly must be swallowtail, notched, or banner")
        packed["fly"] = fly
    return json.dumps(packed, separators=(",", ":"))


def _parts(said: str) -> list[tuple[str, str]]:
    """Split on commas, "and", and sentence ends, keeping each separator as typed."""
    protected = re.sub(r"dagger and rose", "dagger_and_rose", said, flags=re.IGNORECASE)
    pieces = re.split(r"(\s*,\s*|\s+and\s+|(?<=[.!?])\s+)", protected, flags=re.IGNORECASE)
    out: list[tuple[str, str]] = []
    sep = ""
    for index, piece in enumerate(pieces):
        if index % 2:
            sep = piece
            continue
        text = piece.replace("dagger_and_rose", "dagger and rose").strip()
        if text:
            out.append((sep, text))
        sep = ""
    return out


def _is_order(part: str) -> bool:
    """True when a part reads as its own flash order."""
    low = part.lower().strip()
    if _COMMAND.match(low):
        return True
    words = re.findall(r"[a-z]+", low)
    return bool(words) and all(word in _FLASH_WORDS for word in words)


def _opens_sentence(part: str) -> bool:
    """A motto or a profile line runs on until the next order."""
    if _MOTTO.match(part.strip()):
        return True
    try:
        return parse_profile_clause(part) is not None
    except FlagError:
        return False


def spoken_clauses(said: str) -> list[str]:
    """Group the parts of an order into clauses.

    A motto, intent, or profile line keeps the words after it, joined the
    way they were typed, until a part that is its own order or starts a
    line of its own. So "I enjoy
    black coffee and red wine" stays one line, and "selling an amp, list it"
    is a sale and a listing.
    """
    parts = _parts(said)
    merged: list[str] = []
    index = 0
    while index < len(parts):
        _sep, clause = parts[index]
        index += 1
        if _opens_sentence(clause):
            while (index < len(parts) and clause[-1] not in ".!?"
                   and not _is_order(parts[index][1]) and not _opens_sentence(parts[index][1])):
                sep, more = parts[index]
                clause = f"{clause}{sep}{more}"
                index += 1
        merged.append(clause)
    return merged


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
    motto = _MOTTO.match(clause.strip())
    if motto:
        said = motto.group(1).strip().strip("\"'")
        if len(said) > MOTTO_LIMIT:
            raise FlagError("schema_invalid", f"motto is longer than {MOTTO_LIMIT} characters")
        look["motto"] = said
        notes.append(f"Motto {said}.")
        return True
    profile = parse_profile_clause(clause)
    if profile:
        bucket = effect.setdefault("profile", {"intents": [], "good_at": None, "enjoy": None, "refuse": None})
        if profile["field"] == "intent":
            if any(item["kind"] == profile["kind"] for item in bucket["intents"]):
                raise FlagError("schema_invalid", "one mark per intent")
            bucket["intents"].append({"kind": profile["kind"], "sentence": profile["sentence"]})
        else:
            bucket[profile["field"]] = profile["sentence"]
        notes.append(profile["reply"])
        return True
    low = clause.lower()
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


def apply_order(said: str, appearance: dict | None = None) -> dict[str, Any]:
    """Change only the parts a person named. The rest of the flag stays.

    ``listed`` and ``place_id`` are None when the order did not mention them.
    """
    said = (said or "").strip()
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
        "ribbon": True if "ribbon" not in base else as_bool(base.get("ribbon"), True),
        "fly": str(base.get("fly") or "").strip().lower(),
    }
    effect: dict[str, Any] = {"listed": None, "place_id": None}
    notes: list[str] = []
    for clause in spoken_clauses(said):
        if not _apply_clause(clause, look, effect, notes):
            raise FlagError(
                "schema_invalid",
                "tell the Steward a field, a charge, a motto, or paint it black",
            )
    packed: dict[str, Any] = {"field": look["field"], "charge": look["charge"], "motto": look["motto"]}
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


def settle_flash(
    *,
    listed: Any = KEEP,
    place_id: Any = KEEP,
    appearance: Any = KEEP,
    order: str | None = None,
    current_listed: bool = False,
    current_place: str = "",
    current_appearance: dict | None = None,
) -> tuple[bool, str, str | None, dict | None]:
    """Resolve one write's listing, place, and flash.

    Anything the write left out keeps its stored value. An order is applied
    on top and changes only what it names. Returns
    ``(listed, place_id, appearance_json, heard_profile)``.
    """
    look = appearance if given(appearance) else current_appearance
    heard = None
    if (order or "").strip():
        heard = apply_order(order, look if isinstance(look, dict) else None)
        look = heard["appearance"]
    if heard is not None and heard["listed"] is not None:
        on_map = bool(heard["listed"])
    elif given(listed):
        on_map = as_bool(listed, False)
    else:
        on_map = bool(current_listed)
    if heard is not None and heard["place_id"]:
        chosen = heard["place_id"]
    elif given(place_id):
        chosen = place_id or ""
    else:
        chosen = current_place or ""
    place = clean_place(chosen if isinstance(chosen, str) else "")
    if on_map and not place:
        raise FlagError("schema_invalid", "a listed flag needs a WorldSum place")
    return on_map, place, clean_appearance(look), heard.get("profile") if heard else None
