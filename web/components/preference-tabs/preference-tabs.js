/**
 * Preference and settings tabs (Task 4.6).
 *
 * One settings surface for notifications, muted venues, theme, density,
 * text size, motion, and steward. Changes apply immediately and persist
 * through POST /api/auth/preferences (deep-merged server-side).
 */

import { h, clear } from "../../js/core/dom.js";
import Theme from "../../js/core/theme.js";
import { button } from "../button/button.js";

const DEFAULT_PREFS = {
  theme: "system",
  density: "comfortable",
  text_scale: 1,
  motion: "system",
  notifications: {
    earmark_reminders: true,
    cancellation_alerts: true,
    daily_digest: false,
  },
  muted_venues: [],
  steward_handle: "",
  steward_enabled: true,
};

const TABS = [
  { key: "notifications", label: "Notifications" },
  { key: "muted", label: "Muted venues" },
  { key: "display", label: "Theme and display" },
  { key: "steward", label: "Steward" },
];

function cloneDefaults() {
  return {
    ...DEFAULT_PREFS,
    notifications: { ...DEFAULT_PREFS.notifications },
    muted_venues: [],
  };
}

function mergePrefs(base, incoming) {
  const result = { ...base, ...incoming };
  result.notifications = {
    ...DEFAULT_PREFS.notifications,
    ...(base.notifications || {}),
    ...(incoming.notifications || {}),
  };
  if (!Array.isArray(result.muted_venues)) result.muted_venues = [];
  return result;
}

function applyDisplay(spec) {
  Theme.setScheme(spec.theme || "system");
  Theme.setDensity(spec.density || "comfortable");
  const scale = Number(spec.text_scale ?? 1);
  Theme.setTextScale(Number.isFinite(scale) ? scale : 1);
  Theme.setMotion(spec.motion || "system");
}

