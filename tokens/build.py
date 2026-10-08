#!/usr/bin/env python3
"""Build the NightCal token outputs from the JSON sources in this folder.

Sources (edit these):
    tokens/base.json          primitives (palette, type, space, radius, size, motion, density)
    tokens/themes/*.json      semantic tokens per theme; values are literals or {path} refs
    tokens/pairs.json         every fg/bg pairing components use, with its WCAG minimum

Outputs (never edit by hand):
    web/css/tokens.css        CSS custom properties, light default, dark via
                              prefers-color-scheme and [data-theme="dark"]
    web/js/core/tokens.js     the same values as an ES module (theme API, 3D renderer)
    tokens/dist/tokens.json   flat name -> value per theme, for other tools
    tokens/dist/contrast.md   the contrast report for every theme and pair

The build fails (exit 1) when any pair in any theme is under its minimum.

    python3 tokens/build.py            build and check
    python3 tokens/build.py --check    check only, write nothing
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = ROOT / "web"
PREFIX = "--nc-"
REF = re.compile(r"^\{([^}]+)\}$")
THEME_ORDER = ("light", "dark")


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def lookup(tree: dict, dotted: str):
    node = tree
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"unknown token reference {{{dotted}}}")
        node = node[part]
    return node


def resolve(value, base: dict):
    if isinstance(value, str):
        match = REF.match(value)
        if match:
            return resolve(lookup(base, match.group(1)), base)
    return value


def flatten(tree: dict, path: tuple[str, ...] = ()) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in tree.items():
        if key.startswith("$"):
            continue
        if isinstance(value, dict):
            out.update(flatten(value, path + (key,)))
        else:
            out["-".join(path + (key,))] = value
    return out


# --- color math (WCAG 2.x relative luminance) -------------------------------

def parse_color(value: str) -> tuple[float, float, float, float]:
    text = value.strip()
    if text.startswith("#"):
        hexes = text[1:]
        if len(hexes) in (3, 4):
            hexes = "".join(ch * 2 for ch in hexes)
        r, g, b = (int(hexes[i:i + 2], 16) for i in (0, 2, 4))
        a = int(hexes[6:8], 16) / 255 if len(hexes) == 8 else 1.0
        return r, g, b, a
    match = re.match(r"rgba?\(([^)]+)\)", text)
    if match:
        parts = [p.strip() for p in re.split(r"[,\s/]+", match.group(1)) if p.strip()]
        r, g, b = (float(p) for p in parts[:3])
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return r, g, b, a
    raise ValueError(f"cannot read color {value!r}")


def blend(fg, bg):
    r, g, b, a = fg
    return (r * a + bg[0] * (1 - a), g * a + bg[1] * (1 - a), b * a + bg[2] * (1 - a), 1.0)


def luminance(rgb) -> float:
    def channel(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    back = parse_color(bg)
    front = blend(parse_color(fg), back)
    hi, lo = sorted((luminance(front), luminance(back)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# --- build ------------------------------------------------------------------

def primitive_vars(base: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, value in flatten(base).items():
        top = name.split("-", 1)[0]
        if top == "space" and value != "0":
            value = f"calc({value} * var({PREFIX}density))"
        elif top == "motion" and name.startswith("motion-duration"):
            value = f"calc({value} * var({PREFIX}motion-scale))"
            name = name.replace("motion-", "", 1)
        elif top == "motion":
            name = name.replace("motion-", "", 1)
        out.append((name, str(value)))
    return out


def theme_values(theme: dict, base: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    for group in ("color", "shadow"):
        for name, raw in theme.get(group, {}).items():
            values[f"{group}-{name}"] = str(resolve(raw, base))
    return values


def theme_refs(theme: dict) -> dict[str, str]:
    """Semantic name -> primitive var name, for values written as {palette.x.y}.

    The CSS points these at the primitive variable, so an agent that overrides
    a palette entry recolors every semantic token built on it.
    """
    refs: dict[str, str] = {}
    for group in ("color", "shadow"):
        for name, raw in theme.get(group, {}).items():
            match = REF.match(raw) if isinstance(raw, str) else None
            if match:
                refs[f"{group}-{name}"] = match.group(1).replace(".", "-")
    return refs


def css_values(values: dict[str, str], refs: dict[str, str]) -> list[tuple[str, str]]:
    return sorted((name, f"var({PREFIX}{refs[name]})" if name in refs else value) for name, value in values.items())


def block(selector: str, pairs: list[tuple[str, str]], extra: list[str] | None = None, indent: str = "") -> str:
    lines = [f"{indent}{selector} {{"]
    for line in extra or []:
        lines.append(f"{indent}  {line}")
    for name, value in pairs:
        lines.append(f"{indent}  {PREFIX}{name}: {value};")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def check(themes: dict[str, dict[str, str]], pairs: list[dict]) -> tuple[list[str], list[str]]:
    report, failures = [], []
    for theme_name, values in themes.items():
        report.append(f"\n## {theme_name}\n\n| fg | bg | ratio | min | result | use |\n|---|---|---|---|---|---|")
        for pair in pairs:
            fg, bg = values[f"color-{pair['fg']}"], values[f"color-{pair['bg']}"]
            ratio = contrast(fg, bg)
            ok = ratio + 1e-9 >= pair["min"]
            report.append(
                f"| `{pair['fg']}` {fg} | `{pair['bg']}` {bg} | {ratio:.2f}:1 | {pair['min']}:1 | {'pass' if ok else '**FAIL**'} | {pair['use']} |"
            )
            if not ok:
                failures.append(f"{theme_name}: {pair['fg']} on {pair['bg']} = {ratio:.2f}:1 (needs {pair['min']}:1)")
    return report, failures


def write_schema(token_names: list[str], base: dict) -> None:
    """tokens/theme.schema.json: the JSON Schema for agent-emitted theme specs."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://nightcal.justadestination.com/schema/theme.v1.json",
        "title": "NightCal theme spec v1",
        "description": "GENERATED by tokens/build.py. Token overrides plus runtime knobs. Apply with NightCal.theme.apply(spec) "
                       "or the embed 'theme' message. Unknown keys are reported and ignored; colour overrides that break any "
                       "pair in tokens/pairs.json are refused. See docs/THEME_API.md.",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "$schema": {"type": "string"},
            "version": {"const": 1},
            "name": {"type": "string", "maxLength": 80},
            "scheme": {"enum": ["system", "light", "dark"]},
            "textScale": {"type": "number", "minimum": 1, "maximum": 2, "description": "Multiplies every rem size. 1 = default."},
            "density": {"oneOf": [{"enum": list(base["density"])}, {"type": "number", "minimum": 0.75, "maximum": 1.5}],
                        "description": "Multiplies every space-* token."},
            "motion": {"enum": ["system", "reduce", "full"]},
            "tokens": {"$ref": "#/$defs/overrides", "description": "Overrides for every scheme."},
            "schemes": {"type": "object", "additionalProperties": False,
                        "properties": {"light": {"$ref": "#/$defs/overrides"}, "dark": {"$ref": "#/$defs/overrides"}}},
        },
        "$defs": {"overrides": {
            "type": "object",
            "description": "Keys are token names with '-' or '.' separators (color-accent == color.accent), optionally prefixed --nc-.",
            "propertyNames": {"pattern": "^(--nc-)?[a-z0-9]+([.-][a-z0-9]+)*$"},
            "additionalProperties": {"type": "string", "maxLength": 200},
            "x-token-names": token_names,
        }},
    }
    (HERE / "theme.schema.json").write_text(json.dumps(schema, indent=2) + "\n")


