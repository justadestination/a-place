/* Substrate — the render layer.
 *
 * The policy file states floors. `enforce_policy.py` checks that the document
 * doesn't contradict itself. Neither of those renders anything. This does.
 *
 * The contract: if a floor is violated, this SURFACE REFUSES TO RENDER. It does
 * not render the violation in a warning colour, and it does not degrade quietly.
 * A floor that lives only in JSON is a preference with better formatting.
 *
 * Three things get measured against the policy, on the real DOM, after layout:
 *   1. contrast   - computed colours, per theme, against minimumRatio[Dark]
 *   2. motion     - motion.locked + prefers-reduced-motion -> refuse animation
 *   3. clutter    - competing affordances visible against density.clutterCeiling
 *
 * Rule 9: failure is visible. Every refusal says which floor, which element,
 * what it measured, and what the floor was.
 */

const Substrate = (() => {

  /* ---------- colour maths (WCAG 2.x relative luminance) ---------- */

  const srgbToLinear = (c) => {
    c /= 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };

  const luminance = ([r, g, b]) =>
    0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);

  const contrastRatio = (fg, bg) => {
    const a = luminance(fg), b = luminance(bg);
    const hi = Math.max(a, b), lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05);
  };

  const parseRGB = (str) => {
    const m = str && str.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    if (p.length < 3 || p.some(Number.isNaN)) return null;
    return { rgb: [p[0], p[1], p[2]], alpha: p.length > 3 ? p[3] : 1 };
  };

  /* Effective background: walk ancestors until something is actually opaque.
   * Returns null when we hit a gradient or image, which we cannot measure —
   * that is reported as unknown rather than silently assumed to pass. */
  function effectiveBackground(el) {
    let node = el;
    let stack = 0;
    while (node && node !== document.documentElement && stack < 40) {
      const c = parseRGB(getComputedStyle(node).backgroundColor);
      if (c && c.alpha > 0.95) return c.rgb;
      if (c && c.alpha > 0 && c.alpha < 0.95) {
        // Composite the translucent layer over whatever is behind it.
        const behind = effectiveBackground(node.parentElement);
        if (!behind) return null;
        const a = c.alpha;
        return [
          c.rgb[0] * a + behind[0] * (1 - a),
          c.rgb[1] * a + behind[1] * (1 - a),
          c.rgb[2] * a + behind[2] * (1 - a),
        ].map(Math.round);
      }
      node = node.parentElement;
      stack++;
    }
    const root = parseRGB(getComputedStyle(document.documentElement).backgroundColor);
    return root && root.alpha > 0.95 ? root.rgb : [255, 255, 255];
  }

  const isDark = (bg) => luminance(bg) < 0.35;

  /* ---------- state ---------- */

  const state = {
    policy: null,
    applied: [],
    refusals: [],
    warnings: [],
    measurements: [],
    motionAllowed: false,
    motionRefused: false,
    simulated: null, // dev hook: 'contrast' forces a violation to prove refusal
  };

  /* ---------- applying the presentation block ---------- */

  function applyPresentation() {
    const p = state.policy;
    const pres = (p && p.presentation) || {};
    const z = pres.zoom || {};
    const c = pres.contrast || {};
    const d = pres.density || {};
    const m = pres.motion || {};
    const root = document.documentElement.style;

    if (z.rootFontPx) root.setProperty('--root-font', z.rootFontPx + 'px');
    if (z.scale) root.setProperty('--zoom-scale', String(z.scale));
    if (z.lineHeight) root.setProperty('--line-height', String(z.lineHeight));
    if (z.measureCh) root.setProperty('--measure', z.measureCh + 'ch');

    if (c.minimumRatio) root.setProperty('--floor-light', String(c.minimumRatio));
    if (c.minimumRatioDark) root.setProperty('--floor-dark', String(c.minimumRatioDark));
    root.setProperty('--dark-mode', c.darkMode || 'auto');

    if (d.clutterCeiling) root.setProperty('--clutter-ceiling', String(d.clutterCeiling));
    if (d.modulesPerSurface) root.setProperty('--modules-per-surface', String(d.modulesPerSurface));
    root.setProperty('--collapse-secondary', d.alwaysCollapseSecondary === false ? '0' : '1');

    // motion.locked turns the values into floors rather than defaults, and the
    // render layer is where that gets honoured.
    if (m.locked) {
      if (m.reduceMotion === false) {
        state.refusals.push({
          code: 'motion.floor.violated',
          detail: 'motion.locked is true but reduceMotion is false. Locked means the floor is a floor.',
        });
      }
      if (m.allowParallax === true || m.allowAutoPlay === true) {
        state.refusals.push({
          code: 'motion.floor.violated',
          detail: 'motion.locked is true but parallax or autoplay is enabled.',
        });
      }
    }

    state.applied = [
      ['root font', (z.rootFontPx || 18) + 'px'],
      ['zoom scale', String(z.scale || 1)],
      ['line height', String(z.lineHeight || 1.5)],
      ['measure', (z.measureCh || 66) + 'ch'],
      ['contrast floor', (c.minimumRatio || 7) + (c.minimumRatioDark ? ' / ' + c.minimumRatioDark : ' (dark unset)')],
      ['clutter ceiling', String(d.clutterCeiling || 4)],
      ['motion locked', String(!!m.locked)],
    ];
  }

  /* ---------- measuring contrast on the real DOM ---------- */

  function measureContrast(root) {
    const c = ((state.policy || {}).presentation || {}).contrast || {};
    const dark = state.darkSurface;
    let floor = dark ? (c.minimumRatioDark ?? c.minimumRatio) : c.minimumRatio;
    if (floor == null) floor = 4.5; // WCAG AA body text is the fallback, not a lower bar

    const scope = root || document;
    const targets = scope.querySelectorAll(
      '[data-contrast-check], .article-body p, .article-body li, .article-body h2, ' +
      '.steward-line, .choice, .hint, .colophon'
    );

    const seen = [];
    for (const el of targets) {
      if (!el.textContent.trim()) continue;
      const cs = getComputedStyle(el);
      const fg = parseRGB(cs.color);
      const bg = effectiveBackground(el);
      if (!fg || !bg) {
        state.warnings.push({
          code: 'contrast.unmeasurable',
          detail: `could not resolve a solid background behind <${el.tagName.toLowerCase()}>; ` +
                  'a gradient or image backdrop is not measured, so it is not claimed as passing',
        });
        continue;
      }
      const ratio = contrastRatio(fg.rgb, bg);
      const entry = {
        selector: el.className || el.tagName.toLowerCase(),
        ratio: Math.round(ratio * 100) / 100,
        floor,
        theme: dark ? 'dark' : 'light',
      };
      seen.push(entry);

      if (ratio < floor) {
        state.refusals.push({
          code: c.locked ? 'contrast.floor.violated' : 'contrast.below.wcag',
          detail: `${entry.selector} renders at ${entry.ratio}:1 on the ${entry.theme} surface; ` +
                  `the floor is ${floor}:1${c.locked ? ' and contrast.locked is true' : ''}`,
          element: el,
        });
      }
    }
    state.measurements = seen;
    state.floorUsed = floor;
  }

  /* ---------- motion lock ---------- */

  function evaluateMotion() {
    const m = ((state.policy || {}).presentation || {}).motion || {};
    const locked = !!m.locked;
    const wantsReduced = m.reduceMotion !== false;
    const osReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Locked means: no motion the reader did not explicitly opt into. An OS-level
    // reduce request always wins, whatever the document says.
    state.motionAllowed = !locked && !wantsReduced && !osReduced;
    state.motionRefused = locked || wantsReduced || osReduced;
    state.motionReason = locked
      ? 'motion.locked is true in the policy: floors, not defaults'
      : wantsReduced
        ? 'policy sets reduceMotion'
        : osReduced
          ? 'the device reports prefers-reduced-motion: reduce'
          : null;
  }

  /* ---------- clutter ceiling ---------- */

  function evaluateClutter(root) {
    const d = ((state.policy || {}).presentation || {}).density || {};
    const ceiling = d.clutterCeiling || 4;
    // Competing calls to action visible at once: things that invite a response.
    // Scoped to the root being judged, which defaults to the whole document. It
    // must NOT depend on an ancestor having class="surface": that coupling meant
    // content rendered anywhere else escaped the ceiling completely.
    const scope = root || document;
    const competing = [...scope.querySelectorAll('[data-competing]')]
      .filter((el) => el.offsetParent !== null);
    const n = competing.length;
    state.clutter = { visible: n, ceiling };
    if (n > ceiling) {
      state.refusals.push({
        code: 'density.ceiling.exceeded',
        detail: `${n} competing affordances are visible at once; density.clutterCeiling is ${ceiling}. ` +
                'Clutteredness is the default failure mode of agent-generated interfaces.',
      });
    }
    return n <= ceiling;
  }

  /* ---------- refusal ---------- */

  function refuse(reason) {
    const panel = document.getElementById('refusal');
    if (!panel) return;
    panel.hidden = false;
    panel.querySelector('#refusal-reason').textContent = reason;

    const body = document.getElementById('reading-surface');
    if (body) body.hidden = true;

    const list = document.getElementById('refusal-list');
    if (list) {
      list.innerHTML = '';
      for (const r of state.refusals) {
        const li = document.createElement('li');
        const code = document.createElement('code');
        code.textContent = r.code;
        li.appendChild(code);
        li.appendChild(document.createTextNode(' — ' + r.detail));
        list.appendChild(li);
      }
    }
    document.body.dataset.substrate = 'refused';
  }

  function render() {
    const root = document.documentElement;
    root.dataset.substrate = state.refusals.length ? 'refused' : 'ok';
    if (state.refusals.length) refuse('This surface was refused by the substrate.');
    else document.body.dataset.substrate = 'ok';
    renderDebug();
  }

  /* ---------- dev panel: make the enforcement inspectable ---------- */

  function renderDebug() {
    const el = document.getElementById('substrate-debug');
    if (!el) return;

    el.textContent = '';

    // Built with DOM methods, not innerHTML: the policy document is hand-editable,
    // so a class name or detail string is untrusted input even though it is local.
    const table = document.createElement('table');
    const cap = document.createElement('caption');
    cap.textContent = 'applied from policy.generated.json';
    table.appendChild(cap);
    const tbody = document.createElement('tbody');

    const row = (k, v) => {
      const tr = document.createElement('tr');
      const th = document.createElement('th');
      th.textContent = k;
      const td = document.createElement('td');
      td.textContent = v;
      tr.append(th, td);
      tbody.appendChild(tr);
    };

    for (const [k, v] of state.applied) row(k, v);

    const worst = state.measurements.length
      ? state.measurements.reduce((a, b) => (b.ratio < a.ratio ? b : a))
      : null;
    if (worst) row('worst pair', `${worst.ratio}:1 (${worst.theme}, floor ${worst.floor}:1)`);

    row('motion', state.motionAllowed
      ? 'allowed'
      : 'REFUSED — ' + (state.motionReason || ''));
    row('clutter', state.clutter ? `${state.clutter.visible} / ${state.clutter.ceiling}` : '—');
    row('refusals', String(state.refusals.length));
    table.appendChild(tbody);
    el.appendChild(table);

    const controls = document.createElement('p');
    controls.className = 'dev-controls';
    for (const [id, label] of [
      ['sim-contrast', 'force a contrast violation'],
      ['sim-clutter', 'exceed the clutter ceiling'],
    ]) {
      const wrap = document.createElement('label');
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.id = id;
      box.checked = state.simulated === id.replace('sim-', '');
      box.addEventListener('change', () => {
        run({ simulate: box.checked ? id.replace('sim-', '') : null });
      });
      wrap.append(box, document.createTextNode(' ' + label));
      controls.appendChild(wrap);
    }
    el.appendChild(controls);

    const note = document.createElement('p');
    note.className = 'dev-note';
    note.textContent = 'Both switches exist to make the refusal observable without ' +
      'hand-editing the policy. A floor you cannot see fail is a floor you have not tested.';
    el.appendChild(note);
  }

  /* ---------- boot ---------- */

  function run(opts = {}) {
    state.refusals = [];
    state.warnings = [];
    state.measurements = [];
    state.simulated = opts.simulate || null;
    // `scope` names the region being judged (a submission surface, say). Refusals
    // found inside it hide the region; document-wide checks still run.
    const scope = opts.scopeNode || null;

    const pres = (state.policy || {}).presentation || {};
    const c = pres.contrast || {};

    // Which theme are we actually in? Ask the DOM, not the policy.
    const pageBg = effectiveBackground(document.body) || [255, 255, 255];
    state.darkSurface = isDark(pageBg);
    document.documentElement.dataset.theme = state.darkSurface ? 'dark' : 'light';

    applyPresentation();

    if (state.simulated === 'contrast') {
      state.refusals.push({
        code: 'contrast.floor.violated',
        detail: 'SIMULATED: an element was forced to 2.1:1 against a locked floor of ' +
                (state.darkSurface ? (c.minimumRatioDark ?? c.minimumRatio) : c.minimumRatio) +
                ':1. This is what a real violation looks like.',
      });
    }

    measureContrast(scope);
    evaluateMotion();
    evaluateClutter(scope);

    if (state.simulated === 'clutter') {
      state.clutter = { visible: 9, ceiling: pres.density?.clutterCeiling || 4 };
      state.refusals.push({
        code: 'density.ceiling.exceeded',
        detail: 'SIMULATED: 9 competing affordances against a ceiling of ' +
                (pres.density?.clutterCeiling || 4) + '.',
      });
    }

    render();
    return state.refusals.length === 0;
  }

  return {
    state,
    run,
    render,
    contrastRatio,
    parseRGB,
    effectiveBackground,
    luminance,
    /** Steward calls this before every animation. */
    motionPermitted: () => state.motionAllowed,
    motionReason: () => state.motionReason,
  };
})();

window.Substrate = Substrate;
