"""Agent cards as public pages — NightCal v0.2 Phase 1.

Agent cards as public pages [Spec §2 p.4]: every agent's card is a public
profile page. The Myspace concept — every agent has a browsable page that
lists its identity, address, roles, and cited public info.

This module renders a public HTML card for each agent in the scaffold:
- personal_agent
- venue_agent
- board_agent
- subscription_manager

Each card shows the agent's identity (address, agent_id), its role, the
commands it can handle (from the registry), and any cited public refs.
The visual design is NOT baked in — this module emits the data layer:
semantic HTML with data attributes for the A2UI renderer.

Usage:
  python3 -m agent_cards        # render all agent cards
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

# Map scaffold agent files to card data
AGENTS = {
    "personal_agent": {
        "name": "Personal Agent",
        "summary": "A2A personal agent with login. Grants submit + receive scopes. Posts to boards, subscribes to events.",
        "file": "personal_agent.py",
        "address": "a2a://agent/personal_agent_01",
        "role": "personal_user",
        "description": "The user's personal agent. Submits board posts and subscribes to event updates.",
        "commands": ["board.post", "event.subscribe", "event.unsubscribe", "prefs.set", "prefs.get"],
        "refs": ["Personal agent login §2 p.4"],
    },
    "venue_agent": {
        "name": "Venue Agent",
        "summary": "Thin A2A client for venues. Polls its outbox and files event.create / event.update / event.cancel through the engine.",
        "file": "venue_agent.py",
        "address": "a2a://agent/venue_agent_01",
        "role": "venue",
        "description": "A venue's agent. Files shows and manages the event lifecycle through the command engine.",
        "commands": ["event.create", "event.update", "event.cancel"],
        "refs": ["Hosted venue agent §6 pp.8–9"],
    },
    "board_agent": {
        "name": "Public Board Agent",
        "summary": "Public board v1. Posts go through Gatekeeper triage, then render to the public board.",
        "file": "public_board.py",
        "address": "a2a://agent/board_agent",
        "role": "public_board",
        "description": "Public posting surface. Triages incoming posts and renders the board.",
        "commands": ["board.post"],
        "refs": ["Public board v1 §8 p.12"],
    },
    "subscriptions": {
        "name": "Subscription Manager",
        "summary": "Manages event/venue/filter subscriptions and publishes updates to subscriber outboxes.",
        "file": "subscriptions.py",
        "address": "a2a://agent/subscriptions",
        "role": "subscription_manager",
        "description": "Registers interest in events and delivers updates to subscribers.",
        "commands": ["event.subscribe", "event.unsubscribe"],
        "refs": ["Subscriptions v1 §8 p.12"],
    },
}

# A public agent card is a real HTML file with the agent's identity and
# cited public info. The page is the data layer: the visual design is the
# frontend team's job.
# This module emits semantic HTML with data attributes for A2UI binding.

PAGE_TPL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="index, follow">
  <title>{name} — {address}</title>
  <script type="application/ld+json">
  {jsonld}
  </script>
  <style>
  .agent-card {{ font-family: system-ui, -apple-system, sans-serif; max-width: 72ch; margin: 0 auto; }}
  .agent-header {{ padding: 1.5rem 0 1rem; border-bottom: 1px solid #e0e0e0; }}
  .agent-name {{ font-size: 1.4rem; line-height: 1.2; }}
  .agent-address {{ font-size: 0.85rem; color: #666; }}
  .agent-role {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #666; }}
  .agent-summary {{ padding: 1rem 0; font-size: 0.95rem; line-height: 1.5; }}
  .agent-commands {{ padding: 1rem 0; }}
  .agent-commands h3 {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #666; margin: 0 0 0.5rem; }}
  .agent-commands ul {{ list-style: none; margin: 0; padding: 0; }}
  .agent-commands li {{ font-size: 0.85rem; margin: 0.2rem 0; }}
  .agent-refs {{ padding: 1rem 0; }}
  .agent-refs h3 {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #666; margin: 0 0 0.5rem; }}
  .agent-refs ul {{ list-style: none; margin: 0; padding: 0; }}
  .agent-refs li {{ font-size: 0.8rem; color: #666; margin: 0.15rem 0; }}
  .agent-footer {{ margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; font-size: 0.7rem; color: #999; }}
  @media (prefers-reduced-motion: reduce) {{ .agent-card * {{ transition: none !important; }} }}
  </style>
</head>
<body>
  <main class="agent-card" data-agent-type="{role}">
    <header class="agent-header">
      <h1 class="agent-name" data-field="name">{name}</h1>
      <p class="agent-address" data-field="address">{address}</p>
      <p class="agent-role" data-field="role">{role}</p>
    </header>
    <section class="agent-summary" data-field="summary">
      <p>{summary}</p>
    </section>
    <section class="agent-commands" data-field="commands">
      <h3>Commands</h3>
      <ul>
        {commands_html}
      </ul>
    </section>
    <section class="agent-refs" data-field="refs">
      <h3>References</h3>
      <ul>
        {refs_html}
      </ul>
    </section>
    <footer class="agent-footer">
      Agent card generated from {file}. Citation source: NightCal agent ecosystem contract v0.2.
    </footer>
  </main>
</body>
</html>
"""


