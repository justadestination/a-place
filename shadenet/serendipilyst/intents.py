"""Intent marks on a flag, and the private dealing that can follow.

An intent is a mark the Steward sets when the person asks: a conversation,
work, fun, a sale, or a purchase. The mark is never stored without the
sentence that says what it is.

Ratings are hearts for the person and flames for the thing. They stay off
the sheet. The Steward does not coach from them until this person has
twenty-five finished transactions.

The obligation is the purchaser's debt to the platform in Monero, then a
release to the seller. This record does not build a payable address and
does not broadcast a transfer. Hearts, flames, and one word are required
at both of those steps.

An accord is read by both stewards from the private room. Each reading is
one local model call over that conversation. It states what each user
gives, what each user gets, and the price. They keep that price only when
the two readings match, and each user confirms it before anyone is obliged.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from shadenet.serendipilyst.store import FlagError, FlagStore, loads, new_id, now_iso

KINDS = ("conversation", "work", "fun", "sale", "purchase")
SENTENCE_LIMIT = 160
SAMPLE = 25
WORD = re.compile(r"^[A-Za-z][A-Za-z'-]{0,23}$")

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
_ATTEMPT = re.compile(
    r"looking for a conversation|available (?:to|for) work|looking for fun|"
    r"(?:stuff|something) for sale|\bfor sale\b|\bselling\b|"
    r"looking to (?:purchase|buy)|\bgood at\b|\bi enjoy\b|^enjoy\b|"
    r"don't want|do not want|won't want|wont want|not part of|\bi refuse\b",
    re.I,
)


def one_sentence(value: str, *, what: str = "an intent") -> str:
    text = " ".join((value or "").strip().strip("\"'").split())
    if not text:
        raise FlagError("schema_invalid", f"{what} needs a sentence")
    if len(text) > SENTENCE_LIMIT:
        raise FlagError("schema_invalid", f"that sentence is longer than {SENTENCE_LIMIT} characters")
    stops = [index for index, char in enumerate(text) if char in ".!?"]
    if len(stops) > 1 or (stops and stops[-1] != len(text) - 1):
        raise FlagError("schema_invalid", "one sentence")
    return text


def clean_intents(value: Any) -> list[dict[str, str]]:
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
        found[kind] = one_sentence(str(item.get("sentence") or ""))
    if len(found) > len(KINDS):
        raise FlagError("schema_invalid", "one mark per intent")
    return [{"kind": kind, "sentence": found[kind]} for kind in KINDS if kind in found]


def parse_profile_clause(clause: str) -> dict[str, str] | None:
    """Read one clause. None when the clause is not about the person."""
    low = clause.strip().lower()
    for kind, phrases in _CLEARS.items():
        if low in phrases:
            return {
                "field": "intent",
                "kind": kind,
                "sentence": "",
                "reply": f"{_INTENT_LINES[kind]} Off the flag.",
            }
    for field, pattern, lead in _PROFILE_PATTERNS:
        match = pattern.match(clause.strip())
        if match:
            text = one_sentence(match.group(1), what="that line")
            return {"field": field, "kind": "", "sentence": text, "reply": f"{lead} {text}."}
    for kind, pattern in _INTENT_PATTERNS:
        match = pattern.match(clause.strip())
        if match:
            text = one_sentence(match.group(1))
            return {"field": "intent", "kind": kind, "sentence": text, "reply": f"{_INTENT_LINES[kind]} {text}"}
    if _ATTEMPT.search(low):
        raise FlagError("schema_invalid", "an intent needs a sentence")
    return None


def settle_profile(
    change: dict | None,
    *,
    ordered: bool,
    intents: Any,
    good_at: str | None,
    enjoy: str | None,
    refuse: str | None,
    current_intents: list | None,
    current_good: str,
    current_enjoy: str,
    current_refuse: str,
) -> tuple[list[dict[str, str]], str, str, str]:
    """Replace the profile, or let an order change only the lines it names."""
    if not ordered:
        return (
            clean_intents(intents or []),
            one_sentence(good_at, what="that line") if good_at else "",
            one_sentence(enjoy, what="that line") if enjoy else "",
            one_sentence(refuse, what="that line") if refuse else "",
        )
    base = clean_intents(intents) if intents is not None else clean_intents(current_intents or [])
    heard = change or {}
    for item in heard.get("intents") or []:
        base = [row for row in base if row["kind"] != item["kind"]]
        if item.get("sentence"):
            base.append({"kind": item["kind"], "sentence": item["sentence"]})
    base = clean_intents(base)

    def pick(key: str, given: str | None, current: str) -> str:
        if heard.get(key):
            return one_sentence(str(heard[key]), what="that line")
        if given is not None:
            return one_sentence(given, what="that line") if given else ""
        return current or ""

    return (
        base,
        pick("good_at", good_at, current_good),
        pick("enjoy", enjoy, current_enjoy),
        pick("refuse", refuse, current_refuse),
    )


def omitted_profile(payload: dict) -> tuple[Any, str | None, str | None, str | None]:
    """None means an order left that line out, so the stored line stays."""
    raw = payload.get("order")
    ordered = isinstance(raw, str) and bool(raw.strip())

    def text(name: str) -> str | None:
        if name in payload:
            return payload.get(name) or ""
        return None if ordered else ""

    if "intents" in payload:
        intents: Any = payload.get("intents")
    elif ordered:
        intents = None
    else:
        intents = []
    return intents, text("good_at"), text("enjoy"), text("refuse")


def _amount(value: Any, label: str, *, required: bool) -> str | None:
    if value is None or value == "":
        if required:
            raise FlagError("schema_invalid", f"{label} is required")
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise FlagError("schema_invalid", f"{label} must be a Monero amount") from None
    if not number.is_finite() or number < 0 or number > Decimal("1000000"):
        raise FlagError("schema_invalid", f"{label} must be a Monero amount")
    if number == 0:
        if required:
            raise FlagError("schema_invalid", f"{label} must be a Monero amount")
        return None
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -12:
        raise FlagError("schema_invalid", f"{label} must be a Monero amount")
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _score(value: Any, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise FlagError("schema_invalid", f"{label} is a number from 1 to 100")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise FlagError("schema_invalid", f"{label} is a number from 1 to 100") from None
    if str(value).strip() != str(number) or not 1 <= number <= 100:
        raise FlagError("schema_invalid", f"{label} is a number from 1 to 100")
    return number


def _rating(personal: Any, product: Any, word: Any) -> tuple[int, int, str]:
    hearts = _score(personal, "the personal rating")
    flames = _score(product, "the product rating")
    token = (word or "").strip()
    if token and not WORD.match(token):
        raise FlagError("schema_invalid", "the word is one word")
    if hearts is None or flames is None or not token:
        raise FlagError("schema_invalid", "a rating needs hearts, flames, and one word")
    return hearts, flames, token.lower()


def _same(left: str, right: str) -> bool:
    def norm(value: str) -> str:
        return " ".join(value.lower().split()).rstrip(".!?")

    return norm(left) == norm(right)


def _stop(text: str) -> str:
    return text if text[-1:] in ".!?" else f"{text}."


_reader: Callable[[str], str] | None = None
_CANNOT_TELL = (
    "I read the room and I cannot tell what each user gives, what each user gets, and the price"
)
_UNREAD = "I have not read the room"


def use_reader(reader: Callable[[str], str] | None) -> None:
    """Install the completion used to read a room. ``None`` uses local inference."""
    global _reader
    _reader = reader


def _transcript(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        if message.get("redacted"):
            continue
        content = " ".join(str(message.get("content") or "").split())
        if not content:
            continue
        sender = " ".join(str(message.get("sender") or "someone").split())
        lines.append(f"{sender}: {content}")
    return "\n".join(lines)


def _party(value: str) -> str:
    text = " ".join((value or "").split())
    if not text or len(text) > 120 or "a2a://" in text:
        raise FlagError("schema_invalid", _UNREAD)
    return text


def _prompt(transcript: str, *, side: str, buyer: str, seller: str) -> str:
    return (
        f"You are the {side}'s steward. The buyer is {buyer}. The seller is {seller}.\n"
        "Read only the conversation. Do not add terms that were not said.\n"
        "State what each user gives, what each user gets, and the price.\n"
        "buyer_give is what the buyer gives. buyer_get is what the buyer gets.\n"
        "seller_give is what the seller gives. seller_get is what the seller gets.\n"
        "amount is the price in XMR, digits and a dot only.\n"
        "Reply with one JSON object and no other text: "
        '{"buyer_give":"","buyer_get":"","seller_give":"","seller_get":"","amount":""}\n'
        "If the conversation does not state what each user gives, what each user gets, "
        'and the price, reply {"unclear":true}\n\n'
        f"{transcript}"
    )


def _price_token(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    lower = text.lower()
    for suffix in ("xmr", "monero"):
        if lower.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    return text


def _parse_reading(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise FlagError("schema_invalid", _CANNOT_TELL)
    try:
        heard = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        raise FlagError("schema_invalid", _CANNOT_TELL) from None
    if not isinstance(heard, dict) or heard.get("unclear"):
        raise FlagError("schema_invalid", _CANNOT_TELL)
    try:
        buyer_give = one_sentence(str(heard.get("buyer_give") or ""), what="what the buyer gives")
        buyer_get = one_sentence(str(heard.get("buyer_get") or ""), what="what the buyer gets")
        seller_give = one_sentence(str(heard.get("seller_give") or ""), what="what the seller gives")
        seller_get = one_sentence(str(heard.get("seller_get") or ""), what="what the seller gets")
        amount = _amount(_price_token(heard.get("amount")), "the price", required=True)
    except FlagError:
        raise FlagError("schema_invalid", _CANNOT_TELL) from None
    if amount is None or not _same(buyer_give, seller_get) or not _same(buyer_get, seller_give):
        raise FlagError("schema_invalid", _CANNOT_TELL)
    return {
        "buyer_give": buyer_give,
        "buyer_get": buyer_get,
        "seller_give": seller_give,
        "seller_get": seller_get,
        "amount": amount,
    }


def _local_complete(prompt: str) -> str:
    import urllib.error
    import urllib.request
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parents[1] / "steward" / "config" / "agent.yaml"
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        local = loaded["inference"]["local"]
        endpoint = str(local["endpoint"]).rstrip("/")
        model = str(local["model"])
        temperature = float(local.get("temperature", 0.3))
    except (OSError, KeyError, TypeError, ValueError):
        raise FlagError("schema_invalid", _UNREAD) from None
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,
        "format": "json",
    }).encode()
    request = urllib.request.Request(
        f"{endpoint}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise FlagError("schema_invalid", _UNREAD) from None
    text = payload.get("response") if isinstance(payload, dict) else ""
    if not str(text or "").strip():
        raise FlagError("schema_invalid", _UNREAD)
    return str(text)


def _complete(prompt: str) -> str:
    if _reader is not None:
        return _reader(prompt)
    return _local_complete(prompt)


def hear_side(
    messages: list[dict[str, Any]],
    *,
    side: str,
    buyer: str,
    seller: str,
) -> dict[str, str]:
    """One steward reads the conversation and states what each user gives, what each user gets, and the price."""
    if side not in {"buyer", "seller"}:
        raise FlagError("schema_invalid", _UNREAD)
    if not isinstance(messages, list) or len(messages) > 50:
        raise FlagError("schema_invalid", _UNREAD)
    transcript = _transcript([item for item in messages if isinstance(item, dict)])
    if not transcript:
        raise FlagError("schema_invalid", "both of you have to speak before I read an accord")
    prompt = _prompt(transcript, side=side, buyer=_party(buyer), seller=_party(seller))
    return _parse_reading(_complete(prompt))


def _exchange(view: dict[str, str], *, side: str) -> str:
    """Say what each user gives, what each user gets, and the price."""
    if side == "buyer":
        mine_give, mine_get = view["buyer_give"], view["buyer_get"]
        their_give, their_get = view["seller_give"], view["seller_get"]
    else:
        mine_give, mine_get = view["seller_give"], view["seller_get"]
        their_give, their_get = view["buyer_give"], view["buyer_get"]
    return (
        f"You give {_stop(mine_give)} You get {_stop(mine_get)} "
        f"They give {_stop(their_give)} They get {_stop(their_get)} "
        f"The price is {view['amount']} XMR."
    )


def _loads_intents(raw: str | None) -> list[dict[str, str]]:
    return clean_intents(loads(raw))


def _target(store: FlagStore, flag_id: str) -> dict[str, Any]:
    row = store.query_one("SELECT * FROM personal_flags WHERE id = ?", (flag_id,))
    if row is not None:
        return {
            "id": row["id"],
            "owner": row["owner"],
            "name": row["display_name"],
            "intents": _loads_intents(row["intents"]),
            "offer": bool(row["offer_title"]),
        }
    row = store.query_one("SELECT * FROM business_nodes WHERE id = ?", (flag_id,))
    if row is None:
        raise FlagError("not_found", "that flag is not on the sheet")
    return {
        "id": row["id"],
        "owner": row["inbox"],
        "name": row["name"],
        "intents": _loads_intents(row["intents"]),
        "offer": False,
    }


def _offered(target: dict[str, Any]) -> bool:
    return bool(target["offer"] or target["intents"])


def introduce(
    store: FlagStore,
    *,
    actor: str,
    flag_id: str,
    sentence: str,
    chat: Any = None,
) -> dict[str, Any]:
    """Tell the other steward and open a private room for the two of them."""
    from shadenet.chat import STEWARD_PSEUDONYM, create_private_room, get_pseudonym_for_user
    from shadenet.serendipilyst.personal import _actor

    buyer = _actor(actor)
    target = _target(store, flag_id)
    if target["owner"] == buyer:
        raise FlagError("schema_invalid", "that flag is already yours")
    if not _offered(target):
        raise FlagError("schema_invalid", "they haven't put anything up")
    about = one_sentence(sentence)
    told = about if about[-1] in ".!?" else f"{about}."
    stamp = now_iso()
    intro_id = new_id("int")
    if chat is not None:
        room = create_private_room(
            chat,
            name=target["name"],
            topic=about,
            members=[
                STEWARD_PSEUDONYM,
                get_pseudonym_for_user(chat, buyer),
                get_pseudonym_for_user(chat, target["owner"]),
            ],
            opening=(
                f"I told their steward. {target['name']} is in this room. "
                f"You wanted to talk about {told} This room is private."
            ),
        )
        room_id = room["room_id"]
    else:
        room_id = f"!private_{intro_id.removeprefix('int_')}:shady.example.org"
    store.execute(
        """
        INSERT INTO introductions (
            id, room_id, buyer, seller, seller_flag_id, sentence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (intro_id, room_id, buyer, target["owner"], target["id"], about, stamp),
    )
    return {
        "id": intro_id,
        "room_id": room_id,
        "sentence": about,
        "name": target["name"],
        "reply": "I told their steward. The room is private. You are both in it.",
    }


