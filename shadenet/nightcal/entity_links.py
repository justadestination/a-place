"""Bidirectional links between events, entities, and zine articles (Task 2.13).

An event matches an entity when its entityIds list contains the entity id,
or a performer has that id, or a performer name equals the entity name.
An article matches when it lists the entity id, or its title or body contains
the entity name as a whole word.
"""

from __future__ import annotations

from typing import Any


def _name(performer: Any) -> str:
    if isinstance(performer, str):
        return performer.strip()
    if isinstance(performer, dict):
        return str(performer.get("name") or "").strip()
    return ""


def _pid(performer: Any) -> str:
    if isinstance(performer, dict):
        return str(performer.get("id") or "").strip()
    return ""


def _contains_name(blob: str, name: str) -> bool:
    hay = blob.casefold()
    needle = name.casefold()
    if not needle:
        return False
    start = 0
    while True:
        found = hay.find(needle, start)
        if found < 0:
            return False
        before_ok = found == 0 or not hay[found - 1].isalnum()
        after = found + len(needle)
        after_ok = after >= len(hay) or not hay[after].isalnum()
        if before_ok and after_ok:
            return True
        start = found + 1


def event_matches_entity(event: dict[str, Any], entity: dict[str, Any]) -> bool:
    entity_id = str(entity.get("id") or "")
    entity_name = str(entity.get("name") or "")
    if entity_id and entity_id in (event.get("entityIds") or []):
        return True
    for performer in event.get("performers") or []:
        if entity_id and _pid(performer) == entity_id:
            return True
        if entity_name and _name(performer).casefold() == entity_name.casefold():
            return True
    return False


def entities_for_event(event: dict[str, Any], entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entity for entity in entities if event_matches_entity(event, entity)]


def events_for_entity(entity: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event_matches_entity(event, entity)]


def article_matches_entity(article: dict[str, Any], entity: dict[str, Any]) -> bool:
    entity_id = str(entity.get("id") or "")
    listed = list(article.get("entityIds") or []) + list(article.get("entities") or [])
    if entity_id and entity_id in listed:
        return True
    blob = " ".join(str(article.get(key) or "") for key in ("title", "body", "summary", "text", "html"))
    return _contains_name(blob, str(entity.get("name") or ""))


def articles_for_entity(entity: dict[str, Any], articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [article for article in articles if article_matches_entity(article, entity)]
