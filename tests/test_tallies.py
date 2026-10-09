"""Automated tests for Task 2.1: Attendance Tally backend (+/− attendance votes).

Specifications per Decision 004:
- [abuse] rapid +/− toggling from one agent collapses to a single vote
- [abuse] one human minting multiple agent identities behaves per the 0.4 issuance rules
- [int] verified and unverified votes tallied separately
- [unit] deduplication (1 vote per steward per event), retract functionality
"""

import sys
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shadenet.towncrier.store import Store
from shadenet.nightcal.votes import (
    ensure_votes,
    record_vote,
    get_event_tally,
    tally_map,
    normalize_direction,
)


class TestTalliesBackend(unittest.TestCase):
    def setUp(self):
        # In-memory store for isolation
        self.store = Store(":memory:")
        ensure_votes(self.store)

    def tearDown(self):
        self.store.close()

    def test_normalize_direction(self):
        self.assertEqual(normalize_direction("+"), "+")
        self.assertEqual(normalize_direction("up"), "+")
        self.assertEqual(normalize_direction("yes"), "+")
        self.assertEqual(normalize_direction("-"), "−")
        self.assertEqual(normalize_direction("−"), "−")
        self.assertEqual(normalize_direction("down"), "−")
        self.assertEqual(normalize_direction("retract"), "retract")
        self.assertEqual(normalize_direction("cancel"), "retract")
        self.assertIsNone(normalize_direction("invalid_direction"))

    def test_rapid_toggling_collapses_to_single_vote(self):
        """[abuse test] Rapid +/− toggling from one agent collapses to a single vote."""
        event_id = "evt_speed_01"
        steward_id = "steward_fast_finger"

        # Toggle 150 times rapidly
        for i in range(150):
            direction = "+" if (i % 2 == 0) else "−"
            res = record_vote(self.store, event_id, direction, steward_id=steward_id, verified=True)
            self.assertTrue(res["ok"])

        # Final direction in loop was − (index 149 is odd)
        rows = self.store.query(
            "SELECT * FROM nightcal_tallies WHERE event_id = ? AND steward_id = ?",
            (event_id, steward_id)
        )
        self.assertEqual(len(rows), 1, "Must collapse to exactly one row in the database")
        self.assertEqual(rows[0]["direction"], "−")

        tally = get_event_tally(self.store, event_id)
        self.assertEqual(tally["ups"], 0)
        self.assertEqual(tally["downs"], 1)
        self.assertEqual(tally["score"], -1)
        self.assertEqual(tally["bodies"], 0)

    def test_dedup_and_retract(self):
        """[unit test] Idempotent updates and vote retraction."""
        event_id = "evt_dance_99"
        steward_id = "steward_alice"

        # Cast positive vote
        r1 = record_vote(self.store, event_id, "+", steward_id=steward_id)
        self.assertTrue(r1["ok"])
        t1 = get_event_tally(self.store, event_id)
        self.assertEqual(t1["bodies"], 1)
        self.assertEqual(t1["score"], 1)

        # Cast same vote again -> no duplicate count
        r2 = record_vote(self.store, event_id, "+", steward_id=steward_id)
        self.assertTrue(r2["ok"])
        t2 = get_event_tally(self.store, event_id)
        self.assertEqual(t2["bodies"], 1)

        # Flip vote to negative
        r3 = record_vote(self.store, event_id, "down", steward_id=steward_id)
        self.assertTrue(r3["ok"])
        t3 = get_event_tally(self.store, event_id)
        self.assertEqual(t3["bodies"], 0)
        self.assertEqual(t3["downs"], 1)
        self.assertEqual(t3["score"], -1)

        # Retract vote
        r4 = record_vote(self.store, event_id, "retract", steward_id=steward_id)
        self.assertTrue(r4["ok"])
        t4 = get_event_tally(self.store, event_id)
        self.assertEqual(t4["bodies"], 0)
        self.assertEqual(t4["downs"], 0)
        self.assertEqual(t4["score"], 0)

    def test_verified_and_unverified_votes_tallied_separately(self):
        """[int test] Verified and unverified votes tallied separately; unverified do not affect public bodies."""
        event_id = "evt_concert_42"

        # 3 verified stewards planning to attend
        record_vote(self.store, event_id, "+", steward_id="steward_v1", verified=True)
        record_vote(self.store, event_id, "+", steward_id="steward_v2", verified=True)
        record_vote(self.store, event_id, "+", steward_id="steward_v3", verified=True)

        # 1 verified steward not attending
        record_vote(self.store, event_id, "−", steward_id="steward_v4", verified=True)

        # 5 unverified bot / unauthenticated votes
        for i in range(5):
            record_vote(self.store, event_id, "+", steward_id=f"unverified_bot_{i}", verified=False)

        # Public attendance gauge must only count verified stewards
        public_tally = get_event_tally(self.store, event_id, include_unverified=False)
        self.assertEqual(public_tally["ups"], 3, "Only verified + votes count towards public heads")
        self.assertEqual(public_tally["downs"], 1, "Only verified − votes count towards public downs")
        self.assertEqual(public_tally["bodies"], 3)
        self.assertEqual(public_tally["score"], 2)

        # Internal/diagnostic breakdown can view raw unverified data
        raw_tally = get_event_tally(self.store, event_id, include_unverified=True)
        self.assertEqual(raw_tally["ups"], 8, "Includes unverified votes when explicitly requested")

        # tally_map reflects verified
        tm = tally_map(self.store)
        self.assertEqual(tm[event_id], (3, 1))

    def test_multiple_stewards_headcount(self):
        """[unit test] Multiple verified stewards build an accurate attendance headcount."""
        event_id = "evt_headcount"
        for i in range(12):
            record_vote(self.store, event_id, "+", steward_id=f"steward_{i:02d}", verified=True)
        for i in range(4):
            record_vote(self.store, event_id, "−", steward_id=f"steward_pass_{i:02d}", verified=True)

        tally = get_event_tally(self.store, event_id)
        self.assertEqual(tally["bodies"], 12)
        self.assertEqual(tally["downs"], 4)
    def test_surface_load_rows_reflects_tallies(self):
        """[int test] surface.load_rows reflects event attendance tallies and bodies count."""
        from shadenet.nightcal.surface import load_rows

        # Seed sample venue and event
        self.store.execute("CREATE TABLE IF NOT EXISTS venues (id TEXT PRIMARY KEY, name TEXT, handles TEXT)")
        self.store.execute("CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, kind TEXT, name TEXT, meta TEXT)")
        self.store.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, title TEXT, starts_at TEXT, ends_at TEXT,
                status TEXT, venue_id TEXT, confidence REAL, needs_review INTEGER,
                source_count INTEGER, ticket_url TEXT, image_url TEXT, active INTEGER
            )
        """)
        self.store.execute("CREATE TABLE IF NOT EXISTS listings (id TEXT PRIMARY KEY, url TEXT, source_id TEXT, raw_json TEXT, venue_name_raw TEXT, description TEXT, title_raw TEXT, starts_at TEXT, ends_at TEXT)")
        self.store.execute("CREATE TABLE IF NOT EXISTS event_listings (event_id TEXT, listing_id TEXT)")

        self.store.execute("INSERT INTO venues (id, name) VALUES ('v1', 'The Shady Room')")
        self.store.execute("""
            INSERT INTO events (id, title, title_norm, starts_at, venue_id, active, confidence, needs_review, source_count)
            VALUES ('e1', 'Friday Night Jazz', 'friday night jazz', '2026-10-09T20:00:00Z', 'v1', 1, 1.0, 0, 1)
        """)
        self.store.execute("INSERT INTO sources (id, kind) VALUES ('src1', 'manual')")
        self.store.execute("""
            INSERT INTO listings (id, source_id, external_id, title_raw, title_norm, url, raw_json)
            VALUES (1, 'src1', 'ext1', 'Friday Night Jazz', 'friday night jazz', 'https://venue.com/jazz', '{}')
        """)
        self.store.execute("INSERT INTO event_listings (event_id, listing_id) VALUES ('e1', 1)")

        # Cast 4 verified + votes and 1 - vote
        for i in range(4):
            record_vote(self.store, 'e1', '+', steward_id=f'steward_fan_{i}', verified=True)
        record_vote(self.store, 'e1', '−', steward_id='steward_busy', verified=True)

        venues, events, hidden = load_rows(self.store)
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt["id"], "e1")
        self.assertEqual(evt["up"], 4)
        self.assertEqual(evt["down"], 1)
        self.assertEqual(evt["score"], 3)
        self.assertEqual(evt["bodies"], 4)


if __name__ == "__main__":
    unittest.main()
