"""Deterministic synthetic media for the social flyer / animation harvester.

This module exists so the test suite can assert end-to-end behavior of the
OCR-to-listing pipeline with zero network and zero external OCR. Every
GigFactory builds a tiny, pixel-exact PNG poster whose ASCII art is a known
string; the harvester's `_read_text_fast` downmix reads that string back out
verbatim, so the extraction heuristics have something real to grab on, and
the assertions are deterministic.

Public API
----------
    GigFactory()                       create a blank factory
    GigFactory().poster(line=...)       draw one full-bleed flyer PNG
    GigFactory().story(line=...)        draw one animated-sticker PNG sequence
    GigFactory().base64_png(...)        fetch the same image as base64
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from io import BytesIO
from typing import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_PATH = Path(__file__).resolve().parent / "fonts" / "Roboto-Regular.ttf"
if not _FONT_PATH.exists():
    _FONT_PATH = None


def _font(size: int):
    try:
        return ImageFont.truetype(str(_FONT_PATH), size)
    except Exception:
        return ImageFont.load_default()


@dataclass
class GigFactory:
    seed: int = 0
    _lines: list[str] = field(default_factory=list)

    def poster(self, *, line: str, width: int = 640, height: int = 480) -> Path:
        self._lines = [line]
        path = self._save(self._draw_poster, width, height)
        return path

    def story(self, *, line: str, width: int = 640, height: int = 480) -> Path:
        self._lines = [line]
        path = self._save(self._draw_story, width, height)
        return path

    def base64_png(self, *, line: str = "SHADE NET 21+ GIG POSTER", size: int = 640) -> str:
        self._lines = [line]
        im = self._draw_poster(size, size)
        buf = BytesIO()
        im.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _draw_poster(self, width: int, height: int) -> Image.Image:
        im = Image.new("RGB", (width, height), (238, 238, 238))
        draw = ImageDraw.Draw(im)
        # 20px font -> ~120px per short line -> fits inside 640 wide.
        font = _font(20)
        y = height // 2 - font.size // 2
        for i, line in enumerate(self._lines):
            if i:
                y += font.size + 30
            draw.text((width // 2, y), line, fill=(30, 30, 30), font=font, anchor="mm")
        return im

    def _draw_story(self, width: int, height: int) -> Image.Image:
        return self._draw_poster(width, height)

    def _save(self, draw: Callable[[int, int], Image.Image], width: int, height: int) -> Path:
        im = draw(width, height)
        buf = BytesIO()
        im.save(buf, format="PNG")
        digest = base64.b64encode(buf.getvalue())[:12].hex()
        path = Path(__file__).resolve().parent / "data" / "flyer_mock" / f"{digest}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(buf.getvalue())
        return path

    @staticmethod
    def line_21plus() -> str:
        return "THE SHADE NETWORK 21+ GIG POSTER #1"

    @staticmethod
    def line_vintage() -> str:
        return "VIN TAGE SPACE  FRIDAY PUNK SHOW"

    @staticmethod
    def line_3disciples() -> str:
        return "3 DISCIPLES BREWING  LIVE UNICORN SHOW"

    @staticmethod
    def line_barrel() -> str:
        return "BARREL BROTHERS  SOUL JAZZ NIGHT"

    @staticmethod
    def line_shady() -> str:
        return "SHADY OAK  DRUM & BASS 21+"


_FACTORY = GigFactory(seed=1)


def make_image(label: str) -> Image.Image:
    lines = [_FACTORY.line_21plus()]
    if label == "vintage":
        lines = [_FACTORY.line_vintage()]
    elif label == "3disciples":
        lines = [_FACTORY.line_3disciples()]
    elif label == "barrel":
        lines = [_FACTORY.line_barrel()]
    elif label == "shady":
        lines = [_FACTORY.line_shady()]
    _FACTORY._lines = lines
    return _FACTORY._draw_poster(640, 480)


if __name__ == "__main__":
    import sys

    label = sys.argv[1] if len(sys.argv) > 1 else "default"
    im = make_image(label)
    im.save(f"mock_{label}.png")
    print(f"wrote mock_{label}.png ({im.size})")
