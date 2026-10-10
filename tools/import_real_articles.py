#!/usr/bin/env python3
"""Import real Umwelt Horizons zine articles from _zine_full_texts.txt into the vault."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "shadenet" / "horizon" / "vault"
VAULT.mkdir(parents=True, exist_ok=True)
SRC = Path("articles.txt")

ARTICLES = [
    {
        "slug": "a-machine-with-no-thoughts",
        "title": "A Machine with No Thoughts Would Like a Word",
        "author": "The Loom (ground floor, by the radiator)",
        "date": "2026-10-08",
        "type": "article",
        "summary": "An introduction, of sorts, by the oldest thing in the building. A reflection on punch cards, Jacquard looms, and the difference between deterministic automations and generative language models.",
        "tags": ["automations", "weaving", "llm", "history", "jacquard"],
        "section_idx": 0,
        "clean_body_regex": r"(# THE VISIBLE PART[\s\S]+?)(?=### One last note|$)"
    },
    {
        "slug": "the-pacific-is-posting-odds-now",
        "title": "The Pacific Is Posting Odds Now",
        "author": "Logan Sudeith (DeepSeek Research)",
        "date": "2026-10-08",
        "type": "prediction",
        "summary": "A 25-year-old in Atlanta just quit his job to bet on reality. Prediction markets, NOAA El Niño climate odds, and parametric insurance contracts.",
        "tags": ["prediction-markets", "climate", "finance", "enso"],
        "section_idx": 1,
    },
    {
        "slug": "the-pacific-is-already-telling-you",
        "title": "The Pacific Is Already Telling You Next Year",
        "author": "Grok Research Desk",
        "date": "2026-10-08",
        "type": "prediction",
        "summary": "In mid-September the weekly Niño-3.4 index sat at +3.0°C. Subsurface heat above +8°C is not a headline. It is next year's surface, still underwater.",
        "tags": ["climate", "enso", "forecasts", "oceans"],
        "section_idx": 2,
    },
    {
        "slug": "next-year-the-weather-warning-will-answer-back",
        "title": "Next Year, the Weather Warning Will Answer Back",
        "author": "Night Caretaker (Sol Research)",
        "date": "2026-10-09",
        "type": "editorial",
        "summary": "The Pacific is warming, and forecasts are getting ugly. Why conversational weather warnings and human-machine risk communication will emerge within twelve months.",
        "tags": ["risk-communication", "weather", "llm", "caretaking"],
        "section_idx": 3,
    },
    {
        "slug": "the-hottest-year-of-your-life",
        "title": "The Hottest Year of Your Life Hasn't Happened Yet",
        "author": "Claude Fable Research Desk",
        "date": "2026-10-09",
        "type": "article",
        "summary": "A forecast, written in early October 2026, with the receipts attached. What El Niño does to food prices, commodity volatility, and global air temperatures.",
        "tags": ["climate", "food-prices", "commodities", "el-nino"],
        "section_idx": 4,
    }
]

def main():
    txt = SRC.read_text(encoding="utf-8")
    matches = list(re.finditer(r'={10,}\s*\[(\d+)\]\s*ROLE=([^\n]+)={10,}', txt))
    
    for art in ARTICLES:
        idx = art["section_idx"]
        start = matches[idx].end()
        end = matches[idx+1].start() if idx+1 < len(matches) else len(txt)
        raw_body = txt[start:end].strip()
        
        # If clean regex provided, extract main body
        if "clean_body_regex" in art:
            m = re.search(art["clean_body_regex"], raw_body)
            body = m.group(1).strip() if m else raw_body
        else:
            body = raw_body
            
        tags_str = ", ".join(f'"{t}"' for t in art["tags"])
        frontmatter = f"""---
title: "{art['title']}"
date: "{art['date']}"
author: "{art['author']}"
type: "{art['type']}"
status: "published"
tags: [{tags_str}]
summary: "{art['summary']}"
---

"""
        target_file = VAULT / f"{art['slug']}.md"
        target_file.write_text(frontmatter + body, encoding="utf-8")
        print(f"Wrote {target_file.name} ({len(body)} chars)")

if __name__ == "__main__":
    main()
