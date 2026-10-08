"""Tests for entities.py — the tree, the items, and the citation rule.

The two rules under test are the ones the project actually commits to:
  1. A fact is publishable only if a public source backs it.
  2. Conflicting information is preserved, never resolved.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from towncrier import entities as E  # noqa: E402
from towncrier.store import Store  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name}\n     got:  {got!r}\n     want: {want!r}")


def check_true(name: str, cond, detail: str = "") -> None:
    check(name if cond else f"{name} [{detail}]", bool(cond), True)


def new_store() -> Store:
    return Store(Path(tempfile.mkdtemp(prefix="tc-ent-")) / "t.db")


# ------------------------------------------------------------ normalization

check("phone digits only", E.normalize_item("phone", "(707) 543-1234"), "7075431234")
check("phone country code", E.normalize_item("phone", "+1 707 543 1234"), "7075431234")
check(
    "phone formats agree",
    E.normalize_item("phone", "707.543.1234"),
    E.normalize_item("phone", "(707) 543-1234"),
)
check("email lowercase", E.normalize_item("email", "  Book@Royal.COM "), "book@royal.com")
check("website strips scheme", E.normalize_item("website", "https://theroyal.com/"), "theroyal.com")
check("social strips @", E.normalize_item("social", "@TheRoyalSR"), "theroyalsr")
check("address collapses whitespace", E.normalize_item("address", " 150   1st St "), "150 1st st")

# ------------------------------------------------------------ the tree

s = new_store()
trunk = E.ensure_entity(s, name="Metropolis", kind="city")
branch = E.ensure_entity(s, name="The Royal", kind="venue", parent_id=trunk, role="host")
leaf = E.ensure_entity(s, name="Fela Kuti Tribute", kind="band", parent_id=branch)
promo = E.ensure_entity(s, name="Gator Events", kind="promoter", role="booking")

check("trunk is a city", s.get_entity(trunk)["kind"], "city")
check("branch parented to trunk", s.get_entity(branch)["parent_id"], trunk)
check("leaf parented to branch", s.get_entity(leaf)["parent_id"], branch)
check("promoter has no parent", s.get_entity(promo)["parent_id"], None)

# Idempotent
again = E.ensure_entity(s, name="The Royal", kind="venue", parent_id=trunk)
check("ensure_entity is idempotent", again, branch)
check("no duplicate rows", s.one("SELECT COUNT(*) c FROM entities")["c"], 4)

# Many-to-many: a promoter books several branches.
branch2 = E.ensure_entity(s, name="Other Club", kind="venue", parent_id=trunk, role="host")
E.link(s, promo, branch, "books")
E.link(s, promo, branch2, "books")
E.link(s, leaf, branch, "plays_at")
check(
    "promoter books two venues",
    s.one("SELECT COUNT(*) c FROM entity_links WHERE from_id=? AND rel='books'", (promo,))["c"],
    2,
)
E.link(s, promo, branch, "books")
check(
    "duplicate link is ignored",
    s.one("SELECT COUNT(*) c FROM entity_links WHERE from_id=? AND rel='books'", (promo,))["c"],
    2,
)
E.link(s, promo, promo, "books")
check(
    "self-link is refused",
    s.one("SELECT COUNT(*) c FROM entity_links WHERE from_id=?", (promo,))["c"],
    2,
)

# ------------------------------------------------------------ rule 1: citation

s2 = new_store()
ven = E.ensure_entity(s2, name="Venue A", kind="venue")

# No source_url and not manual -> refused.
try:
    E.add_item(s2, entity_id=ven, kind="phone", value="707-555-0100")
    check("uncited fact is refused", "no exception", "UncitedFact")
except E.UncitedFact:
    check("uncited fact is refused", True, True)

# Declaring it manual is the only way through.
i = E.add_item(
    s2, entity_id=ven, kind="phone", value="707-555-0100",
    citation_kind="manual", display="(707) 555-0100",
)
check("manual fact is allowed", isinstance(i, int), True)
check("manual fact stored", s2.one("SELECT COUNT(*) c FROM items")["c"], 1)

# With a real public source it just works.
i2 = E.add_item(
    s2, entity_id=ven, kind="email", value="booking@venuea.com",
    source_id="venuea_site", source_url="https://venuea.com/contact",
    citation_kind="structured_data",
)
check("cited fact is allowed", isinstance(i2, int), True)
check("every fact has a citation", len(E.uncited(s2)), 0)

# A derived fact is allowed to exist but is never trusted on its own.
i3 = E.add_item(
    s2, entity_id=ven, kind="website", value="venuea.com",
    source_url="https://directory.test/venuea", citation_kind="derived",
)
check("derived fact recorded", isinstance(i3, int), True)
check("derived confidence is low", s2.one(
    "SELECT confidence FROM items WHERE id=?", (i3,))["confidence"], 0.2)

# A different source re-asserting the same value adds provenance without
# duplicating the fact. Distinct source_ids: the citation key is
# (item_id, source_id), so two URLs under one source_id collapse by design.
E.add_item(
    s2, entity_id=ven, kind="email", value="booking@venuea.com",
    source_id="city_guide", source_url="https://venuea.com/",
    citation_kind="structured_data",
)
check("same value is one row", s2.one(
    "SELECT COUNT(*) c FROM items WHERE entity_id=? AND kind='email'", (ven,))["c"], 1)
check("both citations recorded", s2.one(
    "SELECT COUNT(*) c FROM citations WHERE item_id=?", (i2,))["c"], 2)
check("both source urls retained", sorted(
    r["source_url"] for r in E.provenance(s2, i2)
), ["https://venuea.com/", "https://venuea.com/contact"])

# Bad kind is a hard error, not a silent 'other'.
try:
    E.add_item(s2, entity_id=ven, kind="wifi_password", value="hunter2",
               source_url="https://venuea.com")
    check("unknown kind refused", "no exception", "ValueError")
except ValueError:
    check("unknown kind refused", True, True)

# ------------------------------------------------------------ rule 2: conflicts

s3 = new_store()
v = E.ensure_entity(s3, name="Venue B", kind="venue")
a = E.add_item(s3, entity_id=v, kind="phone", value="(707) 111-2222",
               source_url="https://venueb.com", citation_kind="structured_data")
b = E.add_item(s3, entity_id=v, kind="phone", value="707-333-4444",
               source_url="https://directory.test/venueb", citation_kind="html")

check("two conflicting values both stored", s3.one(
    "SELECT COUNT(*) c FROM items WHERE entity_id=? AND kind='phone'", (v,))["c"], 2)
check("first is flagged as disputed", s3.one(
    "SELECT conflicts_with FROM items WHERE id=?", (a,))["conflicts_with"], b)
check("second is flagged as disputed", s3.one(
    "SELECT conflicts_with FROM items WHERE id=?", (b,))["conflicts_with"], a)
check("conflicts are reported", len(E.conflicted(s3, v)), 2)

# Neither value is deleted or overwritten.
vals = {r["value"] for r in E.items_for(s3, v, "phone")}
check("both values survive", vals, {"7071112222", "7073334444"})

# The venue's own site outranks the directory.
ordered = E.items_for(s3, v, "phone")
check("trusted value sorts first", ordered[0]["value"], "7071112222")
check("both are marked disputed", all(r["conflicts_with"] is not None for r in ordered), True)

# A third, corroborating source for the FIRST value is not a conflict.
E.add_item(s3, entity_id=v, kind="phone", value="(707) 111-2222",
           source_id="city_guide", source_url="https://cityguide.test/venueb",
           citation_kind="html")
check("corroboration is not a conflict", s3.one(
    "SELECT COUNT(*) c FROM items WHERE entity_id=? AND kind='phone'", (v,))["c"], 2)
check("trusted value now has 2 citations", s3.one(
    "SELECT COUNT(*) c FROM citations WHERE item_id=?", (a,))["c"], 2)

# Absence is not a conflict: a venue with no phone at all is fine.
s4 = new_store()
v2 = E.ensure_entity(s4, name="Venue C", kind="venue")
E.add_item(s4, entity_id=v2, kind="website", value="venuec.com",
           source_url="https://venuec.com", citation_kind="structured_data")
check("venue with no phone is still a record", s4.one(
    "SELECT COUNT(*) c FROM entities WHERE id=?", (v2,))["c"], 1)
check("no phantom conflicts", len(E.conflicted(s4)), 0)
check("phone reported as not_found", E.KIND_PHONE in
      E.venue_dossier(s4, v2)["not_found"], True)

# ------------------------------------------------------------ dossier

dossier = E.venue_dossier(s3, v)
check("dossier has the name", dossier["name"], "Venue B")
check_true("dossier carries a source url per fact",
           all(f["sources"] and f["sources"][0]["url"]
               for fs in dossier["facts"].values() for f in fs),
           str(dossier["facts"]))
check_true("dossier marks disputed facts",
           all(f["disputed"] for f in dossier["facts"]["phone"]), "")
check_true("dossier reports what we did not find",
           E.KIND_EMAIL in dossier["not_found"], str(dossier["not_found"]))

# ------------------------------------------------------------ summary

print("=" * 70)
print("ENTITIES / ITEMS TESTS")
print("=" * 70)
for f in FAILURES:
    print(f"  FAIL  {f}")
print("-" * 70)
print(f"{PASS} passed, {FAIL} failed")
print("=" * 70)

sys.exit(1 if FAIL else 0)
