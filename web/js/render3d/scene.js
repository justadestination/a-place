// 3D renderer (three.js). Draws the SAME scene models the DOM components use
// (weekScene from js/data/scene.js, graphScene(dims: 3) from js/data/graph.js),
// coloured from the SAME tokens via the theme API. See docs/ARCHITECTURE_2D_3D.md.
//
// Scene graph
//   Scene
//   ├─ HemisphereLight, DirectionalLight
//   └─ World (Group)                    one unit = one metre; placed in front of the viewer in AR
//      ├─ WeekLayer (Group)             visible in "week" mode
//      │  └─ DayPanel ×7 (Group)        on an arc around the viewer, userData {kind:"day", date}
//      │     ├─ DayHeader (Mesh)        canvas texture: weekday, date, count
//      │     └─ EventBillboard ×n       canvas texture: time, title, room, kind; userData {kind:"event", id}
//      └─ GraphLayer (Group)            visible in "graph" mode
//         ├─ Edges (LineSegments)
//         └─ NodeMesh ×n                shape per node type; userData {kind:"node", id}
//            └─ Label (Sprite)          notes only
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import Theme from "../core/theme.js";
import { typeOf } from "../data/graph.js";

const NOTE = new Set(["article", "review", "letter", "editorial"]);
const PANEL = { w: 0.9, headerH: 0.28, cardH: 0.3, gap: 0.04, radius: 3, arc: Math.PI * 0.62, y: 2.0 };
const PX = 640; // texture width in pixels

function tokens() {
  const r = k => Theme.read(k);
  return {
    bg: r("color.bg"), surface: r("color.surface"), sunken: r("color.surface-sunken"), text: r("color.text"),
    muted: r("color.text-muted"), border: r("color.border-strong"), accent: r("color.accent"), onAccent: r("color.on-accent"),
    selectedBg: r("color.selected-bg"), selectedText: r("color.selected-text"), edge: r("color.graph-edge"), edgeActive: r("color.graph-edge-active"),
    font: r("font.family.sans") || "system-ui, sans-serif",
    kind: tone => ({ bg: r(`color.kind-${tone}-bg`), fg: r(`color.kind-${tone}-fg`), mark: r(`color.kind-${tone}-mark`) }),
    node: type => r(`color.node-${type}`) || r("color.node-entity"),
  };
}

function roundRect(ctx, x, y, w, h, rad) {
  ctx.beginPath();
  ctx.moveTo(x + rad, y); ctx.arcTo(x + w, y, x + w, y + h, rad); ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad); ctx.arcTo(x, y, x + w, y, rad); ctx.closePath();
}

function wrap(ctx, text, maxW, maxLines) {
  const words = text.split(/\s+/); const lines = []; let line = "";
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
    if (lines.length === maxLines) break;
  }
  if (lines.length < maxLines && line) lines.push(line);
  if (lines.length === maxLines && words.join(" ").length > lines.join(" ").length) lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, "…");
  return lines;
}

function texture(draw, aspect) {
  const c = document.createElement("canvas");
  c.width = PX; c.height = Math.round(PX * aspect);
  const ctx = c.getContext("2d");
  draw(ctx, c.width, c.height);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function cardMesh(w, h, draw) {
  const tex = texture(draw, h / w);
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true });
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
}

const GEOMETRY = {
  circle: () => new THREE.SphereGeometry(0.07, 24, 16),
  diamond: () => new THREE.OctahedronGeometry(0.085),
  square: () => new THREE.BoxGeometry(0.11, 0.11, 0.11),
  triangle: () => new THREE.TetrahedronGeometry(0.1),
  hexagon: () => new THREE.CylinderGeometry(0.07, 0.07, 0.05, 6).rotateX(Math.PI / 2),
  ring: () => new THREE.TorusGeometry(0.06, 0.018, 10, 24),
};

