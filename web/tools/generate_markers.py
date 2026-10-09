#!/usr/bin/env python3
"""Editorial Marker Generator — NightCal Zine (Task 3.8).

Generates high-contrast visual markers with embedded QR matrix data and
printed fallback URLs down to 15mm print size under low light.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import qrcode
import qrcode.image.svg

WEB = Path(__file__).resolve().parent.parent
ROOT = WEB.parent
VAULT = ROOT / "shadenet" / "horizon" / "vault"
MARKERS_DIR = WEB / "data" / "markers"
DEFAULT_ORIGIN = "https://shady.example.org"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "marker"


def generate_marker_svg(target_id: str, origin: str = DEFAULT_ORIGIN) -> tuple[str, str, str]:
    """Generate SVG marker and return (svg_content, destination_url, fallback_caption)."""
    dest_url = f"{origin.rstrip('/')}/portal/?target={target_id}"
    fallback_caption = f"shady.example.org/portal/?target={target_id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% error recovery for print/ink bleed
        box_size=10,
        border=4,  # Standard 4-module quiet zone
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(dest_url)
    qr.make(fit=True)

    img = qr.make_image()
    raw_svg = img.to_string().decode("utf-8")

    # Extract inner path from raw SVG
    path_match = re.search(r'<path[^>]*d="([^"]+)"[^>]*>', raw_svg)
    path_d = path_match.group(1) if path_match else ""

    # Dimensions
    viewbox = re.search(r'viewBox="([^"]+)"', raw_svg)
    vb = viewbox.group(1) if viewbox else "0 0 330 330"
    parts = vb.split()
    w = int(parts[2]) if len(parts) >= 3 else 330
    h = int(parts[3]) if len(parts) >= 4 else 330

    total_h = h + 40  # Extra space below for editorial fallback caption

    # Compose stylized editorial SVG with plain-URL caption
    editorial_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {total_h}" width="{w}" height="{total_h}" class="nc-editorial-marker" role="img" aria-label="Visual print marker for {html.escape(target_id)}">
  <rect width="{w}" height="{total_h}" fill="#FBFAF7" rx="8" />
  <path d="{path_d}" fill="#121214" />
  <text x="{w // 2}" y="{h + 24}" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600" fill="#3E3B35" text-anchor="middle" letter-spacing="0.02em">{html.escape(fallback_caption)}</text>
</svg>"""

    return editorial_svg, dest_url, fallback_caption


def build_all_markers(vault_dir: Path | None = None, out_dir: Path | None = None) -> list[dict]:
    v_dir = vault_dir or VAULT
    o_dir = out_dir or MARKERS_DIR
    o_dir.mkdir(parents=True, exist_ok=True)

    records = []

    # 1. Notes from vault
    if v_dir.exists():
        for md in sorted(v_dir.glob("*.md")):
            node_id = f"note:{md.stem}"
            svg_content, url, caption = generate_marker_svg(node_id)
            out_file = o_dir / f"{md.stem}.svg"
            out_file.write_text(svg_content, encoding="utf-8")
            records.append({
                "target": node_id,
                "file": f"/data/markers/{out_file.name}",
                "destination_url": url,
                "fallback_caption": caption,
            })

    # 2. Key sample entities
    sample_entities = ["venue:royal", "venue:arlene-francis", "event:evt_456"]
    for eid in sample_entities:
        slug = slugify(eid)
        svg_content, url, caption = generate_marker_svg(eid)
        out_file = o_dir / f"{slug}.svg"
        out_file.write_text(svg_content, encoding="utf-8")
        records.append({
            "target": eid,
            "file": f"/data/markers/{out_file.name}",
            "destination_url": url,
            "fallback_caption": caption,
        })

    manifest = o_dir / "index.json"
    manifest.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Generated {len(records)} editorial markers in {o_dir}")
    return records


def main():
    parser = argparse.ArgumentParser(description="Zine Editorial Marker Generator")
    parser.add_argument("--target", help="Single target ID (e.g. note:the-room-after-midnight)")
    parser.add_argument("--all", action="store_true", help="Generate markers for all vault notes")
    parser.add_argument("--out-dir", type=Path, default=MARKERS_DIR, help="Output directory")

    args = parser.parse_args()

    if args.target:
        slug = slugify(args.target)
        svg, url, caption = generate_marker_svg(args.target)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        out_path = args.out_dir / f"{slug}.svg"
        out_path.write_text(svg, encoding="utf-8")
        print(f"Marker generated: {out_path}")
        print(f"  URL: {url}")
        print(f"  Fallback: {caption}")
    else:
        build_all_markers(out_dir=args.out_dir)


if __name__ == "__main__":
    main()
