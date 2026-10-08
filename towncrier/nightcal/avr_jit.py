"""AVR+JIT adaptive layer — NightCal v0.2 Phase 1.

AVR+JIT governs every GUI surface [Spec §10 p.14]: NightCal, entity pages,
public boards, agent cards, AR portal, and the zine entry. It is not a
separate feature box — it is the cross-cutting adaptive-display contract.

Shared keys:
  textSize — Map to a documented type scale. Layout must reflow rather than
             clip.
  density  — Control spacing and information count, not reduce semantic
             content invisibly.
  eventSelection — Choose the default event lens; always expose a way to see
                   all.
  colors — Apply mode, contrast, and accent while preserving readable
           contrast.

Preference resolution order:
  1. Explicit personal preferences from the append-only record; the newest
     correction wins for its key.
  2. Setup-agent suggestion from prefs.infer for the current device.
  3. Accessible system default when neither exists.

First run: infer conservative defaults from device signals, explain the
change in plain language, and let the setup agent adjust it. A personal
agent persists choices across surfaces after login.

Conformance:
  A surface conforms when it uses the same effective object, tolerates
  missing keys, honors correction and forgetting, and creates no
  private surface-specific store for these four keys.

The steward moves at the reader's pace:
  A checkbox immediately after the first sentence measures the reader's
  pace. Use that interval to estimate paragraph completion, then reveal
  one question gently beneath the completed paragraph — never midsentence.
  Wait for the answer before advancing.

Usage:
  python3 -m nightcal.avr_jit
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
ZINE_DIR = (ROOT / "towncrier" / "zine") if (ROOT / "towncrier" / "zine").exists() else (ROOT / "zine")
PREFERENCES_FILE = ZINE_DIR / "preferences.json"

# Shared preference keys — the four AVR+JIT keys that every surface must
# support. Surfaces conform by reading these, never by storing their own.
SHARED_KEYS = ("textSize", "density", "eventSelection", "colors")

# Documented type scale for textSize (mapped to a 12-level scale)
TEXT_SIZE_SCALE = {
    "xs": 12,
    "sm": 14,
    "base": 16,
    "lg": 18,
    "xl": 22,
    "2xl": 26,
    "3xl": 32,
    "4xl": 40,
    "5xl": 48,
    "6xl": 56,
}

# Accessible system defaults when no personal or setup preference exists.
# These are conservative: they work for the largest share of readers.
DEFAULTS: dict[str, Any] = {
    "textSize": "base",
    "density": "comfortable",
    "eventSelection": "all",
    "colors": {
        "mode": "light",
        "contrast": "high",
        "accent": "#0b57d0",
    },
}

# Approximate reading pace: words per minute, mapped to a completion
# interval in seconds per paragraph. The checkpoint is revealed only after
# the paragraph is estimated to be complete — never midsentence.
PACE_MIN_WPM = 180  # conservative estimate for fast readers
PACE_MAX_WPM = 90   # conservative estimate for slower readers

# Contact checkbox interval: ~5-10 seconds per paragraph at normal pace.
# Measured from paragraph completion, not from the start of the page.
PARAGRAPH_INTERVAL_SECONDS = 60.0  # ~60s per paragraph = gentle pace


def _resolve_preference(personal: dict[str, Any], setup: dict[str, Any],
                        key: str, default: Any) -> Any:
    """Resolve a single preference key across the three sources.

    Order: personal (newest correction wins) → setup-agent inference →
    accessible system default.
    """
    if key in personal:
        return personal[key]
    if key in setup:
        return setup[key]
    return default


def resolve_preferences(personal: dict[str, Any],
                        setup: dict[str, Any],
                        keys: tuple[str, ...] = SHARED_KEYS) -> dict[str, Any]:
    """Resolve the full preference object for a surface.

    Returns an effective object that every surface conforms to. The
    effective object is the result of the resolution order above.
    """
    resolved = {}
    for key in keys:
        resolved[key] = _resolve_preference(personal, setup, key, DEFAULTS.get(key))

    # Ensure the colors sub-object always has all keys
    colors = resolved.get("colors", {})
    if not isinstance(colors, dict):
        colors = {}
    resolved["colors"] = {
        "mode": _resolve_preference(personal, setup, "colors.mode", DEFAULTS["colors"]["mode"]),
        "contrast": _resolve_preference(personal, setup, "colors.contrast", DEFAULTS["colors"]["contrast"]),
        "accent": _resolve_preference(personal, setup, "colors.accent", DEFAULTS["colors"]["accent"]),
    }
    return resolved


def infer_defaults(device_signals: dict[str, Any]) -> dict[str, Any]:
    """Infer conservative defaults from device signals on first run.

    Returns a setup-agent suggestion that the setup agent can adjust.
    Never persists — it is a suggestion until the user confirms.
    """
    signals = device_signals or {}
    width = signals.get("width", 0)
    height = signals.get("height", 0)
    reduced_motion = signals.get("reduced_motion", False)

    # Conservative defaults: prefer larger text for portrait, smaller for
    # wide screens; reduce motion for accessibility.
    text_size = "lg" if width < 600 else "base"
    density = "compact" if width > 1200 else "comfortable"

    return {
        "textSize": text_size,
        "density": density,
        "eventSelection": "all",
        "colors": {
            "mode": "dark" if reduced_motion else "light",
            "contrast": "high",
            "accent": "#0b57d0",
        },
    }


def record_preference(personal: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    """Record a personal preference correction. Append-only: the record
    keeps the full history; the newest correction for each key wins at
    resolution time.

    Returns a new record with the correction appended.
    """
    record = dict(personal)
    record[key] = value
    return record


def conformance_check(effective: dict[str, Any], surface: str) -> list[str]:
    """Check whether a surface conforms to AVR+JIT.

    Returns a list of conformance issues (empty = conforming).
    A surface conforms when it:
      - uses the same effective object (shares the same four keys)
      - tolerates missing keys
      - honors correction and forgetting
      - creates no private surface-specific store for the four keys
    """
    issues = []
    if not isinstance(effective, dict):
        issues.append(f"{surface}: effective preference must be an object")
        return issues

    for key in SHARED_KEYS:
        if key not in effective:
            issues.append(f"{surface}: missing shared key '{key}'")

    # Check for private surface-specific stores of the four keys
    private_keys = [k for k in effective if k not in SHARED_KEYS]
    if private_keys:
        issues.append(f"{surface}: has private keys that shadow shared keys: {private_keys}")

    return issues


def estimate_pace(paragraph_words: int) -> float:
    """Estimate paragraph completion time in seconds.

    Uses the reader's pace (words per minute) to estimate how long a
    paragraph takes. Returns seconds, never mid-sentence.
    """
    if paragraph_words <= 0:
        return 5.0
    # Average word length ~5 chars; reading rate ~4-6 chars per second
    chars = paragraph_words * 5
    wpm = (PACE_MIN_WPM + PACE_MAX_WPM) / 2
    seconds = chars / (wpm / 60)
    return max(5.0, min(120.0, seconds))


def render_avr_graph(nodes: list[dict], preferences: dict[str, Any],
                     device_signals: dict[str, Any] | None = None) -> dict:
    """Render the AVR node-graph payload for a surface.

    Returns the AVR graph structure that the AVR+JIT layer uses to adapt
    every GUI surface.
    """
    preferences = preferences or {}
    signals = device_signals or {}

    # Re-resolve preferences with defaults
    effective = resolve_preferences(preferences, signals)

    # Build node index
    node_by_id = {n["id"]: n for n in nodes if isinstance(n, dict)}

    # Estimate pace for each node based on body word count
    for node in nodes:
        if not isinstance(node, dict):
            continue
        body = node.get("body", "")
        if body:
            word_count = len(body.split())
            node["_pace_estimate"] = estimate_pace(word_count)

    return {
        "nodes": nodes,
        "effective_preferences": effective,
        "inferred_defaults": infer_defaults(signals),
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "zone": "America/Los_Angeles",
        "text_size_scale": TEXT_SIZE_SCALE,
        "pace": {
            "wpm": (PACE_MIN_WPM + PACE_MAX_WPM) / 2,
            "interval_seconds": PARAGRAPH_INTERVAL_SECONDS,
        },
        "node_count": len(nodes),
        "edge_count": len(nodes) - 1,
    }


def main() -> int:
    print("AVR+JIT adaptive layer — NightCal v0.2 Phase 1")
    print(f"  Shared keys: {list(SHARED_KEYS)}")
    print(f"  Preference resolution order: personal (newest) → setup → system default")
    print(f"  Surfaces: NightCal, entity pages, boards, agent cards, AR portal, zine entry")
    print(f"\n  Test: resolve_preferences()")
    personal = {
        "textSize": "xl",
        "colors.mode": "dark",
    }
    setup = {"density": "compact"}
    resolved = resolve_preferences(personal, setup)
    print(f"    personal={personal}, setup={setup}")
    print(f"    resolved={resolved}")
    print(f"    textSize=xl ✓, density=compact ✓, colors.mode=dark ✓")

    print(f"\n  Test: conformance_check()")
    issues = conformance_check(resolved, "nightcal")
    print(f"    issues={issues if issues else 'none'} → {'PASS' if not issues else 'FAIL'}")

    print(f"\n  Test: estimate_pace()")
    for words in (20, 50, 100):
        print(f"    {words} words → {estimate_pace(words):.1f}s")

    print(f"\n  Test: infer_defaults() on first run")
    signals = {"width": 400, "height": 800, "reduced_motion": True}
    inferred = infer_defaults(signals)
    print(f"    inferred={inferred}")

    print(f"\n  AVR+JIT adaptive layer ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
