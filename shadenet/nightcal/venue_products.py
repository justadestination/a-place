"""Venue merchandise, product catalogue, and storefront integration models."""

from __future__ import annotations

from typing import Any

DEFAULT_VENUE_MERCH: dict[str, list[dict[str, Any]]] = {
    "ven_arlene_francis": [
        {
            "id": "merch_afc_tee",
            "name": "Arlene Francis Center Community Screenprint Tee",
            "price": "$25",
            "type": "merch",
            "in_stock": True,
            "buy_url": "https://arlenefranciscenter.org/store/tee"
        },
        {
            "id": "merch_afc_poster",
            "name": "Live at the Center Screenprinted Poster (Limited)",
            "price": "$15",
            "type": "poster",
            "in_stock": True,
            "buy_url": "https://arlenefranciscenter.org/store/poster"
        }
    ],
    "ven_vintage_space": [
        {
            "id": "merch_vs_coin",
            "name": "Vintage Space Drink Token Coin (Brass)",
            "price": "$12",
            "type": "token",
            "in_stock": True,
            "buy_url": "https://vintagespace.com/tokens"
        },
        {
            "id": "merch_vs_vinyl",
            "name": "Space Lounge Sessions Vol. 1 (Vinyl 12\")",
            "price": "$30",
            "type": "vinyl",
            "in_stock": True,
            "buy_url": "https://vintagespace.com/vinyl"
        }
    ],
    "ven_shady_oak": [
        {
            "id": "merch_so_glass",
            "name": "Shady Oak Barrel House Belgian Tulip Glass",
            "price": "$14",
            "type": "merch",
            "in_stock": True,
            "buy_url": "https://shadyoakbarrelhouse.com/shop"
        }
    ]
}


def get_venue_merch(venue_id: str) -> list[dict[str, Any]]:
    """Return catalogued merchandise items for a given venue."""
    return DEFAULT_VENUE_MERCH.get(venue_id, [])


def enrich_venue_with_products(venue_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach product catalogue to venue record."""
    vid = venue_dict.get("id", "")
    items = get_venue_merch(vid)
    venue_dict["merch_items"] = items
    venue_dict["has_shop"] = len(items) > 0
    return venue_dict