export function createScene(container, { onSelect = () => {} } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.xr.enabled = true;
  container.append(renderer.domElement);
  renderer.domElement.setAttribute("aria-hidden", "true"); // the DOM list beside it is the accessible version

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 100);
  camera.position.set(0, 1.6, 1.6);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.35, -2.4);
  controls.enableDamping = !Theme.reducedMotion();
  controls.maxDistance = 8;
  controls.update();

  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(2, 4, 3); scene.add(sun);

  const world = new THREE.Group(); world.name = "World"; scene.add(world);
  const weekLayer = new THREE.Group(); weekLayer.name = "WeekLayer"; world.add(weekLayer);
  const graphLayer = new THREE.Group(); graphLayer.name = "GraphLayer"; world.add(graphLayer);
  const pickables = [];
  let data = { week: null, graph: null, selected: "" };
  let mode = "week";

  function clear(group) {
    group.traverse(o => { o.geometry?.dispose(); if (o.material) { o.material.map?.dispose(); o.material.dispose(); } });
    group.clear();
  }

  function buildWeek() {
    clear(weekLayer);
    const week = data.week; if (!week) return;
    const t = tokens();
    week.days.forEach((day, i) => {
      const panel = new THREE.Group();
      panel.name = `DayPanel ${day.date}`;
      panel.userData = { kind: "day", date: day.date };
      const a = -PANEL.arc / 2 + (PANEL.arc * i) / 6;
      panel.position.set(Math.sin(a) * PANEL.radius, PANEL.y, -Math.cos(a) * PANEL.radius);
      panel.lookAt(0, PANEL.y, 0);
      const selected = day.date === data.selected;
      const header = cardMesh(PANEL.w, PANEL.headerH, (ctx, w, h) => {
        roundRect(ctx, 4, 4, w - 8, h - 8, 28);
        ctx.fillStyle = selected ? t.selectedBg : t.surface; ctx.fill();
        ctx.lineWidth = 4; ctx.strokeStyle = t.border; ctx.stroke();
        ctx.fillStyle = selected ? t.selectedText : t.muted;
        ctx.font = `700 34px ${t.font}`; ctx.fillText(day.weekdayShort.toUpperCase(), 32, 64);
        ctx.fillStyle = selected ? t.selectedText : t.text;
        ctx.font = `800 84px ${t.font}`; ctx.fillText(String(day.day), 32, 150);
        ctx.font = `700 34px ${t.font}`; ctx.textAlign = "right";
        ctx.fillText(day.events.length ? `${day.events.length} show${day.events.length === 1 ? "" : "s"}` : "—", w - 32, 150);
      });
      header.name = "DayHeader"; header.userData = panel.userData; pickables.push(header);
      panel.add(header);
      day.events.slice(0, 5).forEach((ev, j) => {
        const k = t.kind(ev.tone);
        const card = cardMesh(PANEL.w, PANEL.cardH, (ctx, w, h) => {
          roundRect(ctx, 4, 4, w - 8, h - 8, 24);
          ctx.fillStyle = t.surface; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = t.border; ctx.stroke();
          ctx.fillStyle = t.text; ctx.font = `800 36px ${t.font}`; ctx.fillText(ev.start || "", 28, 56);
          ctx.font = `700 34px ${t.font}`;
          wrap(ctx, ev.title, w - 56, 2).forEach((ln, n) => ctx.fillText(ln, 28, 100 + n * 40));
          ctx.fillStyle = t.muted; ctx.font = `500 28px ${t.font}`; ctx.fillText((ev.venueName || "").slice(0, 34), 28, h - 26);
          ctx.font = `700 26px ${t.font}`; const label = ev.kindLabel; const lw = ctx.measureText(label).width + 32;
          roundRect(ctx, w - lw - 24, 22, lw, 44, 22); ctx.fillStyle = k.bg; ctx.fill();
          ctx.fillStyle = k.fg; ctx.fillText(label, w - lw - 8, 53);
        });
        card.name = "EventBillboard";
        card.position.y = -(PANEL.headerH / 2 + PANEL.gap + PANEL.cardH / 2 + j * (PANEL.cardH + PANEL.gap));
        card.userData = { kind: "event", id: ev.id };
        pickables.push(card);
        panel.add(card);
      });
      weekLayer.add(panel);
    });
  }

  function buildGraph() {
    clear(graphLayer);
    const g = data.graph; if (!g) return;
    const t = tokens();
    const scale = 0.004; // layout units -> metres
    const center = new THREE.Vector3(0, 1.6, -2.6);
    const pos = n => new THREE.Vector3(n.x * scale, -n.y * scale, n.z * scale).add(center);
    const pts = [];
    for (const e of g.edges) pts.push(pos(g.byId.get(e.source)), pos(g.byId.get(e.target)));
    const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: new THREE.Color(t.edge) }));
    lines.name = "Edges"; graphLayer.add(lines);
    for (const n of g.nodes) {
      const type = typeOf(n.type);
      const mat = n.type === "missing"
        ? new THREE.MeshStandardMaterial({ color: new THREE.Color(t.node(n.type)), wireframe: true })
        : new THREE.MeshStandardMaterial({ color: new THREE.Color(t.node(n.type)), roughness: 0.6 });
      const mesh = new THREE.Mesh(GEOMETRY[type.glyph](), mat);
      if (NOTE.has(n.type)) mesh.scale.setScalar(1.5);
      if (n.id === data.selected) mesh.scale.multiplyScalar(1.4);
      mesh.position.copy(pos(n));
      mesh.name = "NodeMesh"; mesh.userData = { kind: "node", id: n.id };
      pickables.push(mesh);
      if (NOTE.has(n.type) || n.id === data.selected) {
        const tex = texture((ctx, w, h) => {
          ctx.font = `800 44px ${t.font}`; ctx.textAlign = "center"; ctx.lineJoin = "round";
          ctx.lineWidth = 10; ctx.strokeStyle = t.sunken; ctx.strokeText(n.title.slice(0, 26), w / 2, h / 2 + 14);
          ctx.fillStyle = t.text; ctx.fillText(n.title.slice(0, 26), w / 2, h / 2 + 14);
        }, 0.16);
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
        sprite.scale.set(0.9, 0.144, 1); sprite.position.y = 0.16; sprite.name = "Label";
        mesh.add(sprite);
      }
      graphLayer.add(mesh);
    }
  }

  function rebuild() {
    pickables.length = 0;
    buildWeek(); buildGraph();
    weekLayer.visible = mode === "week"; graphLayer.visible = mode === "graph";
    render();
  }

  // Picking: pointer on screen, controller ray in XR.
  const ray = new THREE.Raycaster();
  const pick = () => {
    const hit = ray.intersectObjects(pickables.filter(o => o.parent && isVisible(o)), false)[0];
    if (hit) onSelect(hit.object.userData);
  };
  const isVisible = o => { for (let p = o; p; p = p.parent) if (!p.visible) return false; return true; };
  let down = null;
  renderer.domElement.addEventListener("pointerdown", e => { down = { x: e.clientX, y: e.clientY }; });
  renderer.domElement.addEventListener("pointerup", e => {
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
    const r = renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    pick();
  });
  const controller = renderer.xr.getController(0);
  controller.addEventListener("select", () => {
    const m = new THREE.Matrix4().extractRotation(controller.matrixWorld);
    ray.ray.origin.setFromMatrixPosition(controller.matrixWorld);
    ray.ray.direction.set(0, 0, -1).applyMatrix4(m);
    pick();
  });
  scene.add(controller);

  function resize() {
    const { width, height } = container.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height; camera.updateProjectionMatrix();
    render();
  }
  function render() { renderer.render(scene, camera); }
  // Render on demand outside XR (no idle GPU use); XR drives its own loop.
  controls.addEventListener("change", render);
  let damping = 0;
  renderer.domElement.addEventListener("pointermove", () => {
    if (!controls.enableDamping) return;
    cancelAnimationFrame(damping);
    const tick = () => { if (controls.update()) { render(); damping = requestAnimationFrame(tick); } };
    damping = requestAnimationFrame(tick);
  });
  new ResizeObserver(resize).observe(container);
  const onTheme = () => rebuild();
  document.addEventListener("nightcal:themechange", onTheme);

  async function startXR(kind = "immersive-ar", overlay) {
    const session = await navigator.xr.requestSession(kind, { optionalFeatures: ["local-floor", "dom-overlay"], domOverlay: overlay ? { root: overlay } : undefined });
    renderer.xr.setReferenceSpaceType("local-floor");
    await renderer.xr.setSession(session);
    // In AR the world sits in the room: half scale, a little in front of the viewer.
    world.scale.setScalar(kind === "immersive-ar" ? 0.5 : 1);
    world.position.set(0, kind === "immersive-ar" ? 0.4 : 0, kind === "immersive-ar" ? 0.6 : 0);
    renderer.setAnimationLoop(render);
    session.addEventListener("end", () => { renderer.setAnimationLoop(null); world.scale.setScalar(1); world.position.set(0, 0, 0); resize(); });
    return session;
  }

  return {
    scene, world,
    setWeek(week, selected) { data.week = week; if (selected) data.selected = selected; rebuild(); },
    setGraph(graph) { data.graph = graph; rebuild(); },
    select(id) { data.selected = id; rebuild(); },
    setMode(m) { mode = m; weekLayer.visible = m === "week"; graphLayer.visible = m === "graph"; render(); },
    startXR,
    dispose() { document.removeEventListener("nightcal:themechange", onTheme); clear(world); renderer.dispose(); renderer.domElement.remove(); },
  };
}

export async function xrSupport() {
  if (!navigator.xr) return { ar: false, vr: false };
  const [ar, vr] = await Promise.all(["immersive-ar", "immersive-vr"].map(m => navigator.xr.isSessionSupported(m).catch(() => false)));
  return { ar, vr };
}
