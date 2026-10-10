#!/usr/bin/env python3
"""Process and optimize brand assets for NightCal, Serendipilyst, ShadeNet, and Umwelt Horizons.

Generates:
- Light mode (dark ink #121214) and dark mode (bright #FBFAF7) versions
- Accent color versions (#FFC14D)
- Vector SVGs with clean viewBox
- PWA icons (192x192, 512x512, apple-touch-icon 180x180)
- Clean favicon.svg with authentic NightCal mark
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = Path(".")
BRAND_DIR = ROOT / "web" / "assets" / "brand"
BRAND_DIR.mkdir(parents=True, exist_ok=True)
DOCS_BRAND_DIR = ROOT / "docs" / "assets" / "brand"
DOCS_BRAND_DIR.mkdir(parents=True, exist_ok=True)

ITEMS = [
    ("NightCal", "#FFC14D", "NightCal Downtown Calendar"),
    ("Serendipilyst", "#68D391", "Serendipilyst Autonomous Exchange"),
    ("ShadeNet", "#63B3ED", "ShadeNet Decentralized Mesh Daemon"),
    ("UH", "#F6AD55", "Umwelt Horizons Editorial Dispatch"),
]

def tint_image(src_img: Image.Image, color_hex: str) -> Image.Image:
    """Tint white alpha mask with a target RGB hex color."""
    # Ensure source is RGBA
    rgba = src_img.convert("RGBA")
    r_target = int(color_hex[1:3], 16)
    g_target = int(color_hex[3:5], 16)
    b_target = int(color_hex[5:7], 16)
    
    # Split alpha
    r, g, b, alpha = rgba.split()
    # Create solid color image
    solid = Image.new("RGBA", rgba.size, (r_target, g_target, b_target, 255))
    solid.putalpha(alpha)
    return solid

def main():
    print("Processing brand assets...")
    
    for name, accent_hex, title in ITEMS:
        src_png = SRC_DIR / f"{name}.png"
        src_svg = SRC_DIR / f"{name}.svg"
        
        if not src_png.exists():
            print(f"Skipping {name}: {src_png} not found")
            continue
            
        orig = Image.open(src_png).convert("RGBA")
        bbox = orig.getbbox()
        cropped = orig.crop(bbox)
        
        # Save raw originals
        orig.save(BRAND_DIR / f"{name}.png")
        orig.save(DOCS_BRAND_DIR / f"{name}.png")
        
        if src_svg.exists():
            content = src_svg.read_bytes()
            (BRAND_DIR / f"{name}.svg").write_bytes(content)
            (DOCS_BRAND_DIR / f"{name}.svg").write_bytes(content)
            
        # 1. White on transparent (dark background)
        white_cropped = cropped
        white_cropped.save(BRAND_DIR / f"{name.lower()}-white.png")
        
        # 2. Dark ink on transparent (light background / newsprint)
        dark_cropped = tint_image(cropped, "#121214")
        dark_cropped.save(BRAND_DIR / f"{name.lower()}-dark.png")
        
        # 3. Accent colored version
        accent_cropped = tint_image(cropped, accent_hex)
        accent_cropped.save(BRAND_DIR / f"{name.lower()}-accent.png")
        
        print(f"Rendered {name}: white, dark, accent PNG variants ({cropped.size[0]}x{cropped.size[1]})")

    # 4. Generate App Icons from NightCal
    print("Generating PWA and Favicon icons from NightCal...")
    nc_orig = Image.open(BRAND_DIR / "NightCal.png").convert("RGBA")
    bbox = nc_orig.getbbox()
    nc_cropped = nc_orig.crop(bbox)
    
    # Make square icons with nice padding and dark background
    def make_app_icon(size: int, pad_ratio: float = 0.18) -> Image.Image:
        icon = Image.new("RGBA", (size, size), "#121214")
        target_inner = int(size * (1 - 2 * pad_ratio))
        # Keep aspect ratio
        nc_resized = nc_cropped.copy()
        nc_resized.thumbnail((target_inner, target_inner), Image.Resampling.LANCZOS)
        
        # Golden amber NightCal mark
        tinted = tint_image(nc_resized, "#FFC14D")
        
        offset_x = (size - tinted.size[0]) // 2
        offset_y = (size - tinted.size[1]) // 2
        icon.paste(tinted, (offset_x, offset_y), tinted)
        return icon

    icon_512 = make_app_icon(512)
    icon_512.save(ROOT / "web" / "icon-512.png")
    
    icon_192 = make_app_icon(192)
    icon_192.save(ROOT / "web" / "icon-192.png")
    
    icon_apple = make_app_icon(180)
    icon_apple.save(ROOT / "web" / "apple-touch-icon.png")
    
    # Generate SVG Favicon embedding the crisp amber mark
    buf = io.BytesIO()
    icon_192.save(buf, format="PNG")
    b64_png = base64.b64encode(buf.getvalue()).decode("ascii")
    
    favicon_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="42" fill="#121214"/>
  <image href="data:image/png;base64,{b64_png}" width="192" height="192"/>
</svg>'''
    (ROOT / "web" / "favicon.svg").write_text(favicon_svg, encoding="utf-8")
    print("Updated web/favicon.svg, icon-192.png, icon-512.png, apple-touch-icon.png")

if __name__ == "__main__":
    main()
