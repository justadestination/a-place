// The zine wall. A street facade along the left curb, in the road's own
// perspective, with the zine's latest pieces pasted up as posters that drift
// toward you as you stand on the road. A flat caption in the sky above it
// names the poster nearest you, readable even when the wall is steep.
//
// Article bodies are only ever read as text (DOMParser + textContent); no
// zine HTML is inserted into the page.

import { loadZine, typeOf } from "../js/data/graph.js";

const WRITTEN = new Set([
  "article", "review", "letter", "editorial", "stance", "dossier", "dossier-piece",
  "prediction", "cartoon-brief", "topic-overview", "topic-report",
]);

// One neon per kind of writing. Off the venue hues' job: these are paper, not places.
const INK = {
  article: "#FFB020",
  review: "#C8E04A",
  editorial: "#A56BFF",
  stance: "#FF6B5C",
  prediction: "#3FAE7A",
  "topic-overview": "#5A8BFF",
  "topic-report": "#5A8BFF",
};

const POSTER_W = 340; // px along the wall, before perspective
const GAP = 70;
const SECONDS_PER_POSTER = 9;
const MAX_POSTERS = 10;

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
};

const plain = text => String(text || "").replace(/[*_`#>]+/g, "").replace(/\s+/g, " ").trim();

/** First real paragraphs of a piece, as text, trimmed to about `limit` characters. */
function excerpt(node, limit = 260) {
  const doc = new DOMParser().parseFromString(String(node.html || ""), "text/html");
  const title = plain(node.title).toLowerCase();
  const parts = [...doc.querySelectorAll("p")]
    .map(p => plain(p.textContent))
    .filter(text => text.length > 40 && text.toLowerCase() !== title);
  const text = parts.join(" ") || plain(node.summary);
  return text.length > limit ? `${text.slice(0, limit).replace(/\s+\S*$/, "")}…` : text;
}

function byline(node) {
  const author = String(node.author || "").startsWith("a2a://") ? "a field agent" : plain(node.author);
  return [author, node.date].filter(Boolean).join(" · ");
}

/** Written, published pieces, newest first. */
export function zinePieces(zine, limit = MAX_POSTERS) {
  return (zine?.nodes || [])
    .filter(node => WRITTEN.has(node.type) && (node.status || "published") === "published" && (node.html || node.summary))
    .sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")) || a.title.localeCompare(b.title))
    .slice(0, limit)
    .map(node => ({
      id: node.id,
      type: node.type,
      kind: typeOf(node.type).label,
      title: plain(node.title),
      byline: byline(node),
      excerpt: excerpt(node),
      summary: plain(node.summary),
      ink: INK[node.type] || "#FFB020",
      href: `/zine/?node=${encodeURIComponent(node.id)}`,
    }));
}

function poster(piece) {
  // The wall is scenery (aria-hidden); the caption is the readable, focusable
  // link. Posters still take a mouse click straight into the zine.
  const link = el("a", "zine-poster");
  link.href = piece.href;
  link.tabIndex = -1;
  link.style.setProperty("--ink", piece.ink);
  link.append(
    el("span", "zine-poster__kind", piece.kind),
    el("span", "zine-poster__title", piece.title),
    el("span", "zine-poster__by", piece.byline),
    el("span", "zine-poster__text", piece.excerpt),
    el("span", "zine-poster__read", "Read in the zine →"),
  );
  return link;
}

/**
 * Mount the wall into `stage`. Returns nothing; it runs itself.
 * `motion` false keeps the posters still and turns the caption by timer.
 */
export async function mountZineWall(stage, { motion = true } = {}) {
  const pieces = zinePieces(await loadZine());
  if (!pieces.length) return;

  const scene = el("div", "road__zine");
  scene.setAttribute("aria-hidden", "true");
  const wall = el("div", "road__zine-wall");
  const track = el("div", "road__zine-track");
  // Two copies so the drift loops without a seam.
  track.append(...pieces.map(poster), ...pieces.map(poster));
  track.style.setProperty("--loop", `${pieces.length * (POSTER_W + GAP)}px`);
  track.style.setProperty("--loop-time", `${pieces.length * SECONDS_PER_POSTER}s`);
  track.style.setProperty("--poster-w", `${POSTER_W}px`);
  track.style.setProperty("--poster-gap", `${GAP}px`);
  wall.append(track);
  scene.append(wall);

  const caption = el("aside", "road__zine-caption");
  caption.setAttribute("aria-label", "From the zine");
  const eyebrow = el("p", "road__zine-eyebrow", "From the zine");
  const link = el("a", "road__zine-title");
  const by = el("p", "road__zine-by");
  const text = el("p", "road__zine-text");
  caption.append(eyebrow, link, by, text);

  stage.prepend(scene);
  stage.append(caption);
  if (!motion) track.dataset.still = "1";

  let shown = -1;
  const show = index => {
    const i = ((index % pieces.length) + pieces.length) % pieces.length;
    if (i === shown) return;
    shown = i;
    const piece = pieces[i];
    caption.style.setProperty("--ink", piece.ink);
    eyebrow.textContent = `From the zine · ${piece.kind}`;
    link.textContent = piece.title;
    link.href = piece.href;
    by.textContent = piece.byline;
    text.textContent = piece.summary || piece.excerpt;
  };

  // The nearest poster is whichever has drifted to the front of the wall.
  const period = SECONDS_PER_POSTER * 1000;
  let started = performance.now();
  const tick = () => {
    const anim = motion ? track.getAnimations()[0] : null;
    const ms = anim && anim.currentTime != null ? Number(anim.currentTime) : performance.now() - started;
    show(Math.floor(ms / period));
  };
  show(0);
  setInterval(tick, 500);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !motion) started = performance.now() - shown * period;
  });
}