def _introduction(store: FlagStore, actor: str, flag_id: str):
    from shadenet.serendipilyst.personal import _actor

    who = _actor(actor)
    target = _target(store, flag_id)
    if who == target["owner"]:
        row = store.query_one(
            """
            SELECT * FROM introductions
            WHERE seller = ? AND seller_flag_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (who, flag_id),
        )
    else:
        row = store.query_one(
            """
            SELECT * FROM introductions
            WHERE buyer = ? AND seller_flag_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (who, flag_id),
        )
    if row is None or who not in (row["buyer"], row["seller"]):
        raise FlagError("schema_invalid", "open a private room before you call an accord")
    return who, target, row


def _room_lines(chat: Any, room_id: str, buyer: str, seller: str) -> tuple[list[dict[str, Any]], str, str]:
    if chat is None:
        raise FlagError("schema_invalid", "I have not read the room")
    from shadenet.chat import STEWARD_PSEUDONYM, get_pseudonym_for_user, get_room_messages

    messages = get_room_messages(chat, room_id, viewer=STEWARD_PSEUDONYM)
    spoken = {message["sender"] for message in messages}
    buyer_name = get_pseudonym_for_user(chat, buyer)
    seller_name = get_pseudonym_for_user(chat, seller)
    if buyer_name not in spoken or seller_name not in spoken:
        raise FlagError("schema_invalid", "both of you have to speak before I read an accord")
    return messages, buyer_name, seller_name


