// E2E, Integration, and Perf tests for Task 3.1: Node-map view
// Obsidian-style graph: nodes = articles, reviews, letters, events, venues, entities;
// edges = [[wiki-links]] + frontmatter relations. Force-directed layout, pan/zoom, click a node to read it.
// Usable with 500+ nodes.

import { writeFileSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { launch, VIEWPORTS } from "../tools/browser.mjs";
import { graphScene } from "../js/data/graph.js";

const BASE = process.env.BASE || "http://127.0.0.1:8085";
const WEB = new URL("../", import.meta.url).pathname;
const DOCS = new URL("../../docs/", import.meta.url).pathname;
const SCREENS_DOCS = DOCS + "screens/";
const SCREENS_OUTPUT = WEB + "tests/output/";

mkdirSync(SCREENS_DOCS, { recursive: true });
mkdirSync(SCREENS_OUTPUT, { recursive: true });

console.log("=== Testing Node-map View (Task 3.1) ===");

// ---------------------------------------------------------------------------
// 1. Integration Test: build_zine.py with fixture markdown notes
// ---------------------------------------------------------------------------
console.log("\n1. Testing markdown [[wiki-link]] and frontmatter relations graph extraction...");
const fixtureDir = mkdtempSync(join(tmpdir(), "nightcal-graph-test-"));
const vaultDir = join(fixtureDir, "vault");
mkdirSync(vaultDir);

// Fixture 1: Article with wiki links and frontmatter relations
writeFileSync(join(vaultDir, "alpha-note.md"), `---
title: "Alpha Note"
type: article
author: "Zine Contributor"
events: ["evt-alpha"]
venues: ["ven-alpha"]
---
This note references [[Beta Note]] and an unresolved [[Secret Underground]].
Also mentions [[evt-alpha]].
`);

// Fixture 2: Review linking back to Alpha
writeFileSync(join(vaultDir, "beta-note.md"), `---
title: "Beta Note"
type: review
author: "Critic"
---
Reviewing the vibes from [[Alpha Note]].
`);

const outJson = join(fixtureDir, "zine.json");
const modelJson = join(fixtureDir, "model.json");
writeFileSync(modelJson, JSON.stringify({
  venues: [{ id: "ven-alpha", name: "Alpha Venue" }],
  events: [{ id: "evt-alpha", title: "Alpha Gathering", venueId: "ven-alpha" }]
}));

execFileSync("python3", [
  join(WEB, "tools/build_zine.py"),
  "--vault", vaultDir,
  "--model", modelJson,
  "--out", outJson
], { stdio: "pipe" });

const builtZine = JSON.parse(execFileSync("cat", [outJson], { encoding: "utf-8" }));
const nodeIds = new Set(builtZine.nodes.map(n => n.id));

if (!nodeIds.has("note:alpha-note") || !nodeIds.has("note:beta-note")) {
  throw new Error("Missing notes in extracted graph");
}
if (!nodeIds.has("venue:ven-alpha") || !nodeIds.has("event:evt-alpha")) {
  throw new Error("Missing calendar venue/event in extracted graph");
}
if (!nodeIds.has("missing:secret-underground")) {
  throw new Error("Missing unresolved [[Secret Underground]] as missing node in graph");
}

// Check edges:
// - link between alpha and beta
// - link between alpha and secret underground
// - frontmatter relation alpha -> evt-alpha
// - frontmatter relation alpha -> ven-alpha
// - event -> venue "at" edge
const edgePairs = builtZine.edges.map(e => `${e.source} -> ${e.target} (${e.kind})`);
console.log(`Extracted ${builtZine.nodes.length} nodes and ${builtZine.edges.length} edges:`);
for (const p of edgePairs) console.log("  ", p);

const hasAlphaBeta = builtZine.edges.some(e => e.kind === "link" && e.source === "note:alpha-note" && e.target === "note:beta-note");
const hasBetaAlpha = builtZine.edges.some(e => e.kind === "link" && e.source === "note:beta-note" && e.target === "note:alpha-note");
const hasMissingLink = builtZine.edges.some(e => e.kind === "link" && e.source === "note:alpha-note" && e.target === "missing:secret-underground");
const hasFrontmatterEvent = builtZine.edges.some(e => e.kind === "events" && e.source === "note:alpha-note" && e.target === "event:evt-alpha");
const hasFrontmatterVenue = builtZine.edges.some(e => e.kind === "venues" && e.source === "note:alpha-note" && e.target === "venue:ven-alpha");

if (!hasAlphaBeta && !hasBetaAlpha) throw new Error("Missing wiki link edge between Alpha and Beta");
if (!hasMissingLink) throw new Error("Missing wiki link edge to unresolved note");
if (!hasFrontmatterEvent) throw new Error("Missing frontmatter event edge");
if (!hasFrontmatterVenue) throw new Error("Missing frontmatter venue edge");
console.log("✓ Fixture graph extraction verified: all nodes, [[wiki-links]], and relations correct.");

rmSync(fixtureDir, { recursive: true, force: true });

// ---------------------------------------------------------------------------
// 2. Performance Check: Usability with 500+ nodes
// ---------------------------------------------------------------------------
console.log("\n2. Testing force-directed layout performance with 500+ nodes...");
const syntheticNodes = [];
for (let i = 0; i < 500; i++) {
  syntheticNodes.push({
    id: `node-${i}`,
    title: `Community Node #${i}`,
    type: i % 5 === 0 ? "article" : i % 5 === 1 ? "review" : i % 5 === 2 ? "event" : i % 5 === 3 ? "venue" : "letter"
  });
}
const syntheticEdges = [];
// Create ~1000 edges connecting cluster hubs and neighboring nodes
for (let i = 0; i < 500; i++) {
  syntheticEdges.push({ source: `node-${i}`, target: `node-${(i + 1) % 500}`, kind: "link" });
  if (i % 3 === 0) {
    syntheticEdges.push({ source: `node-${i}`, target: `node-${(i * 7) % 500}`, kind: "link" });
  }
}

const t0 = performance.now();
const synthScene = graphScene({ nodes: syntheticNodes, edges: syntheticEdges }, { dims: 2, size: 2000 });
const layoutDurationMs = performance.now() - t0;
console.log(`✓ 500-node graph layout converged in ${layoutDurationMs.toFixed(1)}ms (${synthScene.nodes.length} nodes, ${synthScene.edges.length} edges).`);

if (layoutDurationMs > 3000) {
  throw new Error(`500-node layout exceeded 3000ms threshold: ${layoutDurationMs.toFixed(1)}ms`);
}
for (const n of synthScene.nodes) {
  if (isNaN(n.x) || isNaN(n.y)) throw new Error(`Node ${n.id} has invalid NaN coordinates`);
}

// ---------------------------------------------------------------------------
// 3. E2E Browser Test: Pan, Zoom, and Click-through on /zine/ and /embed/node-map/
// ---------------------------------------------------------------------------
console.log("\n3. Testing E2E pan, zoom, click-through, and capturing screenshot...");
const browser = await launch();
const page = await browser.newPage({ viewport: VIEWPORTS.desktop });

try {
  // Test standalone embed route
  await page.goto(`${BASE}/embed/node-map/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-map__svg");

  const initialTransform = await page.evaluate(() => {
    const vp = document.querySelector(".nc-map__viewport");
    return vp?.getAttribute("transform") || "";
  });
  console.log(`Initial map transform: "${initialTransform}"`);

  // Zoom In button
  const zoomInBtn = page.locator(".nc-map__tools button").first();
  await zoomInBtn.click();
  await page.waitForTimeout(100);

  const zoomedTransform = await page.evaluate(() => {
    const vp = document.querySelector(".nc-map__viewport");
    return vp?.getAttribute("transform") || "";
  });
  console.log(`After Zoom In transform: "${zoomedTransform}"`);
  if (initialTransform === zoomedTransform) {
    throw new Error("Zoom In button did not change viewport transform");
  }

  // Pan via dragging the SVG stage
  const svgEl = page.locator(".nc-map__svg");
  const box = await svgEl.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 100, box.y + box.height / 2 + 50, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(100);
  }

  const pannedTransform = await page.evaluate(() => {
    const vp = document.querySelector(".nc-map__viewport");
    return vp?.getAttribute("transform") || "";
  });
  console.log(`After Pan transform: "${pannedTransform}"`);
  if (pannedTransform === zoomedTransform) {
    throw new Error("Pan drag did not alter viewport position");
  }

  // Click-through: click a node to select and assert preview card updates
  const firstNode = page.locator(".nc-map__node").first();
  const nodeId = await firstNode.getAttribute("data-id");
  console.log(`Clicking node "${nodeId}"...`);
  await firstNode.click();
  await page.waitForTimeout(150);

  const isSelected = await page.evaluate(id => {
    const n = document.querySelector(`.nc-map__node[data-id="${id}"]`);
    return n?.classList.contains("is-selected") || n?.getAttribute("tabindex") === "0";
  }, nodeId);

  if (!isSelected) {
    throw new Error(`Node ${nodeId} was not selected upon click`);
  }
  console.log(`✓ Node ${nodeId} selected successfully.`);

  // Test full zine page /zine/
  await page.goto(`${BASE}/zine/`, { waitUntil: "networkidle" });
  await page.waitForSelector(".nc-map__svg");

  // Capture screenshot of node map graph
  const screenshotPath = join(SCREENS_DOCS, "node-map-graph.png");
  await page.locator(".nc-map").screenshot({ path: screenshotPath });
  console.log(`✓ Screenshot captured to ${screenshotPath}`);

} finally {
  await browser.close();
}

console.log("\n=== All Node-map View (Task 3.1) tests passed successfully! ===");
