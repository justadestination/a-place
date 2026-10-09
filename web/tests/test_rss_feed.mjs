// Integration test for Task 3.4: Zine RSS feed
// Verifies:
//   1. Full-content RSS 2.0 feed structure and XML validation.
//   2. RFC-822 timestamps and content:encoded enclosures.
//   3. Publication flow: newly published article appears in the feed.

import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const WEB = new URL("../", import.meta.url).pathname;

console.log("=== Testing Zine RSS Feed (Task 3.4) ===");

// ---------------------------------------------------------------------------
// 1. Validate Existing Built RSS Feed
// ---------------------------------------------------------------------------
console.log("\n1. Validating existing generated RSS feed...");
const feedPath = join(WEB, "zine/feed.xml");
if (!existsSync(feedPath)) {
  throw new Error(`Feed file not found at ${feedPath}. Run build_zine.py first.`);
}

const feedXml = readFileSync(feedPath, "utf-8");

// XML structure checks
if (!feedXml.includes('<?xml version="1.0" encoding="UTF-8"?>')) {
  throw new Error("Missing XML declaration");
}
if (!feedXml.includes('<rss version="2.0"')) {
  throw new Error("Missing rss 2.0 root element");
}
if (!feedXml.includes('xmlns:content="http://purl.org/rss/1.0/modules/content/"')) {
  throw new Error("Missing content namespace for full-content RSS");
}
if (!feedXml.includes("<title>Umwelt Horizons · NightCal Zine</title>")) {
  throw new Error("Missing or incorrect channel title");
}
if (!feedXml.includes("<link>https://nightcal.example.org/zine/</link>")) {
  throw new Error("Missing channel link");
}
if (!feedXml.includes('<atom:link href="https://nightcal.example.org/zine/feed.xml" rel="self"')) {
  throw new Error("Missing atom self-link");
}

// Items inspection
const items = [...feedXml.matchAll(/<item>([\s\S]*?)<\/item>/g)];
console.log(`Found ${items.length} items in RSS feed.`);
if (items.length === 0) {
  throw new Error("Feed must contain at least one published item");
}

for (const [idx, itemMatch] of items.entries()) {
  const itemBody = itemMatch[1];
  if (!itemBody.includes("<title>")) throw new Error(`Item ${idx} missing title`);
  if (!itemBody.includes("<link>")) throw new Error(`Item ${idx} missing link`);
  if (!itemBody.includes("<guid")) throw new Error(`Item ${idx} missing guid`);
  if (!itemBody.includes("<pubDate>")) throw new Error(`Item ${idx} missing pubDate`);
  if (!itemBody.includes("<content:encoded>")) throw new Error(`Item ${idx} missing full HTML content:encoded`);

  // Verify RFC-822 date format
  const dateMatch = itemBody.match(/<pubDate>(.*?)<\/pubDate>/);
  if (!dateMatch) throw new Error(`Item ${idx} date match failed`);
  const parsedDate = Date.parse(dateMatch[1]);
  if (isNaN(parsedDate)) {
    throw new Error(`Item ${idx} invalid RFC-822 date: ${dateMatch[1]}`);
  }
}
console.log("✓ RSS feed syntax, elements, RFC-822 dates, and content enclosures valid.");

// ---------------------------------------------------------------------------
// 2. Publication Flow: Newly Published Note Appears in Feed
// ---------------------------------------------------------------------------
console.log("\n2. Testing publish flow: new article appears in regenerated feed...");
const fixtureDir = mkdtempSync(join(tmpdir(), "nightcal-rss-publish-"));
const vaultDir = join(fixtureDir, "vault");
mkdirSync(vaultDir);

// Create a new test note
const newArticleTitle = "Flash Dispatch: Midnight Warehouse Resonance";
writeFileSync(join(vaultDir, "warehouse-resonance.md"), `---
title: "${newArticleTitle}"
type: article
author: "Zine Field Agent"
date: "2026-10-09"
---
Sub-bass frequencies measured across the southern industrial district.
The acoustic reflection off concrete is pristine.
`);

const outJson = join(fixtureDir, "zine.json");
const modelJson = join(fixtureDir, "model.json");
writeFileSync(modelJson, JSON.stringify({ venues: [], events: [] }));

execFileSync("python3", [
  join(WEB, "tools/build_zine.py"),
  "--vault", vaultDir,
  "--model", modelJson,
  "--out", outJson
], { stdio: "pipe" });

// Check regenerated feed
const refreshedFeedXml = readFileSync(feedPath, "utf-8");
if (!refreshedFeedXml.includes(newArticleTitle)) {
  throw new Error(`Newly published article "${newArticleTitle}" was not found in the regenerated RSS feed`);
}
if (!refreshedFeedXml.includes("Sub-bass frequencies measured across")) {
  throw new Error("Full content of newly published article missing from content:encoded enclosure");
}
console.log(`✓ Publish flow verified: "${newArticleTitle}" appeared in feed.`);

rmSync(fixtureDir, { recursive: true, force: true });

// Restore original feed by rebuilding zine with default vault
execFileSync("python3", [join(WEB, "tools/build_zine.py")], { stdio: "pipe" });
console.log("✓ Original feed restored.");

console.log("\n=== All Zine RSS Feed (Task 3.4) tests passed successfully! ===");
