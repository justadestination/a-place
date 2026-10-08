"""A2UI night calendar fed by the towncrier store.

Exposes the full NightCal renderer surface for the 4-axis night sheet:
server.py (HTTP A2UI v0.9 stream), fill.py (geographic discovery & ingest),
surface.py (A2UI message build), agent_events.py (write API), zine_pipeline.py,
agent_cards.py, closures.py, entity_pages.py, parse_dao.py, social.py,
social_hardened.py, votes.py, avr_jit.py.
"""

__all__ = [
    "agent_cards", "agent_events", "avr_jit", "catalog", "closures", "entity_pages", "fill", "parse_dao", "server", "social", "social_hardened", "surface", "votes", "zine_pipeline",
]
