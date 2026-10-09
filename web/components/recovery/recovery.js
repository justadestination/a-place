/**
 * Lost-Phone Recovery Component (Task 4.2).
 *
 * Provides:
 *   1. Self-service account recovery using single-use PBKDF2 recovery codes.
 *   2. Support escalation request submission for lost codes.
 *   3. Replacement passkey re-enrollment CTA upon successful code verification.
 *   4. Fully accessible WCAG 2.2 AA UI with zero raw hex or px values.
 */

import { h } from "../../js/core/dom.js";
import { button } from "../button/button.js";

export function recoveryView(options = {}) {
  const container = h("section.nc-recovery", { "aria-labelledby": "nc-recovery-title" });
  const apiBase = options.apiBase || "";

  let activeTab = "self_service"; // "self_service" | "escalation"
  let statusMessage = "";
  let statusKind = "info"; // "info" | "success" | "error"
  let isSubmitting = false;
  let recoverySuccessData = null;

  const eyebrowEl = h("p.nc-recovery__eyebrow", {}, "Account Security & Recovery");
  const titleEl = h("h2.nc-recovery__title", { id: "nc-recovery-title" }, "Lost Authenticator Recovery");
  const subtitleEl = h(
    "p.nc-recovery__subtitle",
    {},
    "If you lost your passkey device, restore access instantly using an unused recovery code, or submit an escalation request to operators."
  );
  const header = h("header.nc-recovery__header", {}, eyebrowEl, titleEl, subtitleEl);

  const statusLive = h("div.nc-recovery__status.nc-sr-only", {
    role: "status",
    "aria-live": "polite",
  });

  const tabContainer = h("div.nc-recovery__tabs", { role: "tablist", "aria-label": "Recovery options" });

  const btnTabSelf = h(
    "button.nc-recovery__tab",
    {
      type: "button",
      role: "tab",
      id: "nc-tab-self",
      "aria-selected": "true",
      "aria-controls": "nc-panel-self",
    },
    "Use Recovery Code"
  );

  const btnTabEscalate = h(
    "button.nc-recovery__tab",
    {
      type: "button",
      role: "tab",
      id: "nc-tab-escalate",
      "aria-selected": "false",
      "aria-controls": "nc-panel-escalate",
    },
    "Support Escalation"
  );

  btnTabSelf.addEventListener("click", () => {
    activeTab = "self_service";
    statusMessage = "";
    recoverySuccessData = null;
    render();
  });

  btnTabEscalate.addEventListener("click", () => {
    activeTab = "escalation";
    statusMessage = "";
    recoverySuccessData = null;
    render();
  });

  tabContainer.append(btnTabSelf, btnTabEscalate);

  const panel = h("div.nc-recovery__panel", {
    role: "tabpanel",
    id: activeTab === "self_service" ? "nc-panel-self" : "nc-panel-escalate",
    "aria-labelledby": activeTab === "self_service" ? "nc-tab-self" : "nc-tab-escalate",
  });

  async function handleSelfServiceSubmit(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const usernameInput = panel.querySelector("#nc-rec-username");
    const codeInput = panel.querySelector("#nc-rec-code");
    const username = usernameInput ? usernameInput.value.trim() : "";
    const recoveryCode = codeInput ? codeInput.value.trim() : "";

    if (!username || !recoveryCode) {
      statusMessage = "Please enter both your username and recovery code.";
      statusKind = "error";
      render();
      return;
    }

    isSubmitting = true;
    statusMessage = "Verifying recovery credentials...";
    statusKind = "info";
    render();

    try {
      if (options.onRecover) {
        const res = await options.onRecover({ username, recoveryCode });
        recoverySuccessData = res;
        statusMessage = "Account verified successfully. Please enroll your replacement device.";
        statusKind = "success";
      } else {
        const resp = await fetch(`${apiBase}/api/auth/recovery/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, recoveryCode }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || "Recovery failed");
        }
        recoverySuccessData = data;
        statusMessage = "Account verified successfully. Please enroll your replacement device.";
        statusKind = "success";
      }
    } catch (err) {
      statusMessage = err.message || "Invalid username or recovery code.";
      statusKind = "error";
    } finally {
      isSubmitting = false;
      render();
    }
  }

  async function handleEscalationSubmit(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const usernameInput = panel.querySelector("#nc-esc-username");
    const contactInput = panel.querySelector("#nc-esc-contact");
    const notesInput = panel.querySelector("#nc-esc-notes");

    const username = usernameInput ? usernameInput.value.trim() : "";
    const contact = contactInput ? contactInput.value.trim() : "";
    const notes = notesInput ? notesInput.value.trim() : "";

    if (!username || !contact) {
      statusMessage = "Username and contact information are required.";
      statusKind = "error";
      render();
      return;
    }

    isSubmitting = true;
    statusMessage = "Submitting escalation ticket to operator console...";
    statusKind = "info";
    render();

    try {
      if (options.onEscalate) {
        const res = await options.onEscalate({ username, contact, notes });
        recoverySuccessData = res;
        statusMessage = `Escalation ticket submitted (ID: ${res.id || "pending"}). An operator will contact you.`;
        statusKind = "success";
      } else {
        const resp = await fetch(`${apiBase}/api/auth/recovery/escalate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, contact, notes }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || "Escalation request failed");
        }
        recoverySuccessData = data.escalation || data;
        const ticketId = recoverySuccessData.id || "pending";
        statusMessage = `Escalation ticket submitted (${ticketId}). An operator will review your claim.`;
        statusKind = "success";
      }
    } catch (err) {
      statusMessage = err.message || "Failed to submit escalation.";
      statusKind = "error";
    } finally {
      isSubmitting = false;
      render();
    }
  }

  function render() {
    panel.innerHTML = "";
    statusLive.textContent = statusMessage;

    btnTabSelf.setAttribute("aria-selected", activeTab === "self_service" ? "true" : "false");
    btnTabEscalate.setAttribute("aria-selected", activeTab === "escalation" ? "true" : "false");

    btnTabSelf.classList.toggle("nc-recovery__tab--active", activeTab === "self_service");
    btnTabEscalate.classList.toggle("nc-recovery__tab--active", activeTab === "escalation");

    panel.id = activeTab === "self_service" ? "nc-panel-self" : "nc-panel-escalate";
    panel.setAttribute("aria-labelledby", activeTab === "self_service" ? "nc-tab-self" : "nc-tab-escalate");

    let banner = null;
    if (statusMessage) {
      banner = h(
        `div.nc-recovery__banner.nc-recovery__banner--${statusKind}`,
        { role: statusKind === "error" ? "alert" : "status" },
        statusMessage
      );
    }

    if (activeTab === "self_service") {
      if (recoverySuccessData && statusKind === "success") {
        const successBox = h("div.nc-recovery__success-card", {},
          h("h3.nc-recovery__card-title", {}, "Authentication Restored"),
          h("p.nc-recovery__card-text", {}, `Welcome back, ${recoverySuccessData.user?.username || "friend"}. An active session has been created. Re-enroll a new WebAuthn passkey to secure your new device.`),
          h("div.nc-recovery__card-actions", {},
            button({
              label: "Enroll Replacement Passkey",
              variant: "primary",
              onClick: () => {
                if (options.onEnrollPasskey) options.onEnrollPasskey(recoverySuccessData);
                else window.location.href = "/auth/";
              },
            }),
            button({
              label: "Continue to Dashboard",
              variant: "secondary",
              onClick: () => {
                if (options.onContinue) options.onContinue(recoverySuccessData);
                else window.location.href = "/";
              },
            })
          )
        );
        panel.append(...(banner ? [banner] : []), successBox);
      } else {
        const form = h("form.nc-recovery__form", { id: "nc-self-service-form" });
        form.addEventListener("submit", handleSelfServiceSubmit);

        const groupUser = h("div.nc-recovery__field", {},
          h("label.nc-recovery__label", { for: "nc-rec-username" }, "Account Username"),
          h("input.nc-recovery__input", {
            id: "nc-rec-username",
            name: "username",
            type: "text",
            required: "true",
            autocomplete: "username",
            placeholder: "e.g. nightowl42",
          })
        );

        const groupCode = h("div.nc-recovery__field", {},
          h("label.nc-recovery__label", { for: "nc-rec-code" }, "Single-Use Recovery Code"),
          h("input.nc-recovery__input.nc-recovery__input--code", {
            id: "nc-rec-code",
            name: "recoveryCode",
            type: "text",
            required: "true",
            placeholder: "e.g. NC-ABCD-1234",
            autocomplete: "off",
            spellcheck: "false",
          }),
          h("span.nc-recovery__hint", {}, "Enter one of your 8 unconsumed recovery codes generated during signup.")
        );

        const actions = h("div.nc-recovery__actions", {},
          button({
            label: isSubmitting ? "Verifying..." : "Verify & Restore Access",
            variant: "primary",
            type: "submit",
            disabled: isSubmitting,
          })
        );

        form.append(groupUser, groupCode, actions);
        panel.append(...(banner ? [banner] : []), form);
      }
    } else {
      // Escalation tab
      if (recoverySuccessData && statusKind === "success") {
        const successBox = h("div.nc-recovery__success-card", {},
          h("h3.nc-recovery__card-title", {}, "Escalation Request Logged"),
          h("p.nc-recovery__card-text", {}, `Your escalation ticket has been registered in the operator moderation queue. Reference ticket ID: ${recoverySuccessData.id || "pending"}.`),
          h("div.nc-recovery__card-actions", {},
            button({
              label: "Return to Homepage",
              variant: "secondary",
              onClick: () => {
                window.location.href = "/";
              },
            })
          )
        );
        panel.append(...(banner ? [banner] : []), successBox);
      } else {
        const form = h("form.nc-recovery__form", { id: "nc-escalation-form" });
        form.addEventListener("submit", handleEscalationSubmit);

        const groupUser = h("div.nc-recovery__field", {},
          h("label.nc-recovery__label", { for: "nc-esc-username" }, "Account Username"),
          h("input.nc-recovery__input", {
            id: "nc-esc-username",
            name: "username",
            type: "text",
            required: "true",
            autocomplete: "username",
            placeholder: "e.g. nightowl42",
          })
        );

        const groupContact = h("div.nc-recovery__field", {},
          h("label.nc-recovery__label", { for: "nc-esc-contact" }, "Contact Information"),
          h("input.nc-recovery__input", {
            id: "nc-esc-contact",
            name: "contact",
            type: "text",
            required: "true",
            placeholder: "e.g. user@example.org or Signal handle",
          }),
          h("span.nc-recovery__hint", {}, "Operators will reach out using this channel to verify identity.")
        );

        const groupNotes = h("div.nc-recovery__field", {},
          h("label.nc-recovery__label", { for: "nc-esc-notes" }, "Details / Context"),
          h("textarea.nc-recovery__textarea", {
            id: "nc-esc-notes",
            name: "notes",
            rows: "3",
            placeholder: "Describe the situation, e.g. lost phone in transit, no backup recovery codes stored.",
          })
        );

        const actions = h("div.nc-recovery__actions", {},
          button({
            label: isSubmitting ? "Submitting..." : "Submit Support Escalation",
            variant: "primary",
            type: "submit",
            disabled: isSubmitting,
          })
        );

        form.append(groupUser, groupContact, groupNotes, actions);
        panel.append(...(banner ? [banner] : []), form);
      }
    }
  }

  container.append(header, tabContainer, statusLive, panel);
  render();
  return container;
}

export const meta = {
  name: "recovery",
  title: "Lost-phone recovery",
  summary: "Self-service recovery code redemption and support escalation for lost authenticator devices.",
  params: {
    username: "Optional initial username to pre-fill",
  },
};

export async function embed(params, ctx) {
  const initialUsername = params.get("username") || "";
  const el = recoveryView();
  if (initialUsername) {
    const input = el.querySelector("#nc-rec-username");
    if (input) input.value = initialUsername;
  }
  return el;
}