def _accord_view(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "room_id": row["room_id"],
        "state": row["state"],
        "thing": row["thing"] or "",
        "amount_xmr": row["amount_xmr"] or "",
        "buyer_give": row["buyer_give"] or "",
        "buyer_get": row["buyer_get"] or "",
        "seller_give": row["seller_give"] or "",
        "seller_get": row["seller_get"] or "",
        "buyer_confirmed": bool(row["buyer_confirmed"]),
        "seller_confirmed": bool(row["seller_confirmed"]),
    }


def _terms(row, who: str) -> tuple[str, str, str]:
    if who == row["buyer"]:
        return row["buyer_give"], row["buyer_get"], row["buyer_amount"]
    return row["seller_give"], row["seller_get"], row["seller_amount"]


def read_accord(
    store: FlagStore,
    *,
    actor: str,
    flag_id: str,
    chat: Any = None,
) -> dict[str, Any]:
    """One steward reads the private room and states what each user gives, what each user gets, and the price."""
    who, _target_row, intro = _introduction(store, actor, flag_id)
    messages, buyer_name, seller_name = _room_lines(
        chat, intro["room_id"], intro["buyer"], intro["seller"],
    )
    side = "buyer" if who == intro["buyer"] else "seller"
    heard = hear_side(messages, side=side, buyer=buyer_name, seller=seller_name)
    offered = heard["buyer_give"] if side == "buyer" else heard["seller_give"]
    wanted = heard["buyer_get"] if side == "buyer" else heard["seller_get"]
    price = heard["amount"]
    spoken = _exchange(heard, side=side)
    stamp = now_iso()
    current = store.query_one("SELECT * FROM accords WHERE room_id = ?", (intro["room_id"],))
    if current is None:
        saved = new_id("acd")
        store.execute(
            """
            INSERT INTO accords (
                id, room_id, buyer, seller, seller_flag_id, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'reading', ?, ?)
            """,
            (saved, intro["room_id"], intro["buyer"], intro["seller"], intro["seller_flag_id"], stamp, stamp),
        )
    else:
        saved = current["id"]
        if current["state"] == "used":
            other = "seller" if who == intro["buyer"] else "buyer"
            store.execute(
                f"""
                UPDATE accords SET
                    {other}_give = '', {other}_get = '', {other}_amount = '',
                    {other}_confirmed = 0
                WHERE id = ?
                """,
                (saved,),
            )
    prefix = "buyer" if who == intro["buyer"] else "seller"
    store.execute(
        f"""
        UPDATE accords SET
            {prefix}_give = ?, {prefix}_get = ?, {prefix}_amount = ?, updated_at = ?
        WHERE id = ?
        """,
        (offered, wanted, price, stamp, saved),
    )
    row = store.query_one("SELECT * FROM accords WHERE id = ?", (saved,))
    both = bool(row["buyer_amount"] and row["seller_amount"])
    aligned = both and row["buyer_amount"] == row["seller_amount"] and _same(
        row["buyer_get"], row["seller_give"]
    ) and _same(row["buyer_give"], row["seller_get"])
    if aligned:
        state = "agreed"
        thing = row["buyer_get"]
        agreed_amount = row["buyer_amount"]
        buyer_yes = 0
        seller_yes = 0
        reply = (
            "I read the room. Their steward read it too. We are on the same page. "
            f"{spoken} Confirm that this is what you expect."
        )
    elif both:
        state = "apart"
        thing = ""
        agreed_amount = ""
        buyer_yes = 0
        seller_yes = 0
        reply = (
            "I read the room. Their steward read it too. We are not on the same page. "
            f"{spoken} Nothing is confirmed."
        )
    else:
        state = "reading"
        thing = ""
        agreed_amount = ""
        buyer_yes = 0
        seller_yes = 0
        reply = (
            f"I read the room. Both of you have spoken. {spoken} "
            "Their steward has not read it back yet."
        )
    store.execute(
        """
        UPDATE accords SET
            thing = ?, amount_xmr = ?, state = ?,
            buyer_confirmed = ?, seller_confirmed = ?, updated_at = ?
        WHERE id = ?
        """,
        (thing, agreed_amount, state, buyer_yes, seller_yes, stamp, saved),
    )
    saved_row = _accord_view(store.query_one("SELECT * FROM accords WHERE id = ?", (saved,)))
    saved_row["reply"] = reply
    return saved_row


