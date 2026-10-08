"""Umwelt Horizon zine compiler & vault (shadenet.horizon).

Supports syndicated partner news (Spec §E):
- type: syndicated in frontmatter
- partner_name / original_url / author / license fields
- "Independent Partner Syndication" badge + canonical link
"""

__all__ = [
    "compile_zine", "render_avr", "zine_pipeline",  # compiled from shadenet.horizon.zine_pipeline
    "VAULT_DIR", "NODES_FILE", "EDGES_FILE", "AVR_FILE", "AVR_GRAPH",  # dir defines the data
]
