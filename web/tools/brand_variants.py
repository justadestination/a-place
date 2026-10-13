#!/usr/bin/env python3
"""Derive header-sized brand marks from the master Canva PNGs in web/assets/brand.

The masters are ~2000px rasters; the header shows them at 40-112px, so we also
emit 256px copies to keep page weight down. Re-run after replacing a master.

    python3 web/tools/brand_variants.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
SMALL = 256


def recolor(im: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    """Flat-fill every opaque pixel with rgb, keeping the alpha edge."""
    out = Image.new("RGBA", im.size, rgb + (0,))
    out.putalpha(im.getchannel("A"))
    return out


def grayscale(im: Image.Image, lift: int = 0) -> Image.Image:
    """Luminance-only copy; lift brightens toward silver so it reads on dark bg."""
    g = ImageOps.grayscale(im.convert("RGB"))
    if lift:
        g = g.point(lambda v: min(255, v + lift))
    out = Image.merge("RGBA", (g, g, g, im.getchannel("A")))
    return out


def add_foot(im: Image.Image, style: str) -> Image.Image:
    """Give the Serendipilyst mark a base so its bottom spike stops reading as '$'.

    style="pedestal": flat bar centred under the spike.
    style="l": bar running right from the spike, like the foot of an L.
    """
    a = im.getchannel("A")
    w, h = im.size
    fill = im.getpixel((940, 1400))  # solid body colour of the mark
    # locate the bottom tip
    ys = [y for y in range(h) if any(a.getpixel((x, y)) > 128 for x in range(0, w, 4))]
    tip_y = ys[-1]
    row = [x for x in range(w) if a.getpixel((x, tip_y - 40)) > 128]
    tip_x = (row[0] + row[-1]) // 2
    bar_h = int(h * 0.06)
    pad = bar_h // 2
    canvas = Image.new("RGBA", (w, h + bar_h + pad), (0, 0, 0, 0))
    canvas.alpha_composite(im)
    d = ImageDraw.Draw(canvas)
    stem = int(w * 0.07)  # thicken the tip so it lands on the bar
    d.polygon([(tip_x - stem, tip_y - bar_h * 2), (tip_x + stem, tip_y - bar_h * 2),
               (tip_x + stem // 2, tip_y + pad), (tip_x - stem // 2, tip_y + pad)], fill=fill)
    if style == "pedestal":
        half = int(w * 0.30)
        x0, x1 = tip_x - half, tip_x + half
    else:
        x0, x1 = tip_x - stem, tip_x + int(w * 0.50)
    d.rounded_rectangle([x0, tip_y + pad - bar_h // 3, x1, tip_y + pad + bar_h], radius=bar_h // 3, fill=fill)
    return canvas


def small(im: Image.Image) -> Image.Image:
    im = im.crop(im.getbbox())
    im.thumbnail((SMALL, SMALL), Image.LANCZOS)
    return im


def main() -> None:
    sn = Image.open(BRAND / "shadenet-accent.png").convert("RGBA")
    nc = Image.open(BRAND / "nightcal-accent.png").convert("RGBA")
    uh = Image.open(BRAND / "uh-accent.png").convert("RGBA")
    se = Image.open(BRAND / "serendipilyst-accent.png").convert("RGBA")

    out = {
        "shadenet-blue": sn,
        "shadenet-gray": grayscale(sn, lift=40),
        "shadenet-silver": recolor(sn, (200, 204, 210)),
        "nightcal": nc,
        "uh-crimson": recolor(uh, (165, 28, 48)),
        "serendipilyst-pedestal": add_foot(se, "pedestal"),
        "serendipilyst-lfoot": add_foot(se, "l"),
    }
    for name, im in out.items():
        small(im).save(BRAND / f"{name}-256.png", optimize=True)
        print(f"wrote {name}-256.png")


if __name__ == "__main__":
    main()
