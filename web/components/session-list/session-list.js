/**
 * Session Management Component (Task 4.3).
 *
 * Provides:
 *   1. Listing of active sessions and devices with "This Device" indicator.
 *   2. Instant revocation of individual remote device sessions.
 *   3. Global revocation of all other active sessions.
 *   4. Accessible announcements via ARIA live region.
 */

import { h } from "../../js/core/dom.js";
import { button } from "../button/button.js";

const DEFAULT_MOCK_SESSIONS = [
  {
    session_id: "sess_curr_alpha",
    device_info: "Current Browser (Downtown Hub)",
    created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    is_current: true,
  },
  {
    session_id: "sess_remote_phone",
    device_info: "iPhone 15 Pro (Safari Mobile)",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
    is_current: false,
  },
  {
    session_id: "sess_remote_laptop",
    device_info: "MacBook Air (Firefox)",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 28).toISOString(),
    is_current: false,
  },
];

function formatDate(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

export function sessionListView(options = {}) {
  const container = h("section.nc-session-list", { "aria-labelledby": "nc-sessions-title" });
  let sessions = options.initialSessions ? [...options.initialSessions] : [...DEFAULT_MOCK_SESSIONS];
  const sessionToken = options.sessionToken || "";
  const apiBase = options.apiBase || "";

  const titleEl = h("h2.nc-session-list__title", { id: "nc-sessions-title" }, "Active Sessions & Devices");
  const subtitleEl = h("p.nc-session-list__subtitle", {}, "Manage devices currently signed into your NightCal account. Revoking a session signs that device out immediately.");
  const eyebrowEl = h("p.nc-session-list__eyebrow", {}, "Identity & Security");

  const header = h("header.nc-session-list__header", {}, eyebrowEl, titleEl, subtitleEl);
  const statusLive = h("div.nc-session-list__status.nc-sr-only", { role: "status", "aria-live": "polite" }, "");

  const countEl = h("span.nc-session-list__count", {}, "");
  const listEl = h("ul.nc-session-list__items", { role: "list", "aria-label": "Logged-in devices" });

  let revokeAllBtn;

  function announce(msg) {
    statusLive.className = "nc-session-list__status";
    statusLive.textContent = msg;
  }

  async function revokeRemote(targetId, deviceName) {
    if (options.onRevoke) {
      await options.onRevoke(targetId);
    } else if (sessionToken) {
      try {
        const resp = await fetch(`${apiBase}/api/auth/sessions/revoke`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${sessionToken}`,
          },
          body: JSON.stringify({ sessionId: targetId }),
        });
        if (!resp.ok) {
          throw new Error(`Failed to revoke session: ${resp.status}`);
        }
      } catch (err) {
        announce(`Error revoking session: ${err.message}`);
        return;
      }
    }
    sessions = sessions.filter(s => s.session_id !== targetId);
    announce(`Signed out ${deviceName || "remote device"}. Session terminated.`);
    render();
  }

  async function revokeAllOthers() {
    if (options.onRevokeAll) {
      await options.onRevokeAll();
    } else if (sessionToken) {
      try {
        const resp = await fetch(`${apiBase}/api/auth/sessions/revoke-others`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${sessionToken}`,
          },
        });
        if (!resp.ok) {
          throw new Error(`Failed to revoke sessions: ${resp.status}`);
        }
      } catch (err) {
        announce(`Error signing out other devices: ${err.message}`);
        return;
      }
    }
    const count = sessions.filter(s => !s.is_current).length;
    sessions = sessions.filter(s => s.is_current);
    announce(`Signed out ${count} other device${count === 1 ? "" : "s"}.`);
    render();
  }

  revokeAllBtn = button({
    label: "Sign out all other devices",
    variant: "ghost",
    onClick: () => {
      revokeAllOthers();
    },
  });
  revokeAllBtn.classList.add("nc-session-list__revoke-all");

  const toolbar = h("div.nc-session-list__toolbar", {}, countEl, revokeAllBtn);

  function render() {
    countEl.textContent = `${sessions.length} active device${sessions.length === 1 ? "" : "s"}`;
    const otherSessionsCount = sessions.filter(s => !s.is_current).length;
    if (otherSessionsCount === 0) {
      revokeAllBtn.style.display = "none";
    } else {
      revokeAllBtn.style.display = "inline-flex";
    }

    listEl.replaceChildren();

    if (sessions.length === 0) {
      listEl.append(h("li.nc-session-list__empty", {}, "No active sessions found."));
      return;
    }

    for (const item of sessions) {
      const isCurrent = Boolean(item.is_current);
      const li = h("li.nc-session-item" + (isCurrent ? ".nc-session-item--current" : ""), {
        "data-session-id": item.session_id,
      });

      const deviceName = item.device_info || "Web Client";
      const devEl = h("div.nc-session-item__device", {}, deviceName);
      if (isCurrent) {
        devEl.append(h("span.nc-session-item__badge", {}, "This Device"));
      }

      const metaEl = h(
        "div.nc-session-item__meta",
        {},
        `Signed in ${formatDate(item.created_at)}`
      );

      const infoEl = h("div.nc-session-item__info", {}, devEl, metaEl);
      const actionsEl = h("div.nc-session-item__actions", {});

      if (!isCurrent) {
        const revokeBtn = button({
          label: "Revoke",
          variant: "ghost",
          onClick: () => revokeRemote(item.session_id, deviceName),
        });
        revokeBtn.setAttribute("aria-label", `Revoke session for ${deviceName}`);
        actionsEl.append(revokeBtn);
      }

      li.append(infoEl, actionsEl);
      listEl.append(li);
    }
  }

  render();
  container.append(header, toolbar, listEl, statusLive);

  // If live session token was passed and initialSessions was not overridden, fetch live sessions
  if (sessionToken && !options.initialSessions) {
    fetch(`${apiBase}/api/auth/sessions`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then(r => r.json())
      .then(data => {
        if (data.authenticated && Array.isArray(data.sessions)) {
          sessions = data.sessions;
          render();
        }
      })
      .catch(() => {
        // Fall back gracefully to mock sessions
      });
  }

  return container;
}

export const meta = {
  name: "session-list",
  title: "Session management",
  summary: "List active sessions and logged-in devices with instant per-session revocation and global sign-out.",
  params: {
    session: "Active session token to query and manage",
  },
};

export async function embed(params, ctx) {
  const sessionToken = params.get("session") || "";
  return sessionListView({ sessionToken });
}
