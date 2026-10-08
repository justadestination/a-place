/* The steward.
 *
 * Speaks in the article's own voice during calibration, then steps into its own
 * register and stays there. One transition, both legible.
 *
 * THE INVARIANT THIS FILE EXISTS TO PROTECT
 * ------------------------------------------
 * A recorded preference is never terminal. The steward records what happened,
 * says plainly what it recorded, and leaves a live control in the document so
 * the reader can change it from where they noticed it. Corrections append to
 * the log and permanently outrank what they correct — they do not erase it.
 *
 * There is no "never asks again". What there is: the steward does not re-ask
 * unprompted, and can always be asked. Those are different things, and the
 * second one is the whole point.
 *
 * Silence is assent, but only because the window has a defined end: it closes
 * when the reader's position advances past the paragraph the question was
 * raised at. Without that boundary a stray tap months later would resolve the
 * question permanently — which is precisely why the answer must be revisable.
 *
 * Everything motion-related goes through Substrate.motionPermitted(). The
 * policy file says no motion; the steward does not get an exemption for being
 * charming.
 */

const Steward = (() => {

  /* ---------- phase model ----------
   * dormant -> morphing -> speaking -> asking -> confirming -> registered
   * `registered` is a resting state, not a terminal one. From it the reader can
   * re-ask (channel: 'reask') or revoke entirely (channel: 'revoke').
   */
  const state = {
    register: 'article',   // 'article' -> 'steward', once, at the moment of registering
    phase: 'dormant',
    answered: null,        // null | 'yes' | 'no'   — the LAST answer (drives morphing)
    currentAnswered: false,// whether THIS question has been answered yet
    inReask: false,
    askAnchor: null,
    askClosed: false,
    tapCount: 0,
    tapTimer: null,
    preference: null,      // the durable record, in words
    channel: null,         // how they actually answered, this time
    morphsPerformed: 0,
    listenerInstalled: false,
    reaskCount: 0,
    confirmed: false,
    inferenceLog: [],      // shape-compatible with policy inference.inferred
  };

  const WORDS = {
    ask: "Hi, I'm the steward here. Is everything to your liking? " +
         "Tap once for a no — or just keep reading.",
    no: "Understood. I'll stop moving things about.",
    yes: "Good. Enjoy.",
    confirm: (p) => `Noted: ${p}. Tap this line to change it.`,
    revoke: "Nothing written down. Nothing to undo.",
    askAgain: "Ask me again.",
  };

  /* ---------- the two voices ---------- */

  const ARTICLE_VOICE = {
    weight: '450',
    colour: 'var(--sheet, var(--ink))',
    note: "the article's own voice — used during calibration, so the reader learns " +
          "the steward's rhythm in a register they already chose",
  };

  const STEWARD_VOICE = {
    weight: '300',
    colour: 'var(--steward-ink)',
    note: "its own register — lighter weight and a distinct hue, permanently",
  };

  function applyRegister(name) {
    const v = name === 'steward' ? STEWARD_VOICE : ARTICLE_VOICE;
    const el = document.getElementById('steward-line');
    if (el) {
      el.style.fontWeight = v.weight;
      el.style.color = v.colour;
    }
    document.documentElement.dataset.stewardRegister = name;
    state.register = name;
    const badge = document.getElementById('steward-register');
    if (badge) badge.textContent =
      name === 'steward' ? 'steward' : 'article (calibrating)';
  }

  /* ---------- reading position ---------- */

  const reading = {
    position() {
      const paras = [...document.querySelectorAll('.article-body > *')];
      const anchor = window.innerHeight * 0.33;
      let best = 0;
      for (let i = 0; i < paras.length; i++) {
        const r = paras[i].getBoundingClientRect();
        if (r.top <= anchor && r.bottom >= 0) best = i;
      }
      return best;
    },
  };

  /* ---------- the morph ----------
   *
   * The text in the upcoming paragraph drifts a little, so you might think you
   * are tired. Gated twice: the substrate's motion verdict (policy + OS), and
   * the reader's own recorded answer. If they objected, this never runs again
   * until they say otherwise.
   */

  function morphAllowed() {
    if (state.answered === 'no') return false;
    return Substrate.motionPermitted();
  }

  function morph(target, { amplitude = 2.2, duration = 900 } = {}) {
    if (!morphAllowed()) return false;

    state.phase = 'morphing';
    const start = performance.now();

    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const e = 0.5 - Math.cos(t * Math.PI) / 2;   // easeInOutSine: settle, don't snap
      target.style.transform =
        `translate3d(${(amplitude * e).toFixed(3)}px, ${(-amplitude * 0.6 * e).toFixed(3)}px, 0)`;
      target.style.letterSpacing = `${(0.012 * e).toFixed(4)}em`;

      if (t < 1) {
        requestAnimationFrame(tick);
      } else {
        // settle back: the drift was a question, not an event
        target.style.transform = '';
        target.style.letterSpacing = '';
        state.phase = 'speaking';
        state.morphsPerformed++;
        document.documentElement.dataset.stewardMorphs = String(state.morphsPerformed);
      }
    };
    requestAnimationFrame(tick);
    return true;
  }

  /* ---------- speaking ---------- */

  let liveRegion;
  function announce(text) {
    if (!liveRegion) liveRegion = document.getElementById('steward-live');
    if (liveRegion) liveRegion.textContent = text;
  }

  function say(text, { ask = false, durable = false } = {}) {
    const el = document.getElementById('steward-line');
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    el.dataset.contrastCheck = '';
    // A durable line is a control, not a message: it stays tappable.
    el.classList.toggle('is-control', durable);
    el.setAttribute('data-durable', durable ? 'true' : 'false');
    state.phase = ask ? 'asking' : 'speaking';
    if (ask) {
      state.askAnchor = reading.position();
      state.askClosed = false;
      state.currentAnswered = false;
      document.documentElement.dataset.stewardPhase = 'asking';
    }
    announce(text);
  }

  function note(text, { asControl = false } = {}) {
    const el = document.getElementById('steward-note');
    if (!el) return;
    el.hidden = false;
    el.textContent = text;
    el.dataset.contrastCheck = '';
    el.classList.toggle('is-control', asControl);
  }

  /* ---------- the smile ----------
   *
   * No face. The middle of the sentence rides down onto a shallow arc and the
   * colour lifts a shade, which drags the whole sentence into a curve. That is
   * the entire effect and it has to stay this small — any bigger and it stops
   * being a smile and becomes a performance.
   */

  function parseHex(hex) {
    const m = (hex || '').match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i);
    if (!m) return null;
    let h = m[1];
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  }

  function blend(fgHex, bgCss, amount) {
    const fg = parseHex(fgHex);
    const bg = Substrate.parseRGB(bgCss);
    if (!fg || !bg) return fgHex;
    return `rgb(${fg.map((v, i) => Math.round(v + (bg.rgb[i] - v) * amount)).join(',')})`;
  }

  function smile(text) {
    const host = document.getElementById('steward-smile');
    if (!host) return false;

    // The policy wins over the effect. A reader who cannot have motion gets the
    // acknowledgement without the curve.
    if (!Substrate.motionPermitted()) {
      host.hidden = false;
      host.textContent = text;
      host.dataset.motion = 'refused';
      announce(text);
      return false;
    }

    const W = 640, H = 92;
    const depth = 13;   // how far the middle dips, in user units
    const NS = 'http://www.w3.org/2000/svg';

    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('class', 'smile-svg');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', text);

    const defs = document.createElementNS(NS, 'defs');
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('id', 'smile-arc');
    path.setAttribute('fill', 'none');
    defs.appendChild(path);
    svg.appendChild(defs);

    const textEl = document.createElementNS(NS, 'text');
    textEl.setAttribute('class', 'smile-text');
    const tp = document.createElementNS(NS, 'textPath');
    tp.setAttribute('href', '#smile-arc');
    tp.setAttribute('startOffset', '50%');
    tp.setAttribute('text-anchor', 'middle');
    tp.textContent = text;
    textEl.appendChild(tp);
    svg.appendChild(textEl);

    host.textContent = '';
    host.hidden = false;
    host.appendChild(svg);
    announce(text);

    const start = performance.now();
    const dur = 1100;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / dur);
      const e = 0.5 - Math.cos(t * Math.PI) / 2;
      path.setAttribute('d', `M0,${H / 2} Q${W / 2},${H / 2 + depth * e} ${W},${H / 2}`);
      const lift = Math.sin(t * Math.PI);
      const ink = getComputedStyle(document.documentElement)
        .getPropertyValue('--steward-ink').trim();
      const bg = getComputedStyle(document.body).backgroundColor;
      textEl.style.fill = Substrate.parseRGB(bg) ? blend(ink, bg, lift * 0.35) : ink;
      if (t < 1) requestAnimationFrame(tick);
      else host.dataset.motion = 'settled';
    };
    requestAnimationFrame(tick);
    state.phase = 'smiling';
    return true;
  }

  /* ---------- acknowledgement ----------
   * The success state is silence, so it needs one visible marker that the
   * message landed. Otherwise a reader who objected reads the same paragraph
   * twice wondering whether they were ignored. */

  function acknowledge() {
    const tick = document.getElementById('steward-ack');
    if (!tick) return;
    tick.hidden = false;
    tick.textContent = '✓';
    tick.dataset.contrastCheck = '';
  }

  /* ---------- the question, and the window that closes it ---------- */

  function installListener() {
    if (state.listenerInstalled) return;
    state.listenerInstalled = true;

    document.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.dev-controls, #substrate-debug')) return;

      // Tapping the durable line is a correction request, never a "no".
      if (e.target.closest('#steward-line.is-control')) { reask(); return; }
      if (e.target.closest('#steward-revoke')) { revoke(); return; }
      if (e.target.closest('#steward-note.is-control')) { reask(); return; }

      if (state.phase !== 'asking') { dismiss(); return; }

      state.tapCount++;
      clearTimeout(state.tapTimer);
      // 400ms, not an instant read. A deliberate single tap is unambiguous;
      // two taps separated by hesitation is not, so we wait before deciding.
      state.tapTimer = setTimeout(() => {
        const n = state.tapCount;
        state.tapCount = 0;
        if (n === 1) {
          resolve('no', 'tap');
        } else if (n >= 2) {
          // Two taps was the old "no" gesture, and it collided with
          // double-tap-to-zoom. Ambiguous on purpose now: taken as no, but
          // flagged and correctable — because this is exactly the misfire that
          // makes confirmation mandatory rather than optional.
          resolve('no', 'tap');
          note('ambiguous double-tap — recorded as no, but it may have been a ' +
               'zoom attempt. Tap this to ask again.', { asControl: true });
        }
      }, 400);
    }, { capture: true });

    // The window closes on reading-position advance. This is what makes silence
    // mean yes rather than merely mean nothing happened.
    window.addEventListener('scroll', () => {
      if (state.phase !== 'asking' || state.askClosed) return;
      if (reading.position() > state.askAnchor) {
        state.askClosed = true;
        resolve('yes', 'read-on');
      }
    }, { passive: true });

    // Keyboard equivalent. The tap affordance is not the only way in.
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && state.phase === 'asking') resolve('no', 'escape');
    });
  }

  /* ---------- resolution, confirmation, and the log ---------- */

  function describePreference(answer) {
    return answer === 'no'
      ? 'tap once to object; no animating text'
      : 'tap once to object; animation welcome until you say otherwise';
  }

  function evidenceFor(answer, channel, isReask) {
    const at = state.askAnchor != null ? `asked at paragraph ${state.askAnchor}` : 'asked';
    const how = {
      tap: 'reader tapped once inside the 400ms window',
      'read-on': 'reader advanced past the anchor paragraph without tapping',
      escape: 'reader pressed Escape inside the window',
    }[channel] || 'reader answered';

    // A correction says both things: the gesture they actually made, AND that
    // they had to be asked again to make it. Collapsing the two loses the
    // evidence that makes the correction checkable.
    return [`steward ${at}`,
            isReask
              ? `reader reopened the question (ask #${state.reaskCount}) and answered again — ${how}`
              : how];
  }

  function resolve(answer, channel = 'tap') {
    // Guard on THIS question, not on the last answer. A re-ask opens a new
    // question, so it must be answerable — otherwise the steward records a
    // preference and can never be corrected, which is the failure this whole
    // correction path exists to prevent.
    if (state.currentAnswered) return;

    const isReask = state.inReask;
    state.currentAnswered = true;
    state.answered = answer;
    state.channel = channel;          // how they answered: tap | read-on | escape
    state.askClosed = true;
    state.confirmed = false;
    state.inReask = false;

    const pref = describePreference(answer);
    state.preference = pref;

    say(answer === 'no' ? WORDS.no : WORDS.yes);

    // CONFIRMATION. Not a nicety — it is the correction mechanism, and it names
    // exactly what was written so it can be checked.
    setTimeout(() => {
      say(WORDS.confirm(pref), { durable: true });
      state.phase = 'confirming';
      state.confirmed = true;
      document.documentElement.dataset.stewardPhase = 'registered';
      showRevoke(true);
      acknowledge();
      smile(answer === 'no' ? "I'll be quiet, then." : "Glad you're alright.");
    }, 850);

    // The transition into the steward's own register is driven by HAVING
    // ANSWERED, not by a timer. A reader who never got asked stays in the
    // article's voice — there is no transition they did not consent to.
    if (state.register === 'article') {
      setTimeout(() => applyRegister('steward'), 2100);
    }

    record(answer, state.channel, pref);
    Substrate.run();
  }

  /* Every recorded inference, corrections included. Corrections outrank what
   * they correct and are never removed — a log you can edit into agreeing with
   * you is not a log. */
  function record(answer, channel, pref) {
    const isCorrection = state.inferenceLog.length > 0;
    const entry = {
      about: 'how this reader wants to be spoken to',
      conclusion: pref,
      // They said it deliberately, so the first reading is near-certain. A
      // correction resets lower on purpose: the agent no longer has grounds to
      // be confident, and enforce_policy.py refuses high confidence on a
      // contradicted entry anyway.
      confidence: isCorrection ? 0.6 : 0.95,
      evidence: evidenceFor(answer, channel, isCorrection),
      contradictedBy: null,
    };

    if (isCorrection) {
      const prev = state.inferenceLog[state.inferenceLog.length - 1];
      prev.contradictedBy = `reader corrected this on ask #${state.reaskCount}`;
      // The correction outranks: drop confidence rather than delete the entry.
      prev.confidence = Math.min(prev.confidence, 0.5);
      prev.supersededBy = entry.evidence[entry.evidence.length - 1];
    }

    state.inferenceLog.push(entry);
    renderLog();
    persist();
  }

  function renderLog() {
    const log = document.getElementById('inference-log');
    if (!log) return;
    log.textContent = '';
    state.inferenceLog.forEach((e, i) => {
      const li = document.createElement('li');
      li.className = e.contradictedBy ? 'is-corrected' : 'is-current';

      const head = document.createElement('strong');
      head.textContent = `${i + 1}. ${e.about}: `;
      li.append(head, document.createTextNode(e.conclusion));

      const meta = document.createElement('small');
      const parts = [`confidence ${e.confidence}`, ...e.evidence];
      if (e.contradictedBy) parts.push(`corrected — ${e.contradictedBy}`);
      meta.textContent = parts.join(' · ');
      li.appendChild(meta);
      log.appendChild(li);
    });
  }

  function persist() {
    window.__stewardPreference = state.inferenceLog[state.inferenceLog.length - 1] || null;
    window.__stewardLog = state.inferenceLog;
    try {
      localStorage.setItem('steward.inference-log', JSON.stringify(state.inferenceLog));
    } catch (e) { /* private mode: the on-page log is still readable and exportable */ }
  }

  /* ---------- re-ask, and revoke ---------- */

  /* Re-ask: the steward asks again, from where the reader noticed. Same
   * question, same window rules. Nothing is recorded until they answer. */
  function reask() {
    if (state.phase === 'asking') return;
    state.reaskCount++;
    state.askAnchor = reading.position();
    state.askClosed = false;
    state.currentAnswered = false;   // this question is open
    state.inReask = true;            // so the log records it as a correction
    state.confirmed = false;
    showRevoke(false);
    const noteEl = document.getElementById('steward-note');
    if (noteEl) { noteEl.hidden = true; noteEl.textContent = ''; noteEl.classList.remove('is-control'); }

    say(WORDS.ask, { ask: true });
    const badge = document.getElementById('steward-register');
    if (badge) badge.textContent = 'steward (re-asking)';
  }

  /* Revoke: erase the record without recording a correction, for the reader who
   * wants no model of them at all. Distinct from changing the answer. */
  function revoke() {
    state.inferenceLog = [];
    state.preference = null;
    state.answered = null;
    state.currentAnswered = false;
    state.inReask = false;
    state.confirmed = false;
    state.channel = null;
    state.reaskCount = 0;
    window.__stewardPreference = null;
    window.__stewardLog = [];
    try { localStorage.removeItem('steward.inference-log'); } catch (e) {}

    renderLog();
    showRevoke(false);
    say(WORDS.revoke, { durable: false });
    note('Nothing about how you like to be spoken to is stored.');
    const badge = document.getElementById('steward-register');
    if (badge) badge.textContent = 'steward (nothing recorded)';
    Substrate.run();
  }

  function showRevoke(on) {
    const b = document.getElementById('steward-revoke');
    if (b) {
      b.hidden = !on;
      b.dataset.contrastCheck = '';
    }
  }

  function dismiss() {
    if (state.phase === 'dormant') return;
    if (state.phase === 'registered' || state.confirmed) return;  // the durable line stays
    state.phase = 'dormant';
    const line = document.getElementById('steward-line');
    const smileHost = document.getElementById('steward-smile');
    if (line) { line.hidden = true; line.textContent = ''; }
    if (smileHost) { smileHost.hidden = true; smileHost.textContent = ''; }
    document.documentElement.dataset.stewardPhase = 'dormant';
  }

  /* ---------- sequence ---------- */

  function run() {
    applyRegister('article');
    installListener();

    const paras = [...document.querySelectorAll('.article-body > p')];
    const target = paras[Math.min(3, paras.length - 1)] ||
                   document.querySelector('.place') ||
                   document.querySelector('#app p') ||
                   document.querySelector('#app');
    if (!target) return;

    // It arrives while you are reading, not on load — after a couple of minutes,
    // at a natural break. The long delay is the point: this is not a dialog.
    setTimeout(() => {
      const morphed = morph(target);
      if (!morphed) {
        // Motion refused. Say it anyway, in the article's voice, without drift.
        say(WORDS.ask, { ask: true });
      } else {
        setTimeout(() => say(WORDS.ask, { ask: true }), 1200);
      }
      Substrate.run();
    }, 8000);
  }

  return {
    state,
    run,
    say,
    note,
    smile,
    morph,
    resolve,
    reask,
    revoke,
    reading,
    applyRegister,
    morphAllowed,
    ARTICLE_VOICE,
    STEWARD_VOICE,
    WORDS,
  };
})();

window.Steward = Steward;
