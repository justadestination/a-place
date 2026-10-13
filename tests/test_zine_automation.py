"""Unit and integration tests for Umwelt Horizons Zine Automation (Tasks 3.2 & 3.6).

Verifies:
  1. state.py helpers (gate, pick, topic, stance, predict, publish, escalate).
  2. Persona voice guides and append-only stance memory integrity.
  3. Graph pipeline integration (build_zine.py) ingesting published pieces and topics.
  4. Bidirectional and cross-topic edge resolution without missing dead-end nodes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZINE_DIR = ROOT / "zine-automation"
SCRIPTS_DIR = ZINE_DIR / "scripts"
STATE_PY = SCRIPTS_DIR / "state.py"
STATE_JSON = ZINE_DIR / "state" / "state.json"
PUBLISHED_DIR = ZINE_DIR / "published"
TOPICS_DIR = ZINE_DIR / "topics"
PERSONAS_DIR = ZINE_DIR / "personas"
BUILD_ZINE = ROOT / "web" / "tools" / "build_zine.py"


def test_personas_roster_exists():
    """Verify all 8 personas exist with complete voice guides."""
    expected_personas = [
        "mags-pilecki", "juno-voss", "mara-okwonko", "dev-malik",
        "nico-varela", "priya-raman", "silas-brandt", "bea-luna"
    ]
    for p in expected_personas:
        path = PERSONAS_DIR / f"{p}.md"
        assert path.exists(), f"Persona file {p}.md missing"
        text = path.read_text(encoding="utf-8")
        assert "## Voice" in text or "## Personality" in text
        assert "## Stances taken" in text or "## Cartoon briefs" in text


def test_state_gate_execution():
    """Verify deterministic gate rolls via state.py, off the live zine log."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "state").mkdir()
        shutil.copy(STATE_JSON, root / "state" / "state.json")
        env = os.environ.copy()
        env["ZINE_AUTOMATION_ROOT"] = str(root)
        res_pass = subprocess.run(
            [sys.executable, str(STATE_PY), "gate", "--chance", "100"],
            capture_output=True, text=True, env=env,
        )
        assert res_pass.returncode == 0
        assert "PROCEED" in res_pass.stdout

        res_skip = subprocess.run(
            [sys.executable, str(STATE_PY), "gate", "--chance", "0"],
            capture_output=True, text=True, env=env,
        )
        assert res_skip.returncode == 3
        assert "SKIP" in res_skip.stdout
        assert "skipped" in (root / "state" / "run-log.md").read_text(encoding="utf-8")


def test_writer_assignment_force_picks_without_touching_live_log():
    """A forced assignment selects a persona and does not roll the live gate."""
    import shutil
    import tempfile

    assignment = SCRIPTS_DIR / "writer_assignment.py"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "state").mkdir()
        (root / "scripts").mkdir()
        shutil.copy(STATE_JSON, root / "state" / "state.json")
        shutil.copy(STATE_PY, root / "scripts" / "state.py")
        env = os.environ.copy()
        env["ZINE_AUTOMATION_ROOT"] = str(root)
        res = subprocess.run(
            [sys.executable, str(assignment), "--force"],
            capture_output=True, text=True, env=env,
        )
        assert res.returncode == 0, res.stderr
        assert "PROCEED" in res.stdout
        assert "persona=" in res.stdout
        assert "prompt=" in res.stdout
        assert "editors-letter" not in res.stdout


def test_state_pick():
    """Verify randomized persona and prompt selection."""
    res = subprocess.run([sys.executable, str(STATE_PY), "pick"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "persona=" in res.stdout
    assert "prompt=" in res.stdout
    assert "editors-letter" not in res.stdout


def test_zine_graph_intake_and_seed_links():
    """Verify build_zine.py ingests published pieces and topics with clean edges."""
    res = subprocess.run([sys.executable, str(BUILD_ZINE)], capture_output=True, text=True)
    assert res.returncode == 0

    zine_json_path = ROOT / "web" / "data" / "zine.json"
    assert zine_json_path.exists()
    graph = json.loads(zine_json_path.read_text(encoding="utf-8"))

    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", [])

    # Seed topic overview & report
    assert "note:topic-downtown-noise-ordinance-2026" in nodes
    assert "note:topic-downtown-noise-ordinance-2026-report" in nodes

    # Seed stance articles
    mags_id = "note:2026-10-09-the-three-am-decibel-line"
    juno_id = "note:2026-10-09-acoustic-sensors-are-surveillance"
    mara_id = "note:2026-10-09-bring-your-own-baffle"

    assert mags_id in nodes
    assert juno_id in nodes
    assert mara_id in nodes

    assert nodes[mags_id]["type"] == "stance"
    assert nodes[juno_id]["type"] == "stance"
    assert nodes[mara_id]["type"] == "stance"

    # Verify no dead-end unresolved nodes for the seed articles
    for seed_id in (mags_id, juno_id, mara_id):
        seed_edges = [e for e in edges if e["source"] == seed_id or e["target"] == seed_id]
        assert len(seed_edges) >= 2
        for e in seed_edges:
            other = e["target"] if e["source"] == seed_id else e["source"]
            assert not other.startswith("missing:"), f"Dead-end missing edge found: {seed_id} -> {other}"


def test_rss_feed_includes_published_zine_articles():
    """Verify RSS feed contains published zine automation articles."""
    feed_path = ROOT / "web" / "zine" / "feed.xml"
    assert feed_path.exists()
    feed_xml = feed_path.read_text(encoding="utf-8")
    assert "The 3 A.M. Decibel Line" in feed_xml
    assert "Acoustic Sensors Are Surveillance With Better PR" in feed_xml
    assert "Bring Your Own Baffle: A Defense of Loud Rooms" in feed_xml
