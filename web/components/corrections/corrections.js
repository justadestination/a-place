import { h, emit } from "../../js/core/dom.js";
import { button } from "../button/button.js";

const STORAGE_KEY = "nightcal.corrections.v1";
const memoryStore = new Map();

function loadStore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      for (const [k, v] of Object.entries(parsed)) {
        memoryStore.set(k, v);
      }
    }
  } catch {
    // Fall back to memoryStore
  }
}

function saveStore() {
  try {
    const obj = Object.fromEntries(memoryStore.entries());
    localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
  } catch {
    // Non-fatal
  }
}

loadStore();

export function getCorrections(nodeId) {
  return [...(memoryStore.get(nodeId) || [])];
}

export function submitCorrection(nodeId, { text, rationale = "", submitter = "Anonymous Steward" }) {
  if (!text || !text.trim()) {
    throw new Error("Correction text is required");
  }
  const entry = {
    id: `corr-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    nodeId,
    text: text.trim(),
    rationale: rationale.trim(),
    submitter: submitter.trim() || "Anonymous Steward",
    timestamp: new Date().toISOString(),
    kind: "correction",
    outranks: true,
  };
  const list = memoryStore.get(nodeId) || [];
  list.push(entry);
  memoryStore.set(nodeId, list);
  saveStore();
  return entry;
}

export function requestForget(nodeId, { reason = "Author request under retention policy", submitter = "Author" } = {}) {
  const entry = {
    id: `forget-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    nodeId,
    text: "Notice: Section redacted/forgotten under ShadeNet data retention policy.",
    rationale: reason.trim(),
    submitter: submitter.trim() || "Author",
    timestamp: new Date().toISOString(),
    kind: "forget",
    outranks: true,
  };
  const list = memoryStore.get(nodeId) || [];
  list.push(entry);
  memoryStore.set(nodeId, list);
  saveStore();
  return entry;
}

/**
 * Corrections UI: shows authoritative outranking corrections,
 * allows submitting new append+outrank corrections,
 * and provides a separate Forget / redaction control.
 */
export function correctionsUI(nodeId, { level = 3, onUpdate = null } = {}) {
  const container = h("section.nc-corrections", { "aria-label": "Corrections and redactions" });

  function render() {
    container.replaceChildren();
    const list = getCorrections(nodeId);

    if (list.length > 0) {
      const items = list.map(c => {
        const isForget = c.kind === "forget";
        const entryClass = isForget
          ? "li.nc-correction-entry.nc-correction-entry--tombstone"
          : "li.nc-correction-entry.nc-correction-entry--outranking";

        const badgeText = isForget
          ? "Policy Redaction · Forget Control Active"
          : "Authoritative Correction · Outranks Original";

        return h(entryClass, {},
          h("span.nc-correction-entry__badge", {}, badgeText),
          h("p.nc-correction-entry__text", {}, c.text),
          h("p.nc-correction-entry__meta", {},
            `Appended by ${c.submitter}${c.rationale ? ` · Reason: ${c.rationale}` : ""} · ${new Date(c.timestamp).toLocaleDateString()}`
          )
        );
      });
      container.append(
        h(`h${level}.nc-corrections__title`, {}, `Corrections Ledger (${list.length})`),
        h("ul.nc-corrections__list", { role: "list" }, items)
      );
    }

    // Toggleable submission form
    let showForm = false;
    let showForget = false;

    const formHolder = h("div", {});

    const btnSubmitCorr = button({
      label: "Submit Correction",
      variant: "secondary",
      onClick: () => {
        showForm = !showForm;
        showForget = false;
        updateFormHolder();
      }
    });

    const btnForget = button({
      label: "Request Forget / Redaction",
      variant: "ghost",
      onClick: () => {
        showForget = !showForget;
        showForm = false;
        updateFormHolder();
      }
    });

    const controlsBar = h("div.nc-corrections__toggle", {}, btnSubmitCorr, btnForget);

    function updateFormHolder() {
      formHolder.replaceChildren();
      if (showForm) {
        const txtArea = h("textarea.nc-corrections__textarea", {
          placeholder: "Specify corrected facts or text (appends and outranks original)",
          rows: 3,
          required: true,
          "aria-label": "Correction text",
        });
        const txtReason = h("input.nc-corrections__input", {
          type: "text",
          placeholder: "Reason or source reference (optional)",
          "aria-label": "Correction reason",
        });

        const form = h("form.nc-corrections__form", {
          onsubmit: (e) => {
            e.preventDefault();
            if (!txtArea.value.trim()) return;
            submitCorrection(nodeId, { text: txtArea.value, rationale: txtReason.value });
            if (onUpdate) onUpdate();
            render();
          }
        },
          h("p.nc-eyebrow", {}, "Append + Outrank Semantics"),
          txtArea,
          txtReason,
          h("div.nc-corrections__actions", {},
            button({ label: "Cancel", variant: "ghost", onClick: () => { showForm = false; updateFormHolder(); } }),
            button({ label: "Commit Correction", variant: "primary", type: "submit" })
          )
        );
        formHolder.append(form);
      } else if (showForget) {
        const txtReason = h("input.nc-corrections__input", {
          type: "text",
          placeholder: "Reason under retention policy",
          "aria-label": "Forget reason",
        });

        const form = h("form.nc-corrections__form", {
          onsubmit: (e) => {
            e.preventDefault();
            requestForget(nodeId, { reason: txtReason.value });
            if (onUpdate) onUpdate();
            render();
          }
        },
          h("p.nc-eyebrow", {}, "Forget Control (Retention Policy)"),
          h("p.nc-muted", {}, "Requests redaction of this section according to the ShadeNet retention policy."),
          txtReason,
          h("div.nc-corrections__actions", {},
            button({ label: "Cancel", variant: "ghost", onClick: () => { showForget = false; updateFormHolder(); } }),
            button({ label: "Confirm Redaction", variant: "danger", type: "submit" })
          )
        );
        formHolder.append(form);
      }
    }

    container.append(controlsBar, formHolder);
  }

  render();
  return container;
}

export const meta = {
  name: "corrections",
  title: "Corrections and forget UI",
  summary: "Zine contract corrections UI implementing append+outrank semantics and separate Forget policy control.",
  params: { node: "node id to display corrections for" },
};

export async function embed(params) {
  const nodeId = params.get("node") || "sample-note";
  return correctionsUI(nodeId);
}