def confirm_accord(
    store: FlagStore,
    *,
    actor: str,
    flag_id: str,
) -> dict[str, Any]:
    """The user confirms what each user gives, what each user gets, and the price."""
    who, _target_row, intro = _introduction(store, actor, flag_id)
    row = store.query_one("SELECT * FROM accords WHERE room_id = ?", (intro["room_id"],))
    if row is None or row["state"] in {"reading", "used"}:
        raise FlagError("schema_invalid", "their steward has not read the room yet")
    if row["state"] == "apart":
        raise FlagError("schema_invalid", "we are not on the same page")
    if row["state"] != "agreed" and row["state"] != "accorded":
        raise FlagError("schema_invalid", "their steward has not read the room yet")
    side = "buyer" if who == row["buyer"] else "seller"
    prefix = side
    store.execute(
        f"UPDATE accords SET {prefix}_confirmed = 1, updated_at = ? WHERE id = ?",
        (now_iso(), row["id"]),
    )
    current = store.query_one("SELECT * FROM accords WHERE id = ?", (row["id"],))
    both = bool(current["buyer_confirmed"] and current["seller_confirmed"])
    if both and current["state"] != "used":
        store.execute(
            "UPDATE accords SET state = 'accorded', updated_at = ? WHERE id = ?",
            (now_iso(), row["id"]),
        )
        current = store.query_one("SELECT * FROM accords WHERE id = ?", (row["id"],))
    reply = "You confirmed. " + _exchange({
        "buyer_give": current["buyer_give"],
        "buyer_get": current["buyer_get"],
        "seller_give": current["seller_give"],
        "seller_get": current["seller_get"],
        "amount": current["amount_xmr"] or current[f"{side}_amount"],
    }, side=side)
    if both:
        reply = (
            f"{reply} Both of you confirmed. This is what each user gives, "
            "what each user gets, and the price."
        )
    else:
        reply = f"{reply} Their user has not confirmed yet."
    saved = _accord_view(current)
    saved["reply"] = reply
    return saved


