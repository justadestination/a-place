"""The flag order grammar in Python and in pennant.js must agree.

Both read ``tests/data/order_vectors.json``. Add a case there when either
parser changes.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shadenet.serendipilyst.flash import apply_order
from shadenet.serendipilyst.store import FlagError

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "tests" / "data" / "order_vectors.json").read_text())


@pytest.mark.parametrize("row", VECTORS, ids=[row["order"][:40] for row in VECTORS])
def test_python_order_matches_vector(row):
    if "error" in row:
        with pytest.raises(FlagError) as caught:
            apply_order(row["order"], row.get("base"))
        assert str(caught.value) == row["error"]
        return
    heard = apply_order(row["order"], row.get("base"))
    look = heard["appearance"]
    profile = heard["profile"] or {}
    assert {
        "field": look["field"],
        "charge": look["charge"],
        "motto": look["motto"],
        "line": look.get("line", "heavy"),
        "ribbon": look.get("ribbon", True),
        "fly": look.get("fly", ""),
        "listed": heard["listed"],
        "place_id": heard["place_id"],
        "intents": profile.get("intents") or [],
        "good_at": profile.get("good_at"),
        "enjoy": profile.get("enjoy"),
        "refuse": profile.get("refuse"),
    } == row["expect"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_pennant_js_matches_vectors():
    run = subprocess.run(
        ["node", str(ROOT / "tests" / "js" / "order_vectors.mjs")],
        capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 0, run.stdout + run.stderr
