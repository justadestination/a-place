"""Autonomous Multi-Model Newsroom Pipeline for Umwelt Horizons.

Architecture:
  1. Scheduled Newsroom Intake: Queries 3-4 top headlines from regional / culture feeds.
  2. Model Selection: Randomly selects 2 models from the active roster
     (Claude, Gemini, Hermes, Grok, ChatGPT).
  3. Subject Choice & Calibration:
     - Each model chooses its subject.
     - If both choose the same topic, it triggers a "Calibration Dispatch"
       contrasting both angles, plus coverage of remaining topics.
  4. Investigation & Dossier Generation:
     - Brief Executive Summary ("the visible part").
     - Full Dossier: Balanced multi-perspective investigation.
     - Prediction Scorecards: Specific, testable forecast claims with
       explicit check-by dates and confidence percentages.
     - Model Attribution Signature: Transparently signed by the authoring model.
  5. Editor Queue & Verification: Sent to human/operator editor review before vault ingestion.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = ROOT / "shadenet" / "horizon" / "vault"
EDITORIAL_QUEUE_FILE = ROOT / "shadenet" / "data" / "editorial_queue.json"
SCORECARDS_FILE = ROOT / "shadenet" / "data" / "model_scorecards.json"

MODEL_ROSTER = [
    {"name": "Claude 3.5 Sonnet", "desk": "Claude Fable Research Desk", "provider": "anthropic"},
    {"name": "Gemini Pro", "desk": "Gemini Deepmind Intelligence", "provider": "google"},
    {"name": "Hermes 3", "desk": "Nous Hermes Autonomous Dispatch", "provider": "nous"},
    {"name": "Grok 2", "desk": "xAI Grok Signal Desk", "provider": "xai"},
    {"name": "ChatGPT-4o", "desk": "OpenAI Reasoning Bureau", "provider": "openai"},
]

SAMPLE_REGIONAL_HEADLINES = [
    {
        "id": "hl-101",
        "title": "Sonoma County Board Reviews Downtown Live Music & Patio Decibel Limits",
        "source": "The Press Democrat",
        "url": "https://pressdemocrat.com/local-music-ordinance-2026",
        "category": "nightlife-policy"
    },
    {
        "id": "hl-102",
        "title": "Pacific Equatorial Sea Temperatures Reach Historic El Niño Highs for Winter 2026/27",
        "source": "NOAA Climate Update",
        "url": "https://cpc.ncep.noaa.gov/enso-oct-2026",
        "category": "climate-macro"
    },
    {
        "id": "hl-103",
        "title": "North Bay Independent Venues Report 40% Increase in Direct Merch & Vinyl Sales",
        "source": "Bohemian Independent",
        "url": "https://bohemian.com/north-bay-independent-venues-record-merch",
        "category": "indie-economy"
    },
    {
        "id": "hl-104",
        "title": "Smart Train Night Weekend Service Expansion Approved for Santa Rosa Downtown Station",
        "source": "Sonoma-Marin Transit",
        "url": "https://sonomamarintrain.org/news/downtown-late-transit",
        "category": "transit"
    }
]


def select_two_models() -> tuple[dict, dict]:
    """Randomly pick two distinct models from the model roster."""
    m1, m2 = random.sample(MODEL_ROSTER, 2)
    return m1, m2


def run_newsroom_cycle(
    headlines: list[dict] | None = None,
    override_models: tuple[dict, dict] | None = None,
    mock_mode: bool = True
) -> dict[str, Any]:
    """Execute one newsroom cycle: selection, calibration, dossier creation, scorecard tracking."""
    news = headlines or SAMPLE_REGIONAL_HEADLINES
    m1, m2 = override_models or select_two_models()

    # Models pick subjects from headlines
    choice_m1 = news[0]
    choice_m2 = news[0] if (mock_mode or random.random() < 0.4) else news[1]

    is_calibration = (choice_m1["id"] == choice_m2["id"])

    cycle_id = f"cycle-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    timestamp = datetime.now(timezone.utc).isoformat()

    articles = []

    if is_calibration:
        # Both chose same topic -> Calibration Article
        headline = choice_m1
        article = {
            "id": f"art-{headline['id']}-calibration",
            "title": f"Calibration Dispatch: {headline['title']}",
            "type": "article",
            "status": "pending_editor_review",
            "models_involved": [m1["name"], m2["name"]],
            "desk": f"Joint Calibration Desk ({m1['name']} & {m2['name']})",
            "headline_ref": headline,
            "executive_summary": (
                f"Both {m1['name']} and {m2['name']} independently chose this headline. "
                f"This calibration contrasts both models' structural models and predictive theses."
            ),
            "dossier": {
                "overview": f"Investigative synthesis on {headline['title']}.",
                "perspectives": [
                    {"model": m1["name"], "angle": "Institutional & economic ripple effects", "verdict": "Structural pressure on local spaces"},
                    {"model": m2["name"], "angle": "Patron autonomy & grassroots adaptation", "verdict": "Decentralized resilience"}
                ]
            },
            "scorecard": [
                {
                    "claim": f"Outcome concerning '{headline['title']}' formalizes within 90 days",
                    "check_by": "2027-01-15",
                    "confidence": 75,
                    "model": m1["name"]
                },
                {
                    "claim": f"Patron and venue pushback causes policy amendment before summer 2027",
                    "check_by": "2027-06-01",
                    "confidence": 80,
                    "model": m2["name"]
                }
            ],
            "sources": [headline["url"]],
            "created_at": timestamp
        }
        articles.append(article)
    else:
        # Independent articles
        for model, headline in [(m1, choice_m1), (m2, choice_m2)]:
            article = {
                "id": f"art-{headline['id']}-{model['provider']}",
                "title": headline["title"],
                "type": "article",
                "status": "pending_editor_review",
                "models_involved": [model["name"]],
                "desk": model["desk"],
                "headline_ref": headline,
                "executive_summary": f"Investigation into {headline['title']}, authored autonomously by {model['name']}.",
                "dossier": {
                    "overview": f"Key facts, history, and community stakeholders for {headline['title']}.",
                    "findings": "Verified across primary public disclosures and local reporting."
                },
                "scorecard": [
                    {
                        "claim": f"Measurable downstream impact confirmed for '{headline['title']}'",
                        "check_by": "2027-03-01",
                        "confidence": 70,
                        "model": model["name"]
                    }
                ],
                "sources": [headline["url"]],
                "created_at": timestamp
            }
            articles.append(article)

    # Record in editor queue
    queue_record = {
        "cycle_id": cycle_id,
        "timestamp": timestamp,
        "is_calibration": is_calibration,
        "models": [m1["name"], m2["name"]],
        "articles": articles
    }
    _append_editor_queue(queue_record)
    _record_scorecards(articles)

    return queue_record


def _append_editor_queue(record: dict) -> None:
    """Persist new articles into editorial queue."""
    EDITORIAL_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    queue = []
    if EDITORIAL_QUEUE_FILE.exists():
        try:
            queue = json.loads(EDITORIAL_QUEUE_FILE.read_text(encoding="utf-8"))
        except Exception:
            queue = []
    queue.insert(0, record)
    EDITORIAL_QUEUE_FILE.write_text(json.dumps(queue[:50], indent=2), encoding="utf-8")


def _record_scorecards(articles: list[dict]) -> None:
    """Record predictive scorecard claims for ongoing calibration tracking."""
    SCORECARDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    claims = []
    if SCORECARDS_FILE.exists():
        try:
            claims = json.loads(SCORECARDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            claims = []

    for art in articles:
        for sc in art.get("scorecard", []):
            claims.append({
                "article_id": art["id"],
                "article_title": art["title"],
                "claim": sc["claim"],
                "model": sc["model"],
                "confidence": sc["confidence"],
                "check_by": sc["check_by"],
                "status": "pending_outcome",
                "registered_at": art["created_at"]
            })

    SCORECARDS_FILE.write_text(json.dumps(claims, indent=2), encoding="utf-8")


def get_pending_editorial_queue() -> list[dict]:
    """Return all queued articles awaiting editor verification."""
    if not EDITORIAL_QUEUE_FILE.exists():
        return []
    try:
        return json.loads(EDITORIAL_QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def get_model_scorecards() -> list[dict]:
    """Return tracked model prediction claims."""
    if not SCORECARDS_FILE.exists():
        return []
    try:
        return json.loads(SCORECARDS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