export function preferenceTabsView(options = {}) {
  const apiBase = options.apiBase || "";
  const sessionToken = options.sessionToken || "";
  const user = options.user || null;
  let prefs = mergePrefs(cloneDefaults(), options.preferences || {});
  let active = "notifications";
  let ready = false;

  const container = h("section.nc-preference-tabs", { "aria-labelledby": "nc-prefs-title" });
  const liveStatus = h("div.nc-prefs-live.nc-sr-only", {
    role: "status",
    "aria-live": "polite",
    id: "nc-prefs-live-status",
  });
  const tabsRef = h("div.nc-prefs-tabs", { role: "tablist", "aria-label": "Settings sections" });
  const panelHost = h("div.nc-prefs-panels");

  function announce(msg) {
    liveStatus.textContent = "";
    setTimeout(() => { liveStatus.textContent = msg; }, 50);
  }

  let saveChain = Promise.resolve();

  function savePrefs() {
    saveChain = saveChain.then(async () => {
      const snapshot = mergePrefs(cloneDefaults(), prefs);
      try {
        localStorage.setItem(`nightcal.prefs.v1:${user?.username || ""}`, JSON.stringify(snapshot));
      } catch { /* storage may be blocked */ }
      if (!sessionToken) {
        announce("Settings saved on this device");
        return;
      }
      const resp = await fetch(`${apiBase}/api/auth/preferences`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionToken}`,
          "X-Session-Token": sessionToken,
        },
        body: JSON.stringify({ preferences: snapshot }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `save failed (${resp.status})`);
      }
      announce("Settings saved");
    }).catch((err) => {
      announce(`Could not save: ${err.message}`);
    });
    return saveChain;
  }

  function onChange(partial) {
    prefs = mergePrefs(prefs, partial);
    applyDisplay(prefs);
    paint();
    if (ready) savePrefs();
  }

  function radioGroup(key, legend, optionsList) {
    const field = h("fieldset.nc-prefs-field");
    field.appendChild(h("legend.nc-prefs-field-label", {}, legend));
    const group = h("div.nc-prefs-radio-group");
    for (const [value, text] of optionsList) {
      const selected = String(prefs[key]) === String(value);
      const label = h("label.nc-prefs-radio-label", { "aria-pressed": selected ? "true" : "false" });
      const input = h("input", {
        type: "radio",
        name: `nc-prefs-${key}`,
        value: String(value),
        checked: selected,
      });
      input.addEventListener("change", () => {
        const next = key === "text_scale" ? Number(value) : value;
        onChange({ [key]: next });
      });
      label.append(input, h("span.nc-prefs-radio-text", {}, text));
      group.appendChild(label);
    }
    field.appendChild(group);
    return field;
  }

  function notificationPanel() {
    const wrap = h("div.nc-prefs-section");
    wrap.append(
      h("div.nc-prefs-section-head", {},
        h("h2.nc-prefs-section-title", {}, "Notifications"),
        h("p.nc-prefs-section-desc", {}, "Choose what NightCal is allowed to tell you."),
      ),
    );
    const items = [
      ["earmark_reminders", "Earmark reminders", "A nudge before events you have marked"],
      ["cancellation_alerts", "Cancellation alerts", "Hear when a show is called off"],
      ["daily_digest", "Daily digest", "One evening roundup"],
    ];
    for (const [key, label, desc] of items) {
      const id = `nc-prefs-note-${key}`;
      const row = h("label.nc-prefs-check", { for: id });
      const input = h("input", {
        type: "checkbox",
        id,
        checked: Boolean(prefs.notifications?.[key]),
      });
      input.addEventListener("change", () => {
        onChange({ notifications: { [key]: input.checked } });
      });
      row.append(input, h("span", {}, h("span.nc-prefs-field-label", {}, label), h("span.nc-prefs-section-desc", {}, desc)));
      wrap.appendChild(row);
    }
    return wrap;
  }

  function mutedPanel() {
    const wrap = h("div.nc-prefs-section");
    wrap.append(
      h("div.nc-prefs-section-head", {},
        h("h2.nc-prefs-section-title", {}, "Muted venues"),
        h("p.nc-prefs-section-desc", {}, "Hide listings and alerts from venues you mute."),
      ),
    );
    const input = h("input.nc-prefs-input", {
      id: "nc-prefs-venue-input",
      placeholder: "Venue name or id",
      "aria-label": "Venue name or id",
    });
    const add = () => {
      const val = input.value.trim();
      if (!val) return;
      if (!prefs.muted_venues.some(v => v.toLowerCase() === val.toLowerCase())) {
        onChange({ muted_venues: prefs.muted_venues.concat(val) });
      }
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
    const addBtn = button({ label: "Add venue", variant: "secondary", onClick: add });
    wrap.appendChild(h("div.nc-prefs-field.nc-prefs-inline", {}, input, addBtn));
    const list = h("ul.nc-prefs-venue-list");
    if (prefs.muted_venues.length === 0) {
      list.appendChild(h("li.nc-prefs-section-desc", {}, "No venues muted."));
    }
    for (const venue of prefs.muted_venues) {
      const item = h("li.nc-prefs-venue-item");
      const remove = button({
        label: `Remove ${venue}`,
        variant: "ghost",
        onClick: () => onChange({ muted_venues: prefs.muted_venues.filter(v => v !== venue) }),
      });
      item.append(h("span.nc-prefs-venue-name", {}, venue), remove);
      list.appendChild(item);
    }
    wrap.appendChild(list);
    return wrap;
  }

  function displayPanel() {
    const wrap = h("div.nc-prefs-section");
    wrap.append(
      h("div.nc-prefs-section-head", {},
        h("h2.nc-prefs-section-title", {}, "Theme and display"),
        h("p.nc-prefs-section-desc", {}, "These change the page immediately and are saved for next time."),
      ),
    );
    wrap.append(
      radioGroup("theme", "Scheme", [["system", "Match system"], ["light", "Light"], ["dark", "Dark"]]),
      radioGroup("text_scale", "Text size", [["1", "Default"], ["1.25", "Large"], ["1.5", "Larger"], ["2", "Largest"]]),
      radioGroup("density", "Density", [["compact", "Tight"], ["comfortable", "Normal"], ["spacious", "Roomy"]]),
      radioGroup("motion", "Motion", [["system", "Match system"], ["reduce", "Reduce"], ["full", "Allow"]]),
    );
    return wrap;
  }

  function stewardPanel() {
    const wrap = h("div.nc-prefs-section");
    wrap.append(
      h("div.nc-prefs-section-head", {},
        h("h2.nc-prefs-section-title", {}, "Steward"),
        h("p.nc-prefs-section-desc", {}, "How the steward addresses you, and whether personalization is on."),
      ),
    );
    const handle = h("input.nc-prefs-input", {
      id: "nc-prefs-steward-handle",
      value: prefs.steward_handle || "",
      placeholder: "Your steward name",
      autocomplete: "nickname",
    });
    handle.addEventListener("change", () => onChange({ steward_handle: handle.value.trim() }));
    const handleField = h("div.nc-prefs-field", {},
      h("label.nc-prefs-field-label", { for: "nc-prefs-steward-handle" }, "Steward handle"),
      handle,
    );
    const enabledId = "nc-prefs-steward-enabled";
    const enabled = h("input", { type: "checkbox", id: enabledId, checked: Boolean(prefs.steward_enabled) });
    enabled.addEventListener("change", () => onChange({ steward_enabled: enabled.checked }));
    wrap.append(
      handleField,
      h("label.nc-prefs-check", { for: enabledId }, enabled, h("span.nc-prefs-field-label", {}, "Use steward personalization")),
    );
    return wrap;
  }

  const panels = {
    notifications: notificationPanel,
    muted: mutedPanel,
    display: displayPanel,
    steward: stewardPanel,
  };

  function paint() {
    clear(tabsRef);
    for (const tab of TABS) {
      const selected = tab.key === active;
      const buttonEl = h("button.nc-prefs-tab", {
        type: "button",
        role: "tab",
        "data-tab": tab.key,
        id: `nc-prefs-tab-${tab.key}`,
        "aria-selected": selected ? "true" : "false",
        "aria-controls": `nc-prefs-panel-${tab.key}`,
        tabindex: selected ? "0" : "-1",
      }, h("span.nc-prefs-tab-label", {}, tab.label));
      buttonEl.addEventListener("click", () => {
        active = tab.key;
        paint();
      });
      tabsRef.appendChild(buttonEl);
    }
    clear(panelHost);
    const panel = h("div.nc-prefs-panel", {
      role: "tabpanel",
      id: `nc-prefs-panel-${active}`,
      "aria-labelledby": `nc-prefs-tab-${active}`,
    });
    panel.appendChild(panels[active]());
    panelHost.appendChild(panel);
  }

  container.append(
    h("h1.nc-prefs-title", { id: "nc-prefs-title" }, "Settings"),
    h("p.nc-prefs-subtitle", {}, "Notification preferences, muted venues, theme, density, and steward settings. Changes apply live and persist across sessions."),
    liveStatus,
    tabsRef,
    panelHost,
  );

  const reset = button({
    label: "Reset to defaults",
    variant: "ghost",
    onClick: () => onChange(cloneDefaults()),
  });
  container.appendChild(h("div.nc-prefs-actions", {}, reset));

  paint();

  async function loadPrefs() {
    if (sessionToken) {
      try {
        const resp = await fetch(`${apiBase}/api/auth/preferences`, {
          headers: {
            Authorization: `Bearer ${sessionToken}`,
            "X-Session-Token": sessionToken,
          },
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.preferences && typeof data.preferences === "object") {
            prefs = mergePrefs(cloneDefaults(), data.preferences);
          }
        }
      } catch (err) {
        announce(`Could not load preferences: ${err.message}`);
      }
    } else {
      try {
        const stored = localStorage.getItem(`nightcal.prefs.v1:${user?.username || ""}`);
        if (stored) prefs = mergePrefs(cloneDefaults(), JSON.parse(stored));
      } catch { /* ignore broken storage */ }
    }
    applyDisplay(prefs);
    ready = true;
    paint();
  }

  loadPrefs();
  return container;
}

export const meta = {
  name: "preference-tabs",
  title: "Settings",
  summary: "Notifications, muted venues, theme, density, and steward settings in one place.",
  params: { session: "session token used to load and save preferences" },
};

export function embed(params) {
  const sessionToken = params?.get?.("session") || "";
  return preferenceTabsView({ sessionToken });
}
