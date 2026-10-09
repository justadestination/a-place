import { h, emit } from "../../js/core/dom.js";
import { button } from "../button/button.js";

const STORAGE_KEY = "nightcal.article_intake.v1";
const memoryQueue = new Map();

const SPAM_KEYWORDS = [
  "online casino",
  "buy cheap",
  "crypto pump",
  "viagra",
  "free followers",
  "click here to win",
  "telegram @",
  "whatsapp +"
];

function checkClientSpam(title, body) {
  const combined = `${title} ${body}`.toLowerCase();
  for (const kw of SPAM_KEYWORDS) {
    if (combined.includes(kw)) {
      return { isSpam: true, reason: "Automated moderation check failed: suspicious promotional patterns detected." };
    }
  }
  const urls = (body.match(/https?:\/\/[^\s]+/g) || []).length;
  const words = body.trim().split(/\s+/).length;
  if (words < 20 && urls >= 3) {
    return { isSpam: true, reason: "Automated moderation check failed: excessive link density for short submission." };
  }
  return { isSpam: false, reason: "" };
}

function loadStore() {
  try {
    if (typeof localStorage !== "undefined") {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        for (const [k, v] of Object.entries(parsed)) {
          memoryQueue.set(k, v);
        }
      }
    }
  } catch {
    // Non-fatal
  }
}

function saveStore() {
  try {
    if (typeof localStorage !== "undefined") {
      const obj = Object.fromEntries(memoryQueue.entries());
      localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
    }
  } catch {
    // Non-fatal
  }
}

loadStore();

export function getIntakeItems() {
  return [...memoryQueue.values()].sort((a, b) => new Date(b.submittedAt) - new Date(a.submittedAt));
}

