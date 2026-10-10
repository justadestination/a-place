import { h } from "../../js/core/dom.js";

const searchIcon = () => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("aria-hidden", "true");
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "2");
  s.setAttribute("stroke-linecap", "round");
  s.innerHTML = '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>';
  return s;
};

export function searchDialog() {
  const input = h("input.nc-search-dialog__input", {
    type: "search",
    placeholder: "Search events, venues, performers...",
    "aria-label": "Search downtown events and venues",
    autocomplete: "off",
  });

  const resultsContainer = h("div.nc-search-dialog__results", {
    role: "region",
    "aria-live": "polite",
  });

  const dialog = h("div.nc-search-dialog", {
    role: "dialog",
    "aria-modal": "true",
    "aria-label": "Search",
    hidden: true,
  },
    h("div.nc-search-dialog__scrim", {}),
    h("div.nc-search-dialog__panel", {},
      h("div.nc-search-dialog__header", {},
        searchIcon(),
        input,
        h("button.nc-search-dialog__close", {
          type: "button",
          "aria-label": "Close search dialog",
        }, "Esc"),
      ),
      resultsContainer,
      h("div.nc-search-dialog__footer", {},
        h("span", {}, "Navigate with "),
        h("kbd", {}, "↑"),
        h("kbd", {}, "↓"),
        h("span", {}, " · Select with "),
        h("kbd", {}, "Enter"),
        h("span", {}, " · Close with "),
        h("kbd", {}, "Esc"),
      ),
    ),
  );

  let debounceTimer = null;
  let activeIndex = -1;

  function setOpen(open) {
    dialog.hidden = !open;
    if (open) {
      document.body.style.overflow = "hidden";
      input.value = "";
      resultsContainer.replaceChildren(h("p.nc-search-dialog__empty", {}, "Type a word to search shows, venues, or articles..."));
      setTimeout(() => input.focus(), 50);
    } else {
      document.body.style.overflow = "";
    }
  }

  async function performSearch(q) {
    if (!q.trim()) {
      resultsContainer.replaceChildren(h("p.nc-search-dialog__empty", {}, "Type a word to search shows, venues, or articles..."));
      return;
    }
    resultsContainer.replaceChildren(h("p.nc-search-dialog__loading", {}, "Searching..."));
    try {
      const resp = await fetch(`/api/search?q=${encodeURIComponent(q.trim())}`);
      if (!resp.ok) throw new Error("Search request failed");
      const data = await resp.json();
      renderResults(data);
    } catch (e) {
      resultsContainer.replaceChildren(h("p.nc-search-dialog__error", {}, "Search error. Please try again."));
    }
  }

  function renderResults(data) {
    const { results, total, duration_ms } = data;
    activeIndex = -1;
    if (total === 0) {
      resultsContainer.replaceChildren(
        h("p.nc-search-dialog__empty", {}, `No matches found for "${data.query}".`),
      );
      return;
    }

    const sections = [];

    // Helper for rendering group
    const addGroup = (title, items, renderItem) => {
      if (!items || items.length === 0) return;
      sections.push(
        h("div.nc-search-dialog__group", {},
          h("h3.nc-search-dialog__group-title", {}, title),
          h("ul.nc-search-dialog__list", { role: "list" },
            items.map(renderItem),
          ),
        ),
      );
    };

    // 1. Spots (Events)
    addGroup("Shows & Events", results.spots, (item) => {
      const dateStr = item.startsAt ? new Date(item.startsAt).toLocaleDateString("en-US", {
        weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
      }) : "";
      return h("li.nc-search-dialog__item", {},
        h("a.nc-search-dialog__link", { href: item.url || `/event/${item.id}` },
          h("div.nc-search-dialog__item-main", {},
            h("span.nc-search-dialog__item-title", {}, item.title),
            h("span.nc-search-dialog__item-sub", {}, `${item.subtitle || ""} ${dateStr ? " · " + dateStr : ""}`),
          ),
        ),
      );
    });

    // 2. Spaces (Venues)
    addGroup("Venues & Spaces", results.spaces, (item) => {
      return h("li.nc-search-dialog__item", {},
        h("a.nc-search-dialog__link", { href: item.url || `/space/${item.id}` },
          h("div.nc-search-dialog__item-main", {},
            h("span.nc-search-dialog__item-title", {}, item.title),
            h("span.nc-search-dialog__item-sub", {}, item.subtitle || "Santa Rosa"),
          ),
        ),
      );
    });

    // 3. The Listed (Acts/Entities)
    addGroup("Artists & Performers", results.listed, (item) => {
      return h("li.nc-search-dialog__item", {},
        h("a.nc-search-dialog__link", { href: item.url || `/entity/${item.id}` },
          h("div.nc-search-dialog__item-main", {},
            h("span.nc-search-dialog__item-title", {}, item.title),
            h("span.nc-search-dialog__item-sub", {}, item.subtitle || "Performer"),
          ),
        ),
      );
    });

    // 4. Expressions (Zine Articles)
    addGroup("Zine & Stories", results.expressions, (item) => {
      return h("li.nc-search-dialog__item", {},
        h("a.nc-search-dialog__link", { href: item.url || `/zine/${item.id}` },
          h("div.nc-search-dialog__item-main", {},
            h("span.nc-search-dialog__item-title", {}, item.title),
            h("span.nc-search-dialog__item-sub", {}, item.subtitle || "Article"),
          ),
        ),
      );
    });

    sections.push(
      h("div.nc-search-dialog__meta", {}, `Found ${total} result${total === 1 ? "" : "s"} in ${duration_ms}ms`),
    );

    resultsContainer.replaceChildren(...sections);
  }

  input.addEventListener("input", (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => performSearch(e.target.value), 200);
  });

  dialog.querySelector(".nc-search-dialog__scrim").addEventListener("click", () => setOpen(false));
  dialog.querySelector(".nc-search-dialog__close").addEventListener("click", () => setOpen(false));

  dialog.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    const links = Array.from(dialog.querySelectorAll(".nc-search-dialog__link"));
    if (!links.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % links.length;
      links[activeIndex].focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + links.length) % links.length;
      links[activeIndex].focus();
    }
  });

  // Global keydown shortcut: "/" or "Cmd+K" / "Ctrl+K"
  window.addEventListener("keydown", (e) => {
    if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName))) {
      e.preventDefault();
      setOpen(true);
    }
  });

  dialog.open = () => setOpen(true);
  dialog.close = () => setOpen(false);

  return dialog;
}

export function searchButton(onClick) {
  const btn = h("button.nc-button.nc-button--ghost.nc-search-trigger", {
    type: "button",
    "aria-label": "Search calendar and venues (Press /)",
    title: "Search (/)",
  }, searchIcon());
  btn.addEventListener("click", onClick);
  return btn;
}
