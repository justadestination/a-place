/* Gestures — shown, not just named.
 *
 * "Raise two fingers" is only intuitive if you already know it is counted that
 * way. Every channel the steward offers is drawn next to its label, so the
 * vocabulary is taught at the moment of need rather than assumed.
 *
 * Which channels are actually available depends on the device, and the steward
 * says so rather than offering gestures that will not work. Camera channels are
 * unavailable here: WebXR is not supported in Safari (MDN compat: false), there
 * is no ambient light API outside a Chrome flag, and the camera itself needs a
 * permission prompt the reader may decline. A control that might not work is not
 * a control.
 *
 * So: tap is the live channel. Nod and the two-finger raise are rendered as
 * demonstrations of the vocabulary — shown so the idea is legible — and labelled
 * honestly as not wired up in this build.
 */

const Gestures = (() => {

  const NS = 'http://www.w3.org/2000/svg';

  const CHANNELS = [
    {
      id: 'read-on',
      label: 'keep reading',
      meaning: 'yes',
      available: true,
      live: true,
      detail: 'The window closes when you move past this paragraph.',
    },
    {
      id: 'tap',
      label: 'tap once',
      meaning: 'no',
      available: true,
      live: true,
      detail: 'A single tap inside the window. Two taps are ambiguous — they ' +
              'collide with double-tap-to-zoom — so they are flagged and ' +
              'correctable rather than trusted.',
    },
    {
      id: 'nod',
      label: 'nod',
      meaning: 'yes',
      available: false,
      live: false,
      detail: 'Needs a camera. Not available in this build: no hand-tracking ' +
              'model is loaded, and the camera permission is the reader’s to decline.',
    },
    {
      id: 'two-finger',
      label: 'two fingers',
      meaning: 'no / changed your mind',
      available: false,
      live: false,
      detail: 'Needs a camera. The most expressive gesture here and the least ' +
              'available — which is why tap carries the same meaning.',
    },
  ];

  /* ---------- drawing ---------- */

  /* A hand, shown as a palm with fingers raised. Deliberately schematic: this is
   * a vocabulary key, not an illustration. */
  function hand({ raised = 0, w = 44, h = 56 } = {}) {
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 44 56');
    svg.setAttribute('class', 'gesture-icon');
    svg.setAttribute('aria-hidden', 'true');

    const mk = (tag, attrs) => {
      const el = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
      return el;
    };

    // palm
    svg.appendChild(mk('path', {
      d: 'M12 30 h20 v14 a6 6 0 0 1 -6 6 h-8 a6 6 0 0 1 -6 -6 z',
      fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6',
    }));

    // three resting fingers, always down
    for (const x of [24, 29, 34]) {
      svg.appendChild(mk('line', {
        x1: x, y1: 30, x2: x, y2: 42, stroke: 'currentColor', 'stroke-width': '1.6',
      }));
    }

    // raised fingers: index always, middle optional
    const up = [15, 20];
    for (let i = 0; i < raised; i++) {
      const x = up[i];
      svg.appendChild(mk('line', {
        x1: x, y1: 30, x2: x, y2: 12 - i * 2, stroke: 'currentColor', 'stroke-width': '1.8',
      }));
      svg.appendChild(mk('circle', { cx: x, cy: 10 - i * 2, r: 2.2, fill: 'currentColor' }));
    }
    return svg;
  }

  function tapIcon() {
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 44 56');
    svg.setAttribute('class', 'gesture-icon');
    svg.setAttribute('aria-hidden', 'true');
    const mk = (tag, attrs) => {
      const el = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
      return el;
    };
    svg.appendChild(mk('circle', {
      cx: 22, cy: 20, r: 7, fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6',
    }));
    svg.appendChild(mk('line', {
      x1: 22, y1: 27, x2: 22, y2: 40, stroke: 'currentColor', 'stroke-width': '1.8',
    }));
    svg.appendChild(mk('circle', { cx: 22, cy: 44, r: 2.4, fill: 'currentColor' }));
    svg.appendChild(mk('line', {
      x1: 6, y1: 52, x2: 38, y2: 52, stroke: 'currentColor', 'stroke-width': '1.4',
    }));
    return svg;
  }

  function iconFor(channel) {
    switch (channel.id) {
      case 'tap': return tapIcon();
      case 'read-on': {
        const svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('viewBox', '0 0 44 56');
        svg.setAttribute('class', 'gesture-icon');
        svg.setAttribute('aria-hidden', 'true');
        const mk = (tag, attrs) => {
          const el = document.createElementNS(NS, tag);
          for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
          return el;
        };
        svg.appendChild(mk('path', {
          d: 'M22 44 v-30 M22 44 l-7 -8 M22 44 l7 -8',
          fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8',
        }));
        svg.appendChild(mk('circle', { cx: 22, cy: 10, r: 2.4, fill: 'currentColor' }));
        return svg;
      }
      case 'nod': return hand({ raised: 1 });
      case 'two-finger': return hand({ raised: 2 });
      default: return document.createTextNode('·');
    }
  }

  /* ---------- rendering ---------- */

  function render(host) {
    if (!host) return;
    host.textContent = '';

    const list = document.createElement('ul');
    list.className = 'gesture-list';

    for (const c of CHANNELS) {
      const li = document.createElement('li');
      li.className = 'gesture' + (c.available ? '' : ' is-unavailable');
      li.dataset.contrastCheck = '';
      // A legend entry is not a competing call to action. Nothing in this panel
      // is tappable, so counting it against density.clutterCeiling would be the
      // enforcer measuring the wrong thing: a vocabulary reference is not a
      // competing affordance. Only actual controls carry data-competing.

      const icon = document.createElement('span');
      icon.className = 'gesture-fig';
      icon.appendChild(iconFor(c));
      li.appendChild(icon);

      const body = document.createElement('span');
      body.className = 'gesture-body';

      const top = document.createElement('span');
      top.className = 'gesture-top';
      const label = document.createElement('strong');
      label.textContent = c.label;
      const meaning = document.createElement('em');
      meaning.textContent = ' = ' + c.meaning;
      top.append(label, meaning);
      if (!c.available) {
        const badge = document.createElement('span');
        badge.className = 'gesture-badge';
        badge.textContent = 'not wired up';
        top.appendChild(badge);
      }
      body.appendChild(top);

      const detail = document.createElement('small');
      detail.textContent = c.detail;
      body.appendChild(detail);

      li.appendChild(body);
      list.appendChild(li);
    }
    host.appendChild(list);
    return list;
  }

  return { CHANNELS, render, hand, tapIcon, iconFor };
})();

window.Gestures = Gestures;