export function submitArticleDraft({ title, body, type = "article", author = "Anonymous Steward", venues = [], events = [], tags = [] }) {
  if (!title || !title.trim()) {
    throw new Error("Title is required");
  }
  if (!body || !body.trim()) {
    throw new Error("Body content is required");
  }

  const { isSpam, reason } = checkClientSpam(title, body);
  const id = `draft-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const now = new Date().toISOString();

  const item = {
    id,
    title: title.trim(),
    body: body.trim(),
    type,
    author: author.trim() || "Anonymous Steward",
    venues: Array.isArray(venues) ? venues : venues.split(",").map(s => s.trim()).filter(Boolean),
    events: Array.isArray(events) ? events : events.split(",").map(s => s.trim()).filter(Boolean),
    tags: Array.isArray(tags) ? tags : tags.split(",").map(s => s.trim()).filter(Boolean),
    status: isSpam ? "rejected" : "pending",
    rejectionReason: isSpam ? reason : null,
    submittedAt: now,
    reviewedAt: isSpam ? now : null,
    nodeId: null,
  };

  memoryQueue.set(id, item);
  saveStore();
  return item;
}

export function rejectArticleDraft(id, reason) {
  if (!reason || !reason.trim()) {
    throw new Error("Rejections must carry a plain-language reason");
  }
  const item = memoryQueue.get(id);
  if (!item) throw new Error(`Draft ${id} not found`);

  item.status = "rejected";
  item.rejectionReason = reason.trim();
  item.reviewedAt = new Date().toISOString();
  memoryQueue.set(id, item);
  saveStore();
  return item;
}

export function approveArticleDraft(id) {
  const item = memoryQueue.get(id);
  if (!item) throw new Error(`Draft ${id} not found`);
  if (item.status === "rejected") {
    throw new Error(`Cannot approve a rejected draft: ${item.rejectionReason}`);
  }

  const slug = item.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "article";
  item.status = "instantiated";
  item.nodeId = `note:${slug}`;
  item.reviewedAt = new Date().toISOString();
  memoryQueue.set(id, item);
  saveStore();
  return item;
}

/**
 * Article Intake Component
 */
export function articleIntake({ onUpdate = null } = {}) {
  const root = h("section.nc-intake", { "aria-label": "Article Intake and Review Pipeline" });

  let notice = null;

  function render() {
    root.replaceChildren();

    // Notice banner
    let noticeEl = null;
    if (notice) {
      noticeEl = h("div.nc-intake__notice", { role: "alert", "data-kind": notice.kind },
        h("p.nc-intake__notice-text", {}, notice.text)
      );
    }

    // Header
    const header = h("header.nc-intake__header", {},
      h("h2.nc-intake__title", {}, "Zine Article Intake & Instantiation"),
      h("p.nc-intake__subtitle", {}, "Submit draft dispatches for review. Approved submissions instantiate into the content graph.")
    );

    // Form
    const titleInput = h("input.nc-input", {
      type: "text",
      name: "title",
      id: "nc-intake-title",
      placeholder: "e.g., Midnight Sounds at Arlene Francis Center",
      required: true,
      "aria-label": "Article title",
    });

    const typeSelect = h("select.nc-select", {
      name: "type",
      id: "nc-intake-type",
      "aria-label": "Article type",
    },
      h("option", { value: "article" }, "Article"),
      h("option", { value: "review" }, "Review"),
      h("option", { value: "letter" }, "Letter"),
      h("option", { value: "editorial" }, "Editorial")
    );

    const authorInput = h("input.nc-input", {
      type: "text",
      name: "author",
      id: "nc-intake-author",
      placeholder: "e.g., a2a://agent/steward_42 or Your Pseudonym",
      "aria-label": "Author identifier",
    });

    const venuesInput = h("input.nc-input", {
      type: "text",
      name: "venues",
      id: "nc-intake-venues",
      placeholder: "e.g., royal, arlene-francis (comma-separated)",
      "aria-label": "Associated venue IDs",
    });

    const eventsInput = h("input.nc-input", {
      type: "text",
      name: "events",
      id: "nc-intake-events",
      placeholder: "e.g., evt_456 (comma-separated)",
      "aria-label": "Associated event IDs",
    });

    const bodyInput = h("textarea.nc-textarea", {
      name: "body",
      id: "nc-intake-body",
      rows: "5",
      placeholder: "Write your piece. Use [[links]] to reference venues, events, or zine notes...",
      required: true,
      "aria-label": "Article body with wiki-links",
    });

    const submitBtn = button({
      label: "Submit Draft for Review",
      variant: "primary",
      type: "submit",
    });

    const form = h("form.nc-intake__form", {
      onsubmit: (e) => {
        e.preventDefault();
        try {
          const item = submitArticleDraft({
            title: titleInput.value,
            type: typeSelect.value,
            author: authorInput.value,
            venues: venuesInput.value,
            events: eventsInput.value,
            body: bodyInput.value,
          });

          if (item.status === "rejected") {
            notice = { kind: "error", text: `Submission rejected: ${item.rejectionReason}` };
          } else {
            notice = { kind: "success", text: `Draft submitted successfully (ID: ${item.id}). Pending review.` };
            titleInput.value = "";
            authorInput.value = "";
            venuesInput.value = "";
            eventsInput.value = "";
            bodyInput.value = "";
          }
        } catch (err) {
          notice = { kind: "error", text: err.message };
        }
        render();
        if (onUpdate) onUpdate();
      }
    },
      h("div.nc-intake__field", {},
        h("label.nc-label", { for: "nc-intake-title" }, "Article Title"),
        titleInput
      ),
      h("div.nc-intake__row", {},
        h("div.nc-intake__field", {},
          h("label.nc-label", { for: "nc-intake-type" }, "Piece Type"),
          typeSelect
        ),
        h("div.nc-intake__field", {},
          h("label.nc-label", { for: "nc-intake-author" }, "Author / Steward"),
          authorInput
        )
      ),
      h("div.nc-intake__row", {},
        h("div.nc-intake__field", {},
          h("label.nc-label", { for: "nc-intake-venues" }, "Associated Venues"),
          venuesInput
        ),
        h("div.nc-intake__field", {},
          h("label.nc-label", { for: "nc-intake-events" }, "Associated Events"),
          eventsInput
        )
      ),
      h("div.nc-intake__field", {},
        h("label.nc-label", { for: "nc-intake-body" }, "Draft Body (Markdown & [[wiki-links]])"),
        bodyInput
      ),
      h("div.nc-intake__actions", {}, submitBtn)
    );

    // Queue / Review section
    const queue = getIntakeItems();
    const queueItems = queue.map(item => {
      const isPending = item.status === "pending";
      const isApproved = item.status === "instantiated";
      const isRejected = item.status === "rejected";

      let statusBadge = h("span.nc-intake__badge.nc-intake__badge--pending", {}, "Pending Review");
      if (isApproved) {
        statusBadge = h("span.nc-intake__badge.nc-intake__badge--instantiated", {}, "Live in Graph");
      } else if (isRejected) {
        statusBadge = h("span.nc-intake__badge.nc-intake__badge--rejected", {}, "Rejected");
      }

      let actionsEl = null;
      if (isPending) {
        const approveBtn = button({
          label: "Approve & Instantiate",
          variant: "primary",
          onclick: () => {
            approveArticleDraft(item.id);
            notice = { kind: "success", text: `Draft ${item.id} approved and instantiated into the graph.` };
            render();
            if (onUpdate) onUpdate();
          }
        });

        const rejectBtn = button({
          label: "Reject",
          variant: "secondary",
          onclick: () => {
            rejectArticleDraft(item.id, "Content does not meet editorial standards.");
            notice = { kind: "info", text: `Draft ${item.id} rejected: Content does not meet editorial standards.` };
            render();
            if (onUpdate) onUpdate();
          }
        });

        actionsEl = h("div.nc-intake__item-actions", {}, approveBtn, rejectBtn);
      }

      let statusDetail = null;
      if (isRejected) {
        statusDetail = h("p.nc-intake__rejection-reason", {},
          h("strong", {}, "Reason: "),
          item.rejectionReason || "No reason specified"
        );
      } else if (isApproved) {
        statusDetail = h("p.nc-intake__node-link", {},
          h("strong", {}, "Node ID: "),
          h("a", { href: `/zine/?node=${encodeURIComponent(item.nodeId)}` }, item.nodeId)
        );
      }

      return h("article.nc-intake__item", { "data-status": item.status },
        h("div.nc-intake__item-header", {},
          h("h4.nc-intake__item-title", {}, item.title),
          statusBadge
        ),
        h("p.nc-intake__item-meta", {},
          `${item.type.toUpperCase()} · by ${item.author} · ${new Date(item.submittedAt).toLocaleDateString()}`
        ),
        h("p.nc-intake__item-excerpt", {}, item.body.slice(0, 180) + (item.body.length > 180 ? "…" : "")),
        statusDetail,
        actionsEl
      );
    });

    const queueSection = h("div.nc-intake__queue", {},
      h("h3.nc-intake__queue-title", {}, `Review Queue (${queue.length})`),
      queue.length === 0
        ? h("p.nc-intake__empty", {}, "No submissions currently in the intake queue.")
        : h("div.nc-intake__list", {}, ...queueItems)
    );

    if (noticeEl) root.appendChild(noticeEl);
    root.appendChild(header);
    root.appendChild(form);
    root.appendChild(queueSection);
  }

  render();
  return root;
}

export const meta = {
  name: "article-intake",
  title: "Article intake and review",
  summary: "Zine article intake pipeline: draft submission, spam moderation, and graph node instantiation.",
  params: {
    status: "filter by status"
  },
};

export async function embed(params) {
  return articleIntake();
}
