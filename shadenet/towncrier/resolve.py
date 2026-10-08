"""Entity resolution: decide which listings are the same real-world event.

This is the hard part of the whole system, and the part the user's instinct
was right about. A well-promoted show appears as:
  - the venue's own calendar page
  - a ticketing site
  - a band's Facebook post
  - a promoter's Instagram caption
  - a local aggregator
  - a mention in a forum post

Six rows, one show. Fail to merge them and the calendar fills with
duplicates; merge too eagerly and two genuinely different 8pm shows at
different venues collapse into one.

The approach, following what production aggregators converge on:

  1. **Block** — only compare listings that could plausibly be the same show.
     Blocking by (venue, calendar date) cuts the comparison set by orders of
     magnitude and prevents the expensive fuzzy comparison from running on
     every pair. Blocking is a hard constraint: two listings at different
     venues are never merged on title alone, because "Special" is a real
     event name and appears everywhere.

  2. **Compare** — within a block, score on independent axes:
       * title similarity (token-set + fuzzy, order-insensitive)
       * time proximity (how far apart are the start times)
       * venue agreement (same venue, or a known alias)

  3. **Threshold** — merge only if the combined score clears a bar, and
     require title agreement to be the dominant term. A strong time match
     must not paper over a completely different title.

Why each signal gets its own axis rather than one blended score: the failure
modes are asymmetric. Over-merging is silent and permanent (you then track a
show that isn't happening); under-merging is obvious and self-correcting (the
duplicate shows up and you notice). The thresholds are tuned toward
under-merging, and the corroboration count is what tells you how thin an
event's evidence is.

One important non-goal: we do NOT try to be clever with an LLM here. Merging
decisions need to be deterministic and explainable — every merge records the
score and the reason, so a wrong merge can be diagnosed. That is in
`event_listings.match_reason`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

try:
    from rapidfuzz import fuzz
    _HAS_FUZZ = True
except ImportError:  # pragma: no cover - rapidfuzz is a hard requirement in practice
    _HAS_FUZZ = False

from .store import Store, stable_id, utcnow

# ---------------------------------------------------------------- tuning
#
# These are the numbers that decide whether the calendar is usable. They are
# grouped here so they can be argued about in one place.

# Title similarity (0-100) required for a merge, given the time is close.
TITLE_STRONG = 92.0
# A looser title can still merge if the time is a near-exact match AND the
# venues agree — a venue writing "Foo" and a promoter writing
# "Foo (with Bar)" should merge.
TITLE_WEAK = 78.0

# Start times within this many minutes are "the same slot". Two sources
# routinely disagree by ~30-60min on doors vs show, and timezones are handled
# upstream so this is a genuine disagreement window.
TIME_TIGHT_MIN = 45
TIME_LOOSE_MIN = 180

# Venue separation treated as the same place (~800m, matching what production
# aggregators use).
VENUE_GEO_METERS = 800.0


@dataclass
class MatchResult:
    """Outcome of comparing two listings."""

    merged: bool
    score: float
    title_score: float
    time_delta_min: float | None
    venue_agrees: bool
    reason: str


@dataclass
class Cluster:
    """A set of listings believed to be one event."""

    listings: list[sqlite3.Row] = field(default_factory=list)
    event_id: str | None = None


# ---------------------------------------------------------------- helpers

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def title_similarity(a: str, b: str) -> float:
    """Order-insensitive title similarity, 0-100.

    Token-set comparison first, because billing order varies between a
    venue's listing ("Foo w/ Bar") and a promoter's ("Bar + Foo") while the
    show is identical. Falls back to character-level fuzzy matching for
    typo and OCR-ish variance ("Thge Oh Sees").
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 100.0

    set_a, set_b = set(a.split()), set(b.split())
    if set_a and set_b:
        jaccard = len(set_a & set_b) / len(set_a | set_b)
        if jaccard == 1.0:
            # Same words, different order.
            return 100.0
    else:
        jaccard = 0.0

    if _HAS_FUZZ:
        # token_sort_ratio is order-insensitive. token_set_ratio is not
        # averaged with a Jaccard term: both are already set-based, and
        # blending them dilutes a good signal (a one-character typo scores
        # 91.7 on token_set, but drops under 85 once averaged against a
        # token-overlap ratio). Jaccard is kept only as a tie-breaker when
        # the fuzzy scores disagree.
        char_score = fuzz.token_sort_ratio(a, b)
        partial = fuzz.token_set_ratio(a, b)
    else:  # pragma: no cover
        char_score = partial = 0.0

    fuzzy = max(char_score, partial)
    # Only pull the score down when the fuzzy metrics are middling and the
    # token overlap is poor — that is the signature of two different events
    # that happen to share a prefix.
    if 60.0 <= fuzzy <= 95.0 and jaccard < 0.34:
        return fuzzy * 0.6
    return fuzzy


