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


def generate_full_zine_print_sheet(out_png: Path) -> None:
    """Render a full simulated printed newspaper/zine page with article copy,

    listings, and scannable portal markers.
    """
    page_w, page_h = 1200, 1600
    page = Image.new("RGB", (page_w, page_h), "#FBFAF7")
    draw = ImageDraw.Draw(page)

    # Masthead
    draw.rectangle([40, 40, page_w - 40, 44], fill="#121214")
    draw.text((50, 55), "UMWELT HORIZONS", fill="#121214")
    draw.text((page_w - 420, 65), "ISSUE NO. 42 · SANTA ROSA, CA · FALL 2026", fill="#736E65")
    draw.rectangle([40, 115, page_w - 40, 118], fill="#121214")

    # Lead Headline
    draw.text((50, 140), "THE ROOM AFTER MIDNIGHT: A DISPATCH FROM 4TH STREET", fill="#121214")
    draw.text((50, 190), "BY DOWNTOWN EDITORIAL DESK · CITATIONS VERIFIED ON SHADENET", fill="#736E65")
    draw.rectangle([40, 220, page_w - 40, 222], fill="#D0CEC8")

    # Column 1: Article Text
    col1_x = 50
    col1_y = 250
    article_lines = [
        "A review of the new late-night venue emerging in downtown",
        "Metropolis. The room has never been this full.",
        "",
        "Behind the brick walls on 4th Street, sound spill rules have",
        "pushed acoustic sets indoors while the open-air beer gardens",
        "adapt to the 10:00 PM acoustic threshold.",
        "",
        "\"The room breathes when the street goes quiet,\" noted a local",
        "drummer following Friday's impromptu session at Arlene Francis",
        "Center. \"You can hear the whole room move together.\"",
        "",
        "Every listing on this sheet is cryptographically anchored to",
        "NightCal's public ledger. Scanning the portal marker to the right",
        "reveals live attendance gauges, spatial letter threads, and",
        "real-time setlist updates directly in WebXR AR.",
        "",
        "Whether you read this page on newsprint or directly off a glass",
        "screen, the camera portal links this ink to the live room.",
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
    draw.text((col2_x + 20, col2_y + 45), "Scan to enter spatial dispatch", fill="#121214")

    qr_portal = create_qr_image("https://shady.example.org/portal/?target=note:the-room-after-midnight&ar=1", box_size=8, border=2)
    qw, qh = qr_portal.size
    page.paste(qr_portal, (col2_x + (box_w - qw) // 2, col2_y + 80))

    draw.text((col2_x + 25, col2_y + 440), "PORTAL FALLBACK URL:", fill="#736E65")
    draw.rectangle([col2_x + 20, col2_y + 470, col2_x + box_w - 20, col2_y + 515], fill="#FBFAF7", outline="#D0CEC8")
    draw.text((col2_x + 30, col2_y + 485), "shady.example.org/portal/?target=note:the-room-after-midnight", fill="#121214")

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

    qr_afc = create_qr_image("https://shady.example.org/portal/?target=venue:arlene-francis&ar=1", box_size=8, border=2)
    qw2, qh2 = qr_afc.size
    page.paste(qr_afc, (vbox_x + (box_w - qw2) // 2, vbox_y + 80))

    draw.text((vbox_x + 25, vbox_y + 440), "PORTAL FALLBACK URL:", fill="#736E65")
    draw.rectangle([vbox_x + 20, vbox_y + 470, vbox_x + box_w - 20, vbox_y + 515], fill="#FBFAF7", outline="#D0CEC8")
    draw.text((vbox_x + 30, vbox_y + 485), "shady.example.org/portal/?target=venue:arlene-francis", fill="#121214")

    # Footer
    draw.rectangle([40, page_h - 70, page_w - 40, page_h - 68], fill="#121214")
    draw.text((50, page_h - 55), "Printed by ShadeNet Autonomous Dispatcher · Downtown Santa Rosa Open Public Gazetteer", fill="#736E65")
    draw.text((page_w - 380, page_h - 55), "ONLINE AT SHADY.example.org", fill="#121214")

    page.save(out_png, "PNG")


def main():
    print("Generating scannable marker cards and full zine print sheet...")

    # 1. Full Zine Print Sheet (simulates the entire printed newspaper page)
    sheet_png = ROOT / "web" / "print" / "zine-print-sheet.png"
    generate_full_zine_print_sheet(sheet_png)
    print(f"Created print sheet: {sheet_png}")

    # Copy to docs/screens
    generate_full_zine_print_sheet(SCREENS_DIR / "zine-print-sheet.png")

    # 2. Individual Marker Cards
    card1_png = ROOT / "web" / "data" / "markers" / "the-room-after-midnight.png"
    generate_marker_card(
        "note:the-room-after-midnight",
        "The Room After Midnight (Portal Marker)",
        "https://shady.example.org/portal/?target=note:the-room-after-midnight&ar=1",
        card1_png,
    )
    print(f"Created card: {card1_png}")

    card2_png = ROOT / "web" / "data" / "markers" / "venue-arlene-francis.png"
    generate_marker_card(
        "venue:arlene-francis",
        "Arlene Francis Center (Venue Portal)",
        "https://shady.example.org/portal/?target=venue:arlene-francis&ar=1",
        card2_png,
    )
    print(f"Created card: {card2_png}")

    # Update docs/screens/editorial-marker.png with the real scannable card
    generate_marker_card(
        "note:the-room-after-midnight",
        "The Room After Midnight (Print Marker)",
        "https://shady.example.org/portal/?target=note:the-room-after-midnight&ar=1",
        SCREENS_DIR / "editorial-marker.png",
    )
    print(f"Updated: {SCREENS_DIR / 'editorial-marker.png'}")


if __name__ == "__main__":
    main()