def oblige(
    store: FlagStore,
    *,
    actor: str,
    flag_id: str,
    sentence: str,
    amount: Any,
    room_id: str | None = None,
) -> dict[str, Any]:
    """Oblige the purchaser only after both users confirmed the price."""
    from shadenet.serendipilyst.personal import _actor

    buyer = _actor(actor)
    target = _target(store, flag_id)
    if target["owner"] == buyer:
        raise FlagError("schema_invalid", "that flag is already yours")
    selling = target["offer"] or any(item["kind"] == "sale" for item in target["intents"])
    if not selling:
        raise FlagError("schema_invalid", "they don't have anything for sale")
    about = one_sentence(sentence)
    owed = _amount(amount, "the amount", required=True)
    accord = store.query_one(
        """
        SELECT * FROM accords
        WHERE buyer = ? AND seller_flag_id = ? AND state = 'accorded'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (buyer, target["id"]),
    )
    if accord is None:
        raise FlagError(
            "schema_invalid",
            "both of you have to confirm what you give, what you get, and the price",
        )
    asked = str(room_id).strip() if room_id else ""
    if asked and asked != accord["room_id"]:
        raise FlagError("schema_invalid", "that is not the room you both confirmed")
    if accord["amount_xmr"] != owed or not _same(accord["thing"] or "", about):
        raise FlagError(
            "schema_invalid",
            "that is not the price and the thing you both confirmed",
        )
    saved = new_id("obl")
    stamp = now_iso()
    store.execute(
        "UPDATE accords SET state = 'used', updated_at = ? WHERE id = ?",
        (stamp, accord["id"]),
    )
    store.execute(
        """
        INSERT INTO obligations (
            id, buyer, seller, seller_flag_id, sentence, amount_xmr, state,
            room_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'obliged', ?, ?, ?)
        """,
        (saved, buyer, target["owner"], target["id"], about, owed, accord["room_id"], stamp, stamp),
    )
    return _obligation(store, saved)


def _obligation(store: FlagStore, obligation_id: str) -> dict[str, Any]:
    row = store.query_one("SELECT * FROM obligations WHERE id = ?", (obligation_id,))
    if row is None:
        raise FlagError("not_found", "that obligation does not exist")
    return {
        "id": row["id"],
        "buyer": row["buyer"],
        "seller": row["seller"],
        "seller_flag_id": row["seller_flag_id"],
        "sentence": row["sentence"],
        "amount_xmr": row["amount_xmr"],
        "state": row["state"],
        "paid_tip_xmr": row["paid_tip_xmr"] or "",
        "released_tip_xmr": row["released_tip_xmr"] or "",
        "buyer_personal": row["buyer_personal"],
        "buyer_product": row["buyer_product"],
        "buyer_word": row["buyer_word"] or "",
        "seller_personal": row["seller_personal"],
        "seller_product": row["seller_product"],
        "seller_word": row["seller_word"] or "",
        "room_id": row["room_id"] or "",
    }


def _take_rating(
    store: FlagStore,
    *,
    obligation_id: str,
    actor: str,
    side: str,
    state: str,
    tip: Any,
    personal: Any,
    product: Any,
    word: Any,
) -> dict[str, Any]:
    from shadenet.serendipilyst.personal import _actor

    who = _actor(actor)
    row = store.query_one("SELECT * FROM obligations WHERE id = ?", (obligation_id,))
    if row is None:
        raise FlagError("not_found", "that obligation does not exist")
    if row["state"] != state:
        raise FlagError("schema_invalid", "that step has already been taken")
    owner = row["buyer"] if side == "buyer" else row["seller"]
    if who != owner:
        raise FlagError("scope_denied", "only that steward can take this step")
    hearts, flames, token = _rating(personal, product, word)
    tipped = _amount(tip, "the tip", required=False)
    column = "paid_tip_xmr" if side == "buyer" else "released_tip_xmr"
    next_state = "paid" if side == "buyer" else "released"
    prefix = "buyer" if side == "buyer" else "seller"
    store.execute(
        f"""
        UPDATE obligations SET
            state = ?, {column} = ?,
            {prefix}_personal = ?, {prefix}_product = ?, {prefix}_word = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (next_state, tipped, hearts, flames, token, now_iso(), obligation_id),
    )
    saved = _obligation(store, obligation_id)
    if side == "buyer":
        reply = f"You owe the platform {saved['amount_xmr']} XMR for {saved['sentence']}"
    else:
        reply = f"Released to the seller. {saved['sentence']}"
    if tipped:
        reply = f"{reply} Tip noted."
    reply = (
        f"{reply} The ratings stay with me until {SAMPLE} transactions."
    )
    saved["reply"] = reply
    return saved