def venue_distance_m(lat1: float | None, lon1: float | None,
                     lat2: float | None, lon2: float | None) -> float | None:
    """Haversine distance in meters, or None if either point is missing."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371000.0
    p1, p2 = float(lat1) * 3.14159265 / 180, float(lat2) * 3.14159265 / 180
    dp = (float(lat2) - float(lat1)) * 3.14159265 / 180
    dl = (float(lon2) - float(lon1)) * 3.14159265 / 180
    a = __import__("math").sin(dp / 2) ** 2 + __import__("math").cos(p1) * \
        __import__("math").cos(p2) * __import__("math").sin(dl / 2) ** 2
    return 2 * r * __import__("math").asin(a ** 0.5)


# ---------------------------------------------------------------- matching

def compare(
    a: sqlite3.Row,
    b: sqlite3.Row,
    *,
    venue_aliases: dict[str, str] | None = None,
) -> MatchResult:
    """Decide whether two listings are the same event.

    Called only for listings in the same block, but it re-checks the venue
    itself rather than trusting the caller — a block is a hint, not a proof.
    """
    aliases = venue_aliases or {}

    t_score = title_similarity(a["title_norm"] or "", b["title_norm"] or "")

    dt_a, dt_b = _parse_dt(a["starts_at"]), _parse_dt(b["starts_at"])
    if dt_a is None or dt_b is None:
        # No time to compare. Two same-venue listings with a very strong
        # title match is still a merge; anything less is a coin flip we
        # should decline.
        time_delta = None
        venue_ok = _venues_agree(a, b, aliases)
        if t_score >= TITLE_STRONG and venue_ok:
            return MatchResult(True, t_score, t_score, None, venue_ok, "title+venue, no time")
        return MatchResult(False, 0.0, t_score, None, venue_ok, "insufficient evidence")

    time_delta = abs((dt_a - dt_b).total_seconds()) / 60.0
    venue_ok = _venues_agree(a, b, aliases)

    if not venue_ok:
        # Different venues. "Special", "Happy Hour" and a dozen tribute
        # nights all collide on title, so require near-identical titles AND
        # near-identical times before merging across venues. This is the case
        # that catches the same touring act playing two rooms on one night —
        # rare, but a duplicate calendar entry when it happens.
        if t_score >= 98.0 and time_delta <= TIME_TIGHT_MIN:
            return MatchResult(
                False, 0.0, t_score, time_delta, False,
                "same title+time but different venue — declined",
            )
        return MatchResult(False, 0.0, t_score, time_delta, False, "different venue")

    if time_delta <= TIME_TIGHT_MIN:
        merged = t_score >= TITLE_WEAK
        return MatchResult(
            merged,
            t_score if merged else 0.0,
            t_score,
            time_delta,
            venue_ok,
            f"time+venue, title={t_score:.0f}",
        )

    if time_delta <= TIME_LOOSE_MIN:
        # Times are meaningfully different. Only a very strong title saves
        # this, and it is usually a doors/show confusion or a reschedule
        # that has not propagated to all sources.
        merged = t_score >= TITLE_STRONG
        return MatchResult(
            merged,
            t_score * 0.8 if merged else 0.0,
            t_score,
            time_delta,
            venue_ok,
            f"loose time ({time_delta:.0f}m), title={t_score:.0f}",
        )

    return MatchResult(False, 0.0, t_score, time_delta, venue_ok, "times too far apart")


def _venues_agree(a: sqlite3.Row, b: sqlite3.Row, aliases: dict[str, str]) -> bool:
    va, vb = a["venue_id"], b["venue_id"]
    if va and vb:
        if va == vb:
            return True
        # Alias handling lets "The Royal" and "Royal Theater" resolve to one
        # place once configured.
        if aliases.get(va) and aliases.get(va) == vb:
            return True
        if aliases.get(vb) and aliases.get(vb) == va:
            return True
    # Fall back to name text when neither listing resolved a venue id.
    na = (a["venue_name_raw"] or "").strip().lower()
    nb = (b["venue_name_raw"] or "").strip().lower()
    if na and nb:
        return na == nb or na in nb or nb in na
    # No venue information on either side: do not treat that as agreement.
    # Two unknown venues is not evidence they are the same room.
    return False


# ---------------------------------------------------------------- resolver

class Resolver:
    """Groups listings into events and maintains the event rows."""

    def __init__(self, store: Store, venue_aliases: dict[str, str] | None = None):
        self.store = store
        self.venue_aliases = venue_aliases or {}

    def block_key(self, listing: sqlite3.Row, tz_name: str = "America/Los_Angeles") -> str | None:
        """Coarse bucket for candidate matching.

        A listing with no start time cannot be blocked by date, so we fall
        back to blocking on venue alone, which is coarser but still prevents
        cross-town comparisons.
        """
        dt = _parse_dt(listing["starts_at"])
        if dt is None:
            return f"venue:{listing['venue_id'] or listing['venue_name_raw'] or '?'}"
        local = dt.astimezone(ZoneInfo(tz_name))
        venue = listing["venue_id"] or listing["venue_name_raw"] or "?"
        return f"{venue}|{local.date().isoformat()}"

    def candidate_blocks(self, listing: sqlite3.Row, tz_name: str) -> list[str]:
        """Blocks to search for a merge partner.

        Includes the previous and next calendar day. A show that runs past
        midnight, and a source that reports a UTC date while another reports
        local, would otherwise land in different blocks.
        """
        key = self.block_key(listing, tz_name)
        if key is None:
            return []
        dt = _parse_dt(listing["starts_at"])
        if dt is None:
            return [key]
        local = dt.astimezone(ZoneInfo(tz_name))
        out = [key]
        for delta in (-1, 1):
            neighbor = (local + timedelta(days=delta)).date().isoformat()
            out.append(f"{key.split('|')[0]}|{neighbor}")
        return out

    def resolve(self, tz_name: str = "America/Los_Angeles") -> dict:
        """Run resolution over all listings. Returns a summary dict.

        Idempotent: safe to re-run after every scan. Existing event
        assignments are recomputed from scratch so a change in one listing
        can cause a cluster to split, which is what we want when a source
        corrects itself.
        """
        listings = self.store.query(
            "SELECT * FROM listings ORDER BY starts_at, id"
        )
        if not listings:
            return {"events": 0, "listings": 0, "merged": 0, "singletons": 0}

        # 1. Block.
        blocks: dict[str, list[sqlite3.Row]] = {}
        for listing in listings:
            key = self.block_key(listing, tz_name)
            if key:
                blocks.setdefault(key, []).append(listing)
        # Undatable listings form their own blocks keyed by id so they can
        # still be clustered among themselves.
        undated = [l for l in listings if not _parse_dt(l["starts_at"])]
        for listing in undated:
            blocks.setdefault(f"nodate:{listing['id']}", []).append(listing)

        clusters: list[Cluster] = []
        for members in blocks.values():
            clusters.extend(self._cluster_block(members))

        # 2. Persist.
        self.store.execute("DELETE FROM event_listings")
        self.store.execute(
            "UPDATE events SET active = 0 WHERE last_seen_at < ?",
            (utcnow(),),
        )

        summary = {"events": 0, "listings": len(listings), "merged": 0, "singletons": 0}
        for cluster in clusters:
            self._persist_cluster(cluster, tz_name)
            summary["events"] += 1
            if len(cluster.listings) > 1:
                summary["merged"] += len(cluster.listings) - 1
            else:
                summary["singletons"] += 1
        return summary

    def _cluster_block(self, members: list[sqlite3.Row]) -> list[Cluster]:
        """Union-find within a block.

        Order matters: we process strongest pairs first so the best evidence
        forms the core of a cluster, and weaker pairs can then attach to it
        rather than forming their own competing group.
        """
        parent: dict[int, int] = {m["id"]: m["id"] for m in members}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        pairs: list[tuple[float, sqlite3.Row, sqlite3.Row, MatchResult]] = []
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if a["venue_id"] and b["venue_id"] and a["venue_id"] != b["venue_id"]:
                    # Cheap pre-filter; compare() also checks, but skipping
                    # the fuzzy math on most pairs is the point of blocking.
                    if not (
                        a["venue_id"] in (self.venue_aliases or {})
                        or self.venue_aliases.get(a["venue_id"]) == b["venue_id"]
                        or self.venue_aliases.get(b["venue_id"]) == a["venue_id"]
                    ):
                        continue
                result = compare(a, b, venue_aliases=self.venue_aliases)
                if result.merged:
                    pairs.append((result.score, a, b, result))

        for _score, a, b, _r in sorted(pairs, key=lambda p: -p[0]):
            union(a["id"], b["id"])

        grouped: dict[int, Cluster] = {}
        for m in members:
            grouped.setdefault(find(m["id"]), Cluster()).listings.append(m)
        return list(grouped.values())

    def _persist_cluster(self, cluster: Cluster, tz_name: str) -> None:
        members = sorted(cluster.listings, key=lambda r: (r["venue_id"] is None, r["id"]))
        canonical = members[0]

        source_ids = {m["source_id"] for m in members}
        starts = [_parse_dt(m["starts_at"]) for m in members]
        starts = [s for s in starts if s]
        # Use the earliest stated start: sources more often round late (doors)
        # than early. Erring early is also safer for a calendar.
        canonical_start = min(starts) if starts else None

        title = self._best_title(members)
        title_norm = canonical["title_norm"]
        venue_id = canonical["venue_id"]

        # Event id is derived from the stable facts of the cluster, so a
        # re-resolve produces the same id and history survives.
        event_id = stable_id(
            "evt",
            title_norm,
            canonical_start.isoformat() if canonical_start else "",
            venue_id or "",
        )

        existing = self.store.get_event(event_id)
        record = {
            "title": title,
            "title_norm": title_norm,
            "description": self._best_description(members),
            "starts_at": canonical_start.isoformat() if canonical_start else canonical["starts_at"] or "",
            "ends_at": self._best_ends(members),
            "timezone": tz_name,
            "venue_id": venue_id,
            "status": self._best_status(members),
            "ticket_url": self._best_field(members, "ticket_url"),
            "price": self._best_field(members, "price"),
            "image_url": self._best_field(members, "image_url"),
            "source_count": len(source_ids),
            "listing_count": len(members),
            "confidence": self._confidence(members, source_ids),
            "last_seen_at": utcnow(),
            # The pre-pass marks every previously seen event inactive.
            # A cluster we are writing still has its listings, so it stays up,
            # including when resolve() runs a second time.
            "active": 1,
        }

        # needs_review is computed for BOTH new and existing events. For a new
        # event this is the only chance to compute it at all — previously a
        # freshly inserted event kept the column default and silently bypassed
        # the whole policy, which is how a merged 3-source show shipped with
        # needs_review=1 and reason=NULL.
        needs_review, reason = self._review_decision(record, members)
        record["needs_review"] = int(needs_review)
        record["review_reason"] = reason

        if existing is None:
            self.store.insert_event(id=event_id, **record)
        else:
            # A status change is the signal that matters; record it so the
            # feed can emit a cancellation instead of silently dropping it.
            if existing["status"] != record["status"]:
                self.store.record_change(
                    event_id, "status", existing["status"], record["status"],
                    reason="listing status changed",
                )
                if record["status"] == "EventCancelled":
                    record["cancelled_at"] = utcnow()
            if existing["starts_at"] != record["starts_at"]:
                self.store.record_change(
                    event_id, "starts_at", existing["starts_at"], record["starts_at"],
                    reason="rescheduled on some source",
                )
            self.store.update_event(event_id, **record)

        for member in members:
            match_score = None
            reason = None
            if member["id"] != canonical["id"]:
                result = compare(canonical, member, venue_aliases=self.venue_aliases)
                match_score, reason = result.score, result.reason
            self.store.execute(
                """
                INSERT OR REPLACE INTO event_listings
                    (event_id, listing_id, match_score, match_reason)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, member["id"], match_score, reason),
            )

        for member in members:
            self._link_performers(event_id, member)

    def _link_performers(self, event_id: str, listing: sqlite3.Row) -> None:
        from .normalize import clean_performer_name, split_performers

        text = f"{listing['title_raw'] or ''} {listing['description'] or ''}"
        for name, billing in split_performers(listing["title_raw"] or ""):
            cleaned = clean_performer_name(name)
            if not cleaned:
                continue
            performer_id = self.store.ensure_performer(cleaned)
            self.store.link_performer(event_id, performer_id, billing, name)
        del text

    def _best_title(self, members: Sequence[sqlite3.Row]) -> str:
        """Prefer the longest non-empty title: it usually carries the billing
        and the "with" clause, which is what a human wants to see."""
        titles = [m["title_raw"] for m in members if m["title_raw"]]
        return max(titles, key=len) if titles else ""

    def _best_description(self, members: Sequence[sqlite3.Row]) -> str | None:
        descs = [m["description"] for m in members if m["description"]]
        return max(descs, key=len) if descs else None

    def _best_ends(self, members: Sequence[sqlite3.Row]) -> str | None:
        ends = [m["ends_at"] for m in members if m["ends_at"]]
        return ends[0] if ends else None

    def _best_status(self, members: Sequence[sqlite3.Row]) -> str:
        """Cancellation is sticky and dominant.

        If ANY source says cancelled, the event is cancelled — a venue that
        cancels rarely tears down its own listing, so one source usually
        learns about it first. Taking the most severe status avoids showing a
        cancelled show as upcoming.
        """
        statuses = {m["status"] for m in members}
        for severe in ("EventCancelled", "EventPostponed", "EventRescheduled"):
            if severe in statuses:
                return severe
        return "EventScheduled"

    def _best_field(self, members: Sequence[sqlite3.Row], field_name: str) -> str | None:
        values = [m[field_name] for m in members if m[field_name]]
        if not values:
            return None
        # Prefer a value that appears more than once — agreement beats
        # specificity when two sources disagree.
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return max(counts, key=lambda v: (counts[v], len(v)))

    def _confidence(self, members: Sequence[sqlite3.Row], source_ids: set[str]) -> float:
        """Corroboration confidence, 0..1.

        Built from the count of DISTINCT sources, not listings. Ten posts of
        the same flyer is one piece of evidence; the venue site and a
        ticketing site are two.

        Diminishing returns: 1 source is thin, 2 is the minimum to publish,
        3+ is solid. Scaled so the curve flattens rather than rewarding a
        dozen scrapes of one page.
        """
        n = len(source_ids)
        base = {0: 0.0, 1: 0.35, 2: 0.7, 3: 0.85}.get(n, 0.85 + min(0.13, (n - 3) * 0.02))

        # Agreement penalty: sources that disagree on the start time reduce
        # confidence even when they agree on the title.
        starts = [_parse_dt(m["starts_at"]) for m in members]
        starts = [s for s in starts if s]
        if len(starts) > 1:
            spread = (max(starts) - min(starts)).total_seconds() / 60.0
            if spread > TIME_TIGHT_MIN:
                base *= 0.85
            if spread > TIME_LOOSE_MIN:
                base *= 0.7

        # Retraction penalty: a listing that has gone missing is a warning.
        missing = sum(1 for m in members if m["missing_since"])
        if missing:
            base *= 0.8 ** missing

        return round(max(0.0, min(1.0, base)), 3)

    @staticmethod
    def _cancel_sources(members: Sequence[sqlite3.Row]) -> int:
        """How many distinct sources assert EventCancelled.

        Distinct by source_id, not listing count: one source with three
        listings that all flipped is still one voice.
        """
        return len({
            m["source_id"] for m in members if m["status"] == "EventCancelled"
        })

    def _review_decision(
        self, record: dict, members: Sequence[sqlite3.Row]
    ) -> tuple[bool, str | None]:
        """Decide whether this event needs a human before it hits the feed.

        The user asked to start by adding everything, so this is permissive
        by default: only genuinely unverifiable things are held back. The
        flag exists so a later "be stricter" change is a config flip, not a
        rewrite.
        """
        if not record["starts_at"]:
            return True, "no start time could be determined"
        if record["source_count"] < 1:
            return True, "no source"
        if record["status"] == "EventCancelled" and self._cancel_sources(members) < 2:
            # A cancellation confirmed by only one source is usually a venue
            # rotating its calendar, not a real cancellation. Count the
            # sources that actually assert cancellation — NOT source_count,
            # which counts every source listing the event. A show listed by
            # the venue and a ticketing site still has source_count=2 when
            # only the venue has cancelled it, and that must be held back.
            return True, (
                "cancellation asserted by a single source "
                "(likely calendar rotation)"
            )
        if not record["venue_id"]:
            return True, "venue could not be identified"
        if record["confidence"] < 0.3:
            return True, f"low confidence ({record['confidence']})"
        del members
        return False, None
