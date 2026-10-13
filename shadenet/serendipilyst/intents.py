"""Intent marks and the three profile lines on a flag.

An intent is a mark with one sentence: conversation, work, fun, sale, or
purchase. A flag carries at most one mark of each kind. The profile lines
are what the person is good at, what they enjoy, and what they won't be
part of. All of it is public flag content.
"""

from __future__ import annotations

import re
from typing import Any

from shadenet.serendipilyst.fields import KEEP, given, one_sentence
from shadenet.serendipilyst.store import FlagError

KINDS = ("conversation", "work", "fun", "sale", "purchase")
LINES = ("good_at", "enjoy", "refuse")

_INTENT_LINES = {
    "conversation": "Conversation.",
    "work": "Work.",
    "fun": "Fun.",
    "sale": "For sale.",
    "purchase": "Looking to purchase.",
}
_CLEARS = {
    "conversation": ("not looking for a conversation", "drop the conversation"),
    "work": ("not available to work", "drop the work"),
    "fun": ("not looking for fun", "drop the fun"),
    "sale": ("nothing for sale", "drop the sale"),
    "purchase": ("not looking to purchase", "not looking to buy", "drop the purchase"),
}
_INTENT_PATTERNS = (
    ("conversation", re.compile(r"^(?:i am |i'm )?looking for a conversation(?: about| on|:)?\s+(.+)$", re.I)),
    ("conversation", re.compile(r"^conversation(?: about|:)\s+(.+)$", re.I)),
    ("work", re.compile(r"^(?:i am |i'm )?available (?:to|for) work(?:[:,]| on| for)?\s+(.+)$", re.I)),
    ("fun", re.compile(r"^(?:i am |i'm )?looking for fun(?:[:,]| about)?\s+(.+)$", re.I)),
    ("sale", re.compile(r"^(?:i have )?(?:stuff|something) for sale[:,]?\s+(.+)$", re.I)),
    ("sale", re.compile(r"^(?:for sale|selling)[:,]?\s+(.+)$", re.I)),
    ("purchase", re.compile(r"^(?:i am |i'm )?looking to (?:purchase|buy)\s+(.+)$", re.I)),
)
_PROFILE_PATTERNS = (
    ("good_at", re.compile(r"^(?:i am |i'm )?good at\s+(.+)$", re.I), "Good at"),
    ("enjoy", re.compile(r"^(?:i enjoy|enjoy)\s+(.+)$", re.I), "You enjoy"),
    ("refuse", re.compile(
        r"^(?:i (?:don't|do not|won't|wont) want(?: to be a part of)?|not part of|i refuse)\s+(.+)$",
        re.I,
    ), "You won't be part of"),
)
# A clause that starts like an intent but has no sentence after it.
_ATTEMPT = re.compile(
    r"^(?:i am |i'm |i have )?(?:looking for a conversation|conversation|available (?:to|for) work|"
    r"looking for fun|(?:stuff|something) for sale|for sale|selling|looking to (?:purchase|buy)|"
    r"good at|i enjoy|enjoy|i (?:don't|do not|won't|wont) want|not part of|i refuse)\b",
    re.I,
)


def clean_intents(value: Any) -> list[dict[str, str]]:
    """At most one mark per kind, each with its sentence, in a fixed order."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise FlagError("schema_invalid", "intents must be a list")
    found: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            raise FlagError("schema_invalid", "an intent needs a kind and a sentence")
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in KINDS:
            raise FlagError("schema_invalid", "intent must be conversation, work, fun, sale, or purchase")
        if kind in found:
            raise FlagError("schema_invalid", "one mark per intent")
        found[kind] = one_sentence(str(item.get("sentence") or ""))
    return [{"kind": kind, "sentence": found[kind]} for kind in KINDS if kind in found]


def parse_profile_clause(clause: str) -> dict[str, str] | None:
    """Read one clause. None when the clause is not about the person."""
    said = clause.strip()
    low = said.lower()
    for kind, phrases in _CLEARS.items():
        if low in phrases:
            return {
                "field": "intent",
                "kind": kind,
                "sentence": "",
                "reply": f"{_INTENT_LINES[kind]} Off the flag.",
            }
    for field, pattern, lead in _PROFILE_PATTERNS:
        match = pattern.match(said)
        if match:
            line = one_sentence(match.group(1), what="that line")
            return {"field": field, "kind": "", "sentence": line, "reply": f"{lead} {line}."}
    for kind, pattern in _INTENT_PATTERNS:
        match = pattern.match(said)
        if match:
            line = one_sentence(match.group(1))
            return {"field": "intent", "kind": kind, "sentence": line, "reply": f"{_INTENT_LINES[kind]} {line}"}
    if _ATTEMPT.match(low):
        raise FlagError("schema_invalid", "an intent needs a sentence")
    return None


def settle_profile(
    heard: dict | None,
    *,
    intents: Any = KEEP,
    lines: dict[str, Any] | None = None,
    current_intents: list | None = None,
    current_lines: dict[str, str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Resolve the marks and the three lines for one write.

    A field the write left out keeps its stored value. What an order heard
    is applied last and changes only the kinds and lines it named.
    """
    given_lines = lines or {}
    stored_lines = current_lines or {}
    marks = clean_intents(intents if given(intents) else (current_intents or []))
    for item in (heard or {}).get("intents") or []:
        marks = [row for row in marks if row["kind"] != item["kind"]]
        if item.get("sentence"):
            marks.append({"kind": item["kind"], "sentence": item["sentence"]})
    marks = clean_intents(marks)

    settled: dict[str, str] = {}
    for key in LINES:
        if (heard or {}).get(key):
            settled[key] = one_sentence(str(heard[key]), what="that line")
        elif given(given_lines.get(key, KEEP)):
            raw = given_lines[key]
            settled[key] = one_sentence(raw, what="that line") if raw else ""
        else:
            settled[key] = stored_lines.get(key) or ""
    return marks, settled