def main(argv: list[str]) -> int:
    only_check = "--check" in argv
    base = load(HERE / "base.json")
    pairs = load(HERE / "pairs.json")["pairs"]
    sources = {path.stem: load(path) for path in sorted((HERE / "themes").glob("*.json"))}
    names = [n for n in THEME_ORDER if n in sources] + [n for n in sources if n not in THEME_ORDER]
    themes = {name: theme_values(sources[name], base) for name in names}
    refs = {name: theme_refs(sources[name]) for name in names}

    # Every theme must define the same semantic names as the first one.
    reference = set(themes[names[0]])
    for name in names[1:]:
        missing = reference - set(themes[name])
        extra = set(themes[name]) - reference
        if missing or extra:
            print(f"theme {name}: missing {sorted(missing)} extra {sorted(extra)}", file=sys.stderr)
            return 1

    report, failures = check(themes, pairs)
    if failures:
        print("contrast failures:\n  " + "\n  ".join(failures), file=sys.stderr)
    if only_check:
        return 1 if failures else 0
    if failures:
        return 1

    knobs = [("text-scale", "1"), ("density", "1"), ("motion-scale", "1")]
    prims = primitive_vars(base)
    light = css_values(themes["light"], refs["light"])
    dark = css_values(themes["dark"], refs["dark"])
    css = [
        "/* NightCal tokens. GENERATED by tokens/build.py from tokens/*.json. Do not edit. */",
        "/* Runtime knobs (--nc-text-scale, --nc-density, --nc-motion-scale) are set by web/js/core/theme.js. */",
        "",
        block(":root", knobs + prims + light, ["color-scheme: light;"]),
        "",
        "@media (prefers-color-scheme: dark) {",
        block(':root:not([data-theme="light"])', dark, ["color-scheme: dark;"], indent="  "),
        "}",
        "",
        block(':root[data-theme="dark"]', dark, ["color-scheme: dark;"]),
        "",
        block(':root[data-theme="light"]', light, ["color-scheme: light;"]),
        "",
        "@media (prefers-reduced-motion: reduce) {",
        f'  :root:not([data-motion="full"]) {{ {PREFIX}motion-scale: 0; }}',
        "}",
        f':root[data-motion="reduce"] {{ {PREFIX}motion-scale: 0; }}',
        f':root[data-density="compact"] {{ {PREFIX}density: {base["density"]["compact"]}; }}',
        f':root[data-density="spacious"] {{ {PREFIX}density: {base["density"]["spacious"]}; }}',
        "",
    ]
    (WEB / "css").mkdir(parents=True, exist_ok=True)
    (WEB / "css" / "tokens.css").write_text("\n".join(css))

    module = {
        "prefix": PREFIX,
        "themes": {name: {"label": sources[name].get("label", name), "colorScheme": sources[name].get("colorScheme", name), "values": themes[name], "refs": refs[name]} for name in names},
        "primitives": dict(prims),
        "density": base["density"],
        "knobs": dict(knobs),
        "pairs": [{k: p[k] for k in ("fg", "bg", "min")} for p in pairs],
    }
    js = (
        "// NightCal tokens. GENERATED by tokens/build.py from tokens/*.json. Do not edit.\n"
        "// Used by the theme API (contrast checks on overrides) and by the 3D renderer.\n"
        f"export const TOKENS = {json.dumps(module, indent=2)};\n"
        "export default TOKENS;\n"
    )
    (WEB / "js" / "core").mkdir(parents=True, exist_ok=True)
    (WEB / "js" / "core" / "tokens.js").write_text(js)

    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    flat = {name: {f"{PREFIX}{k}": v for k, v in (dict(prims) | themes[name]).items()} for name in names}
    (dist / "tokens.json").write_text(json.dumps(flat, indent=2) + "\n")
    (dist / "contrast.md").write_text(
        "# Contrast report\n\nGenerated by `tokens/build.py`. Every pair components use, per theme. "
        "Alpha colors are blended over their background first.\n" + "\n".join(report) + "\n"
    )
    write_schema(sorted(set(dict(prims)) | set(themes[names[0]])), base)
    total = len(pairs) * len(names)
    print(f"tokens: {len(prims)} primitives, {len(reference)} semantic x {len(names)} themes; contrast {total}/{total} pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