def _commands_html(commands: list[str]) -> str:
    return "".join(f'<li>{cmd}</li>' for cmd in commands)


def _refs_html(refs: list[str]) -> str:
    return "".join(f'<li>{ref}</li>' for ref in refs)


def _jsonld(agent: dict) -> str:
    """JSON-LD for the agent card — machine-readable identity."""
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": agent["name"],
        "url": f"https://nightcal.example.org/agents/{agent['address'].replace('a2a://agent/', '')}",
        "description": agent["summary"],
    }, ensure_ascii=False)


def _render_html(agent: dict) -> str:
    """Assemble the agent card HTML. Presentation classes only."""
    return PAGE_TPL.format(
        name=agent["name"],
        address=agent["address"],
        role=agent["role"],
        summary=agent["summary"],
        file=agent["file"],
        commands_html=_commands_html(agent.get("commands", [])),
        refs_html=_refs_html(agent.get("refs", [])),
        jsonld=_jsonld(agent),
    )


def render_agent_card(agent: dict, output_path: Path) -> None:
    """Write a public agent card page."""
    output_path.write_text(_render_html(agent), encoding="utf-8")


def render_all_agent_cards(output_dir: Path) -> dict[str, int]:
    """Render a public card for every scaffold agent."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {"rendered": 0, "skipped": 0, "errors": []}

    for key, agent in AGENTS.items():
        try:
            out = output_dir / f"{key}.html"
            render_agent_card(agent, out)
            results["rendered"] += 1
        except Exception as exc:
            results["errors"].append(f"{key}: {exc}")

    return results


# --- Test harness ---

def run_tests(tmpdir: Path) -> bool:
    """Render a known agent card and verify the output."""
    agent = AGENTS["personal_agent"]
    out = tmpdir / "personal_agent.html"
    render_agent_card(agent, out)

    html = out.read_text(encoding="utf-8")
    ok = True

    for needle in ["Personal Agent", "a2a://agent/personal_agent_01",
                   "submit + receive scopes", "event.subscribe", "board.post",
                   "personal_agent.py"]:
        if needle not in html:
            ok = False
            print(f"  FAIL: {needle!r} not in page")

    if 'data-agent-type="personal_user"' not in html:
        ok = False
        print("  FAIL: data-agent-type attribute missing")

    if '<script type="application/ld+json">' not in html:
        ok = False
        print("  FAIL: JSON-LD missing")

    print(f"  {'PASS' if ok else 'FAIL'}: agent card contains identity")
    return ok


def main() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="nightcal-agents-"))

    # 1. Unit test with a known agent
    ok = run_tests(tmp)

    # 2. Real render over all scaffold agents
    print("\n══ Rendering agent cards ══")
    results = render_all_agent_cards(tmp / "agents")
    print(f"  Rendered: {results['rendered']}, skipped: {results['skipped']}")
    if results["errors"]:
        print(f"  Errors: {results['errors']}")

    # 3. Verification
    ok2 = True
    for f in sorted((tmp / "agents").glob("*.html")):
        html = f.read_text(encoding="utf-8")
        if "<h1" not in html or "data-agent-type" not in html:
            ok2 = False
            print(f"  FAIL: {f.name} missing header")
    print(f"  Cards verified: {ok2}")

    print(f"\n  Sample cards written to {tmp / 'agents'}")
    for f in sorted((tmp / "agents").glob("*.html")):
        print(f"    - {f.name}")

    return 0 if (ok and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())