def pay(store: FlagStore, *, actor: str, obligation_id: str, tip: Any = None,
         personal: Any = None, product: Any = None, word: Any = None) -> dict[str, Any]:
    return _take_rating(
        store, obligation_id=obligation_id, actor=actor, side="buyer", state="obliged",
        tip=tip, personal=personal, product=product, word=word,
    )


def release(store: FlagStore, *, actor: str, obligation_id: str, tip: Any = None,
            personal: Any = None, product: Any = None, word: Any = None) -> dict[str, Any]:
    return _take_rating(
        store, obligation_id=obligation_id, actor=actor, side="seller", state="paid",
        tip=tip, personal=personal, product=product, word=word,
    )


def _received(store: FlagStore, actor: str) -> list[Any]:
    return store.query_all(
        """
        SELECT * FROM obligations
        WHERE state = 'released' AND (buyer = ? OR seller = ?)
        ORDER BY updated_at ASC
        """,
        (actor, actor),
    )


def counsel(store: FlagStore, *, actor: str) -> dict[str, Any]:
    """Speak about ratings only after a real sample. The sheet never hears this."""
    from shadenet.serendipilyst.personal import _actor

    who = _actor(actor)
    rows = _received(store, who)
    count = len(rows)
    held = f"I'm holding the ratings. {SAMPLE} transactions, then I will say what to change."
    if count < SAMPLE:
        return {"ready": False, "count": count, "note": held}
    hearts: list[int] = []
    flames: list[int] = []
    words: list[str] = []
    for row in rows:
        if row["seller"] == who and row["buyer_personal"] is not None:
            hearts.append(int(row["buyer_personal"]))
            flames.append(int(row["buyer_product"]))
            if row["buyer_word"]:
                words.append(row["buyer_word"])
        if row["buyer"] == who and row["seller_personal"] is not None:
            hearts.append(int(row["seller_personal"]))
            flames.append(int(row["seller_product"]))
            if row["seller_word"]:
                words.append(row["seller_word"])
    if not hearts:
        return {
            "ready": True,
            "count": count,
            "note": "Twenty-five transactions, and nobody left a rating. I still need words before I coach you.",
        }
    personal = sum(hearts) / len(hearts)
    product = sum(flames) / len(flames)
    word = max(set(words), key=words.count) if words else ""
    notes: list[str] = []
    if personal < 50:
        notes.append(
            f"People are rating you low. The word that keeps showing up is {word}."
            if word else "People are rating you low."
        )
    elif personal >= 80:
        notes.append("People are fine with you. Don't sand off the edges.")
    if product < 50:
        notes.append("The thing you are offering is the weak part. Look at that before the small talk.")
    elif product >= 80:
        notes.append("The offer is landing. Leave it alone.")
    if not notes:
        notes.append("You are in the middle of the range. One sharp change will show up faster than a new motto.")
    return {"ready": True, "count": count, "note": " ".join(notes)}
