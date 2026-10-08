// Small deterministic force-directed layout (no dependencies).
// Charge repulsion + link springs + centering + collision, run to rest before
// first paint so the map never jiggles (and reduced motion is free).
// Works in 2 or 3 dimensions. O(n^2) per tick; fine for a zine (< 500 nodes).

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

export function layout(nodes, edges, { dims = 2, size = 1000, ticks = 400, linkDistance = 80, charge = 4200 } = {}) {
  const n = nodes.length;
  if (!n) return nodes;
  const index = new Map(nodes.map((node, i) => [node.id, i]));
  const pos = new Float64Array(n * 3);
  const vel = new Float64Array(n * 3);
  // Seed positions from the node id so the layout is stable between builds.
  for (let i = 0; i < n; i++) {
    const r = rng(hash(nodes[i].id));
    const radius = size * 0.3 * Math.sqrt(r());
    const a = r() * Math.PI * 2, b = Math.acos(2 * r() - 1);
    pos[i * 3] = radius * Math.cos(a) * (dims === 3 ? Math.sin(b) : 1);
    pos[i * 3 + 1] = radius * Math.sin(a) * (dims === 3 ? Math.sin(b) : 1);
    pos[i * 3 + 2] = dims === 3 ? radius * Math.cos(b) : 0;
  }
  const links = edges.map(e => [index.get(e.source), index.get(e.target)]).filter(([a, b]) => a != null && b != null);
  const deg = new Float64Array(n);
  for (const [a, b] of links) { deg[a]++; deg[b]++; }
  const radiusOf = i => 10 + Math.min(14, deg[i] * 2);

  for (let t = 0; t < ticks; t++) {
    const alpha = 1 - t / ticks;
    // Repulsion
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = pos[j * 3] - pos[i * 3], dy = pos[j * 3 + 1] - pos[i * 3 + 1], dz = pos[j * 3 + 2] - pos[i * 3 + 2];
        let d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < 1) { dx = 1; dy = 0.5; dz = 0; d2 = 1.25; }
        const d = Math.sqrt(d2);
        const f = (charge * alpha) / d2;
        const minD = radiusOf(i) + radiusOf(j) + 8;
        const push = d < minD ? (minD - d) * 0.5 : 0;
        const fx = (dx / d) * (f + push), fy = (dy / d) * (f + push), fz = (dz / d) * (f + push);
        vel[i * 3] -= fx; vel[i * 3 + 1] -= fy; vel[i * 3 + 2] -= fz;
        vel[j * 3] += fx; vel[j * 3 + 1] += fy; vel[j * 3 + 2] += fz;
      }
    }
    // Springs
    for (const [a, b] of links) {
      const dx = pos[b * 3] - pos[a * 3], dy = pos[b * 3 + 1] - pos[a * 3 + 1], dz = pos[b * 3 + 2] - pos[a * 3 + 2];
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
      const k = ((d - linkDistance) / d) * 0.08 * alpha;
      const wa = deg[b] / (deg[a] + deg[b]), wb = 1 - wa;
      vel[a * 3] += dx * k * wa; vel[a * 3 + 1] += dy * k * wa; vel[a * 3 + 2] += dz * k * wa;
      vel[b * 3] -= dx * k * wb; vel[b * 3 + 1] -= dy * k * wb; vel[b * 3 + 2] -= dz * k * wb;
    }
    // Gravity to centre keeps islands on screen
    for (let i = 0; i < n; i++) {
      for (let c = 0; c < 3; c++) {
        vel[i * 3 + c] -= pos[i * 3 + c] * 0.012 * alpha;
        vel[i * 3 + c] *= 0.6;
        pos[i * 3 + c] += vel[i * 3 + c];
      }
      if (dims === 2) pos[i * 3 + 2] = 0;
    }
  }
  for (let i = 0; i < n; i++) {
    nodes[i].x = pos[i * 3]; nodes[i].y = pos[i * 3 + 1]; nodes[i].z = pos[i * 3 + 2];
    nodes[i].r = radiusOf(i);
  }
  return nodes;
}

/** Bounding box of laid-out nodes, padded. */
export function bounds(nodes, pad = 40) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of nodes) {
    minX = Math.min(minX, n.x - n.r); minY = Math.min(minY, n.y - n.r);
    maxX = Math.max(maxX, n.x + n.r); maxY = Math.max(maxY, n.y + n.r);
  }
  if (!Number.isFinite(minX)) return { x: -100, y: -100, w: 200, h: 200 };
  return { x: minX - pad, y: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 };
}
