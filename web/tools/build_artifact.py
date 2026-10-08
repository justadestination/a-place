#!/usr/bin/env python3
"""Regenerate the design-system artifact's files in design-system/project/.

The published artifact (see design-system/README.md) is a copy of that
folder. This script rebuilds the parts derived from the real sources, so the
artifact can't drift from tokens/ and web/components/:

    design-system/project/tokens.json                 from tokens/ (artifact list format)
    design-system/project/components/<Comp>/README.md from web/components/<name>/README.md
    design-system/project/components/bundle.css       from web/css/nightcal.css

Hand-maintained there (edit in place): README.md (brand book),
components/Cover/preview.html, design-system.json (index).
Previews (components/<Comp>/preview.html) are captured from the live embed
routes by tools/artifact_previews.mjs, which needs the dev server.

    python3 web/tools/build_artifact.py           write
    python3 web/tools/build_artifact.py --check   exit 1 if anything is stale
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent
ROOT = WEB.parent
OUT = ROOT / "design-system" / "project"

USAGE = {
    "bg": "Page background.",
    "surface": "Cards, rows, controls.",
    "surface-raised": "Dialogs, popovers, menus.",
    "surface-sunken": "Wells: month cells, the zine map, code.",
    "text": "Body text and headings on any surface.",
    "text-muted": "Secondary text: venue, counts, bylines. AA on every surface.",
    "border": "Decorative dividers and card edges (no contrast requirement).",
    "border-strong": "Control borders: inputs, buttons, segmented controls. 3:1 on bg and surface.",
    "accent": "Bulb amber. Fill of the ONE primary button and the selected segment in dark. Never text on light.",
    "on-accent": "Text on accent fills.",
    "accent-text": "Amber as text (eyebrows, highlights). Darker in light theme so it reads.",
    "link": "Links.",
    "focus": "Focus ring (3px). 3:1 on every surface.",
    "selected-bg": "Selected day / segment fill.",
    "selected-text": "Text on selected-bg.",
    "today": "Today marker (underline or border).",
    "scrim": "Behind modal dialogs.",
    "shadow": "Shadow colour.",
    "graph-edge": "Zine map edges (3:1 on the map well).",
    "graph-edge-active": "Edges of the selected node.",
}
STYLE_NOTES = [
    ("display", "64px", 1.1, 800, "Page headline (fluid: 36px on phones to 64px). \"Tonight\".", "Tonight"),
    ("3xl", None, 1.1, 800, "Reader titles, the next-night headline.", None),
    ("2xl", None, 1.1, 800, "Section titles, event card title.", None),
    ("xl", None, 1.3, 800, "Month title, wordmark, day numbers.", None),
    ("lg", None, 1.3, 700, "Billboard row: time and title. Lede paragraphs.", "9:00 pm  Turn of the Century"),
    ("md", None, 1.5, 400, "Body text, controls.", None),
    ("sm", None, 1.5, 700, "Labels, eyebrows (uppercase, +0.06em), kind tags.", None),
    ("xs", None, 1.3, 700, "Smallest text allowed (13px): weekday heads, counts.", None),
]
SPACE_NOTES = ["Hairline gaps, segmented inset.", "Inline gaps, small padding.", "Control padding, list gaps.",
               "Card padding, default stack gap.", "Card body padding, section inner gaps.", "Section spacing.",
               "Between page sections.", "Page bottom spacing."]


def pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in name.split("-"))


def color_usage(name: str) -> str:
    if name in USAGE:
        return USAGE[name]
    m = re.match(r"kind-(\w+)-(bg|fg|mark)$", name)
    if m:
        kind, part = m.groups()
        return {"bg": f"Kind tag fill for {kind}.", "fg": f"Kind tag text for {kind} (4.5:1 on its bg).",
                "mark": f"Glyph colour for {kind} on surfaces (3:1)."}[part]
    m = re.match(r"node-(\w+)$", name)
    if m:
        return f"Zine map node: {m.group(1)} (3:1 on the map well)."
    return ""


def norm(value: str) -> str:
    value = value.strip()
    return value.lower() if value.startswith("#") else value.replace(" ", "")


def tokens_json() -> dict:
    base = json.loads((ROOT / "tokens" / "base.json").read_text())
    light = json.loads((ROOT / "tokens" / "themes" / "light.json").read_text())
    dark = json.loads((ROOT / "tokens" / "themes" / "dark.json").read_text())
    src = (WEB / "js" / "core" / "tokens.js").read_text()
    resolved = json.loads(src[src.index("{"):src.rindex("}") + 1])["themes"]
    colors = [{
        "name": name,
        "value": {"light": norm(resolved["light"]["values"][f"color-{name}"]), "dark": norm(resolved["dark"]["values"][f"color-{name}"])},
        "usage": color_usage(name),
    } for name in light["color"]]
    sizes = base["font"]["size"]
    styles = []
    for name, size, lh, weight, usage, sample in STYLE_NOTES:
        style = {"name": name, "fontSize": size or sizes[name], "lineHeight": lh, "fontWeight": weight}
        if name == "display":
            style["letterSpacing"] = base["font"]["tracking"]["tight"]
        style["usage"] = usage
        if sample:
            style["sample"] = sample
        styles.append(style)
    spaces = [(k, v) for k, v in base["space"].items() if k != "0"]
    return {
        "name": "NightCal", "version": 1,
        "color": {"themes": [{"id": "light", "name": "Light"}, {"id": "dark", "name": "Dark"}], "tokens": colors},
        "type": {"fonts": [], "families": {"sans": base["font"]["family"]["sans"], "mono": base["font"]["family"]["mono"]},
                 "groups": [{"name": "Text", "family": "sans", "styles": styles}]},
        "spacing": {"note": "Every space token is multiplied by --nc-density (Tight 0.8 · Normal 1 · Roomy 1.25) at runtime.",
                    "tokens": [{"name": f"space-{k}", "value": v, "usage": u} for (k, v), u in zip(spaces, SPACE_NOTES)]},
        "radius": {"tokens": [
            {"name": "radius-sm", "value": base["radius"]["sm"], "usage": "Month cells, inner segments, code."},
            {"name": "radius-md", "value": base["radius"]["md"], "usage": "Buttons, inputs, rows."},
            {"name": "radius-lg", "value": base["radius"]["lg"], "usage": "Cards, dialogs, map well."},
            {"name": "radius-pill", "value": base["radius"]["pill"], "usage": "Kind tags, count badges."},
        ]},
        "shadow": {"tokens": [
            {"name": "shadow-raised", "value": {"light": light["shadow"]["raised"], "dark": dark["shadow"]["raised"]}, "usage": "Cards."},
            {"name": "shadow-overlay", "value": {"light": light["shadow"]["overlay"], "dark": dark["shadow"]["overlay"]}, "usage": "Dialogs, popovers."},
        ]},
        "size": {"tokens": [
            {"name": "size-target", "value": "44px", "usage": "Minimum touch target for every control."},
            {"name": "size-focus-ring", "value": base["size"]["focus-ring"], "usage": "Focus ring width."},
            {"name": "size-content-max", "value": "1152px", "usage": "Page content width."},
            {"name": "size-glyph", "value": "12px", "usage": "Kind / node-type glyph."},
        ]},
        "meta": {"source": "justadestination/a-place tokens/ (base.json, themes/light.json, themes/dark.json); generated by tokens/build.py"},
    }


def outputs() -> dict[Path, str]:
    files = {OUT / "tokens.json": json.dumps(tokens_json(), indent=2)}
    files[OUT / "components" / "bundle.css"] = (WEB / "css" / "nightcal.css").read_text()
    for folder in sorted((WEB / "components").iterdir()):
        readme = folder / "README.md"
        if folder.is_dir() and readme.exists():
            files[OUT / "components" / pascal(folder.name) / "README.md"] = readme.read_text()
    return files


def main(argv: list[str]) -> int:
    stale = []
    for path, text in outputs().items():
        current = path.read_text() if path.exists() else None
        if current == text:
            continue
        stale.append(path.relative_to(ROOT))
        if "--check" not in argv:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    if "--check" in argv:
        if stale:
            print("design-system artifact is stale; run python3 web/tools/build_artifact.py:\n  " + "\n  ".join(map(str, stale)), file=sys.stderr)
            return 1
        print("design-system artifact: up to date")
        return 0
    print(f"design-system artifact: {len(stale)} file(s) updated" + (": " + ", ".join(map(str, stale)) if stale else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
