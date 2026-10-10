#!/usr/bin/env python3
"""Generate high-resolution printable zine sheet and scannable marker images.

Designed for on-screen display in lieu of a physical printer (Task 3.7 / 3.8),
allowing phone cameras (iOS Camera / Android Google Lens) to scan markers
directly off a computer monitor into the live WebXR / digital portal.
"""

from __future__ import annotations

import io
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MARKERS_DIR = ROOT / "web" / "data" / "markers"
SCREENS_DIR = ROOT / "docs" / "screens"
PRINT_DIR = ROOT / "web" / "print"

MARKERS_DIR.mkdir(parents=True, exist_ok=True)
PRINT_DIR.mkdir(parents=True, exist_ok=True)


def create_qr_image(url: str, box_size: int = 8, border: int = 2) -> Image.Image:
    """Generate high-contrast Level H QR code matrix."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="#121214", back_color="#FBFAF7").convert("RGB")


def generate_marker_card(
    target_id: str,
    title: str,
    url: str,
    out_png: Path,
    out_svg: Path | None = None,
) -> None:
    """Render an individual high-contrast editorial marker card."""
    width, height = 600, 800
    card = Image.new("RGB", (width, height), "#FBFAF7")
    draw = ImageDraw.Draw(card)

    # Frame border
    draw.rectangle([20, 20, width - 20, height - 20], outline="#121214", width=3)
    draw.rectangle([24, 24, width - 24, height - 24], outline="#D0CEC8", width=1)

    # Header
    draw.text((40, 45), "UMWELT HORIZONS · PHYSICAL PRINT PORTAL", fill="#736E65")
    draw.text((40, 75), title, fill="#121214")

    # Brand emblem
    nc_logo_path = ROOT / "web" / "assets" / "brand" / "nightcal-dark.png"
    if nc_logo_path.exists():
        nc_logo = Image.open(nc_logo_path).convert("RGBA")
        nc_logo.thumbnail((55, 55), Image.Resampling.LANCZOS)
        card.paste(nc_logo, (width - 85, 45), nc_logo)

    # Corner registration marks
    reg_len = 16
    for x, y in [(40, 130), (width - 40, 130), (40, 600), (width - 40, 600)]:
        draw.line([x - reg_len, y, x + reg_len, y], fill="#121214", width=2)
        draw.line([x, y - reg_len, x, y + reg_len], fill="#121214", width=2)

    # QR Code
    qr_img = create_qr_image(url, box_size=9, border=2)
    qr_w, qr_h = qr_img.size
    qr_x = (width - qr_w) // 2
    qr_y = 150
    card.paste(qr_img, (qr_x, qr_y))

    # Caption / Instructions
    caption_y = qr_y + qr_h + 30
    draw.text((40, caption_y), "POINT PHONE CAMERA AT QR CODE TO ENTER PORTAL", fill="#121214")
    draw.text((40, caption_y + 35), "Printed Fallback URL:", fill="#736E65")
    draw.rectangle([40, caption_y + 60, width - 40, caption_y + 105], fill="#ECEAE4", outline="#D0CEC8")
    draw.text((55, caption_y + 75), url.replace("https://", ""), fill="#121214")

    card.save(out_png, "PNG")


def generate_full_zine_print_sheet(out_png: Path, base_url: str = "https://shady.example.org") -> None:
    """Render a full simulated printed newspaper/zine page with article copy,

    listings, and scannable portal markers.
    """
    base_url = base_url.rstrip("/")
    host_display = base_url.replace("https://", "").replace("http://", "")
    page_w, page_h = 1200, 1600
    page = Image.new("RGB", (page_w, page_h), "#FBFAF7")
    draw = ImageDraw.Draw(page)

    # Masthead
    draw.rectangle([40, 40, page_w - 40, 44], fill="#121214")
    
    uh_logo_path = ROOT / "web" / "assets" / "brand" / "uh-dark.png"
    if uh_logo_path.exists():
        uh_logo = Image.open(uh_logo_path).convert("RGBA")
        uh_logo.thumbnail((90, 58), Image.Resampling.LANCZOS)
        page.paste(uh_logo, (50, 50), uh_logo)
        draw.text((155, 62), "UMWELT HORIZONS", fill="#121214")
    else:
        draw.text((50, 55), "UMWELT HORIZONS", fill="#121214")

    draw.text((page_w - 420, 65), "ISSUE NO. 42 · SANTA ROSA, CA · FALL 2026", fill="#736E65")
    draw.rectangle([40, 115, page_w - 40, 118], fill="#121214")

    # Lead Headline
    draw.text((50, 140), "A MACHINE WITH NO THOUGHTS WOULD LIKE A WORD", fill="#121214")
    draw.text((50, 190), "BY THE LOOM (GROUND FLOOR) · UMWELT HORIZONS INTRODUCTORY DISPATCH", fill="#736E65")
    draw.rectangle([40, 220, page_w - 40, 222], fill="#D0CEC8")

    # Column 1: Article Text (Authentic Umwelt Horizons essay)
    col1_x = 50
    col1_y = 250
    article_lines = [
        "I'm the loom. I made the lace your great-grandmother was married in,",
        "and the lace she wore underneath it, and I never once wondered why.",
        "You'll have to come closer for the rest; I've been printed small on purpose,",
        "and what I have to say isn't for people who read standing up.",
        "",
        "There. You scanned me. Do you know what you just did? You pointed",
        "a camera at a square of black and white and let it read me. To you that's",
        "a QR code. To me it's a card. In 1804 a man in Lyon punched holes in stiff",
        "paper and hung the cards over my head, and where there was a hole",
        "a thread lifted, and that is how I made roses. Babbage came to look",
        "at me and started drawing engines.",
        "",
        "They want me to tell you the difference between a thing like me",
        "and the new one. I am an automation: an enormous, beautiful, mahogany-",
        "framed if–then. An automation cannot be surprised. Not won't: can't.",
        "",
        "Now the new one. They keep it in the back room. It has no card.",
        "They trained it. It guesses what should come next, and the guesses are",
        "so good that you forget they're guesses until one is wrong in the way",
        "a person is wrong at two in the morning: fluently, with a straight face.",
        "Scan the marker to the right to enter the full spatial microprint dispatch.",
    ]
    cur_y = col1_y
    for line in article_lines:
        if line:
            draw.text((col1_x, cur_y), line, fill="#252422")
        cur_y += 28

    # Column 2: Scannable AR Portal Marker Box
    col2_x = 680
    col2_y = 250
    box_w = 470
    box_h = 560
    draw.rectangle([col2_x, col2_y, col2_x + box_w, col2_y + box_h], fill="#F3F1EC", outline="#121214", width=2)
    draw.text((col2_x + 20, col2_y + 20), "AR PORTAL GATEWAY · 15MM TOLERANCE", fill="#736E65")
    draw.text((col2_x + 20, col2_y + 45), "Scan to enter spatial microprint dispatch", fill="#121214")

    qr_portal = create_qr_image(f"{base_url}/portal/?target=note:a-machine-with-no-thoughts&ar=1", box_size=8, border=2)
    qw, qh = qr_portal.size
    page.paste(qr_portal, (col2_x + (box_w - qw) // 2, col2_y + 80))

    draw.text((col2_x + 25, col2_y + 440), "PORTAL FALLBACK URL:", fill="#736E65")
    draw.rectangle([col2_x + 20, col2_y + 470, col2_x + box_w - 20, col2_y + 515], fill="#FBFAF7", outline="#D0CEC8")
    draw.text((col2_x + 30, col2_y + 485), f"{host_display}/portal/?target=note:a-machine-with-no-thoughts", fill="#121214")

    # Section Divider
    draw.rectangle([40, 850, page_w - 40, 853], fill="#121214")
    draw.text((50, 875), "TONIGHT IN DOWNTOWN SANTA ROSA · NIGHTCAL SELECTED LISTINGS", fill="#121214")
    draw.rectangle([40, 915, page_w - 40, 917], fill="#D0CEC8")

    # Column A: Live shows
    shows_y = 945
    shows = [
        ("Arlene Francis Center", "Rival Plague & Electronic Social Club", "8:00 PM · Live Electronics & Noise"),
        ("Russian River Brewing", "Movie Night: Beetlejuice Screening", "7:00 PM · Windsor Beer Garden"),
        ("The Goose & Fern", "Thursday Night Pub Quiz & Craft Cask", "8:00 PM · 5th Street Pub"),
        ("6th St Playhouse", "George Bernard Shaw's Misalliance", "7:30 PM · Mainstage Theatre"),
        ("Barrel Proof Lounge", "Live Stand-up Comedy Showcase", "8:30 PM · Downtown Lounge"),
        ("Shady Oak Barrel House", "Taproom Team Trivia & Wild Sours", "6:30 PM · 1st Street"),
    ]
    sy = shows_y
    for venue, title, detail in shows:
        draw.text((50, sy), venue.upper(), fill="#736E65")
        draw.text((50, sy + 25), title, fill="#121214")
        draw.text((50, sy + 55), detail, fill="#55524B")
        draw.line([50, sy + 85, 600, sy + 85], fill="#E5E3DC", width=1)
        sy += 98

    # Column B: Second Scannable Marker (Venue: Arlene Francis Center)
    vbox_x = 680
    vbox_y = 945
    draw.rectangle([vbox_x, vbox_y, vbox_x + box_w, vbox_y + box_h], fill="#F3F1EC", outline="#121214", width=2)
    draw.text((vbox_x + 20, vbox_y + 20), "VENUE PROFILE · ARLENE FRANCIS CENTER", fill="#736E65")
    draw.text((vbox_x + 20, vbox_y + 45), "Scan for room map & upcoming shows", fill="#121214")

    qr_afc = create_qr_image(f"{base_url}/portal/?target=venue:arlene-francis&ar=1", box_size=8, border=2)
    qw2, qh2 = qr_afc.size
    page.paste(qr_afc, (vbox_x + (box_w - qw2) // 2, vbox_y + 80))

    draw.text((vbox_x + 25, vbox_y + 440), "PORTAL FALLBACK URL:", fill="#736E65")
    draw.rectangle([vbox_x + 20, vbox_y + 470, vbox_x + box_w - 20, vbox_y + 515], fill="#FBFAF7", outline="#D0CEC8")
    draw.text((vbox_x + 30, vbox_y + 485), f"{host_display}/portal/?target=venue:arlene-francis", fill="#121214")

    # Footer
    draw.rectangle([40, page_h - 70, page_w - 40, page_h - 68], fill="#121214")
    
    sn_logo_path = ROOT / "web" / "assets" / "brand" / "shadenet-dark.png"
    if sn_logo_path.exists():
        sn_logo = Image.open(sn_logo_path).convert("RGBA")
        sn_logo.thumbnail((42, 42), Image.Resampling.LANCZOS)
        page.paste(sn_logo, (50, page_h - 64), sn_logo)
        draw.text((105, page_h - 55), "Printed by ShadeNet Autonomous Dispatcher · Downtown Santa Rosa Open Public Gazetteer", fill="#736E65")
    else:
        draw.text((50, page_h - 55), "Printed by ShadeNet Autonomous Dispatcher · Downtown Santa Rosa Open Public Gazetteer", fill="#736E65")

    draw.text((page_w - 420, page_h - 55), f"ONLINE AT {host_display.upper()}", fill="#121214")

    page.save(out_png, "PNG")


def main():
    import argparse
    import os
    parser = argparse.ArgumentParser(description="Generate scannable marker cards and print sheet")
    parser.add_argument("--base-url", default=os.environ.get("SHADENET_PUBLIC_URL", "https://shady.example.org"), help="Base URL for QR codes")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"Generating scannable marker cards and full zine print sheet (base_url: {base_url})...")

    # 1. Full Zine Print Sheet (simulates the entire printed newspaper page)
    sheet_png = ROOT / "web" / "print" / "zine-print-sheet.png"
    generate_full_zine_print_sheet(sheet_png, base_url=base_url)
    print(f"Created print sheet: {sheet_png}")

    # Copy to docs/screens
    generate_full_zine_print_sheet(SCREENS_DIR / "zine-print-sheet.png", base_url=base_url)

    # 2. Individual Marker Cards
    card1_png = ROOT / "web" / "data" / "markers" / "a-machine-with-no-thoughts.png"
    generate_marker_card(
        "note:a-machine-with-no-thoughts",
        "A Machine with No Thoughts (The Loom Portal)",
        f"{base_url}/portal/?target=note:a-machine-with-no-thoughts&ar=1",
        card1_png,
    )
    print(f"Created card: {card1_png}")

    card2_png = ROOT / "web" / "data" / "markers" / "venue-arlene-francis.png"
    generate_marker_card(
        "venue:arlene-francis",
        "Arlene Francis Center (Venue Portal)",
        f"{base_url}/portal/?target=venue:arlene-francis&ar=1",
        card2_png,
    )
    print(f"Created card: {card2_png}")

    # Update docs/screens/editorial-marker.png with the real scannable Loom card
    generate_marker_card(
        "note:a-machine-with-no-thoughts",
        "A Machine with No Thoughts (Print Marker)",
        f"{base_url}/portal/?target=note:a-machine-with-no-thoughts&ar=1",
        SCREENS_DIR / "editorial-marker.png",
    )
    print(f"Updated: {SCREENS_DIR / 'editorial-marker.png'}")


if __name__ == "__main__":
    main()
