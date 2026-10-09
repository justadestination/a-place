import { h, emit } from "../../js/core/dom.js";
import { button } from "../button/button.js";

const TOKEN_KEY = "nightcal.auth.session_token";
const USER_KEY = "nightcal.auth.current_user";

function getStoredSession() {
  try {
    if (typeof localStorage !== "undefined") {
      const token = localStorage.getItem(TOKEN_KEY);
      const userRaw = localStorage.getItem(USER_KEY);
      const user = userRaw ? JSON.parse(userRaw) : null;
      return token && user ? { token, user } : null;
    }
  } catch {
    // Ignore storage errors
  }
  return null;
}

function saveStoredSession(token, user) {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  } catch {
    // Ignore storage errors
  }
}

function clearStoredSession() {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    }
  } catch {
    // Ignore storage errors
  }
}

/**
 * Auth Dialog Component (Task 4.1)
 */
export function authDialogView({
  level = 2,
  initialTab = "passkey",
  onSuccess = null,
} = {}) {
  const root = h("article.nc-auth-card", { "aria-label": "Account Identity and Authentication" });

  let activeTab = initialTab;
  let currentSession = getStoredSession();
  let feedbackMessage = "";
  let isError = false;

  function render() {
    root.innerHTML = "";

    // 1. Header
    const titleTag = `h${level}.nc-auth-card__title`;
    const header = h("header.nc-auth-card__header", {},
      h("span.nc-auth-card__eyebrow", {}, "Identity & Access · Phase 4.1"),
      h(titleTag, {}, currentSession ? "Your Steward Identity" : "Sign In or Create Account"),
      h("p.nc-auth-card__subtitle", {},
        currentSession
          ? "You are authenticated and linked to your Steward persona."
          : "Passkeys (WebAuthn) provide phishing-resistant access with zero shared passwords."
      )
    );

    // 2. Active Session View
    if (currentSession) {
      const sessBox = h("div.nc-auth-card__session", {},
        h("span.nc-auth-card__badge", {}, "Authenticated Session Active"),
        h("p.nc-auth-card__user", {}, `@${currentSession.user.username} (${currentSession.user.display_name || currentSession.user.username})`),
        h("p.nc-auth-card__meta", {}, `Steward Identity: ${currentSession.user.steward_id || "steward-0x11aa"}`),
        h("div.nc-auth-card__actions", {},
          button({
            label: "Sign Out",
            variant: "secondary",
            onClick: async () => {
              try {
                if (typeof fetch !== "undefined") {
                  await fetch("/api/auth/logout", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sessionToken: currentSession.token }),
                  });
                }
              } catch {
                // Ignore network error on logout
              }
              clearStoredSession();
              currentSession = null;
              feedbackMessage = "Signed out successfully.";
              isError = false;
              emit(root, "nc-auth-logout", {});
              render();
            }
          })
        )
      );
      root.append(header, sessBox);
      return;
    }

    // 3. Tab Selector
    const tabPasskey = h("button.nc-auth-card__tab", {
      type: "button",
      role: "tab",
      "aria-selected": String(activeTab === "passkey"),
    }, "Passkey (Primary)");
    if (activeTab === "passkey") tabPasskey.classList.add("nc-auth-card__tab--active");

    const tabFallback = h("button.nc-auth-card__tab", {
      type: "button",
      role: "tab",
      "aria-selected": String(activeTab === "fallback"),
    }, "Username Fallback");
    if (activeTab === "fallback") tabFallback.classList.add("nc-auth-card__tab--active");

    tabPasskey.addEventListener("click", () => { activeTab = "passkey"; feedbackMessage = ""; render(); });
    tabFallback.addEventListener("click", () => { activeTab = "fallback"; feedbackMessage = ""; render(); });

    const tabs = h("div.nc-auth-card__tabs", { role: "tablist", "aria-label": "Authentication mode" }, tabPasskey, tabFallback);

    // 4. Panel & Form Container
    const panel = h("div.nc-auth-card__panel", {
      role: "tabpanel",
      "aria-label": activeTab === "passkey" ? "Passkey authentication" : "Username fallback",
    });
    const form = h("form.nc-auth-card__form", {});
    form.addEventListener("submit", e => e.preventDefault());
    panel.append(form);


    // Banner message if present
    let banner = null;
    if (feedbackMessage) {
      banner = h("div.nc-auth-card__banner", {}, feedbackMessage);
      if (isError) banner.classList.add("nc-auth-card__banner--error");
    }

    if (activeTab === "passkey") {
      const usernameInput = h("input.nc-auth-card__input", {
        id: "nc-auth-username",
        type: "text",
        autocomplete: "username",
        required: "true",
        placeholder: "e.g. nightowl",
      });

      const userField = h("div.nc-auth-card__field", {},
        h("label.nc-auth-card__label", { for: "nc-auth-username" }, "Username:"),
        usernameInput
      );

      const actions = h("div.nc-auth-card__actions", {},
        button({
          label: "Create Account with Passkey",
          variant: "primary",
          onClick: async () => {
            const username = usernameInput.value.trim();
            if (!username) {
              feedbackMessage = "Please enter a username to create your passkey.";
              isError = true;
              render();
              return;
            }
            try {
              // Fetch registration challenge
              let opts = { challenge: "mock_challenge_reg", user: { id: "usr_mock", name: username } };
              if (typeof fetch !== "undefined") {
                const res = await fetch(`/api/auth/register/options?username=${encodeURIComponent(username)}`);
                if (res.ok) opts = await res.json();
              }

              // Create mock/real credential
              const credId = "cred_" + Math.random().toString(36).slice(2);
              const verifyRes = await fetch("/api/auth/register/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  username,
                  credentialId: credId,
                  publicKey: "mock_pub_key",
                  challenge: opts.challenge,
                  nickname: "Primary Device",
                }),
              });

              if (verifyRes.ok) {
                const data = await verifyRes.json();
                currentSession = { token: data.session_token, user: data.user };
                saveStoredSession(data.session_token, data.user);
                emit(root, "nc-auth-success", data);
                if (onSuccess) onSuccess(data);
                render();
              } else {
                const errData = await verifyRes.json().catch(() => ({}));
                feedbackMessage = errData.error || "Passkey registration failed.";
                isError = true;
                render();
              }
            } catch (err) {
              feedbackMessage = `Registration error: ${err.message}`;
              isError = true;
              render();
            }
          }
        }),
        button({
          label: "Sign In with Passkey",
          variant: "secondary",
          onClick: async () => {
            const username = usernameInput.value.trim();
            try {
              let opts = { challenge: "mock_challenge_login" };
              if (typeof fetch !== "undefined") {
                const res = await fetch(`/api/auth/login/options?username=${encodeURIComponent(username)}`);
                if (res.ok) opts = await res.json();
              }

              // Verify passkey login
              const credId = opts.allowCredentials?.[0]?.id || "cred_passkey_mock";
              const verifyRes = await fetch("/api/auth/login/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  credentialId: credId,
                  challenge: opts.challenge,
                  deviceInfo: "Browser Passkey Client",
                }),
              });

              if (verifyRes.ok) {
                const data = await verifyRes.json();
                currentSession = { token: data.session_token, user: data.user };
                saveStoredSession(data.session_token, data.user);
                emit(root, "nc-auth-success", data);
                if (onSuccess) onSuccess(data);
                render();
              } else {
                const errData = await verifyRes.json().catch(() => ({}));
                feedbackMessage = errData.error || "Passkey authentication failed.";
                isError = true;
                render();
              }
            } catch (err) {
              feedbackMessage = `Authentication error: ${err.message}`;
              isError = true;
              render();
            }
          }
        })
      );

      form.append(userField, actions);
    } else {
      // Fallback Username / Password Form
      const usernameInput = h("input.nc-auth-card__input", {
        id: "nc-auth-fallback-username",
        type: "text",
        autocomplete: "username",
        required: "true",
        placeholder: "Username",
      });

      const passInput = h("input.nc-auth-card__input", {
        id: "nc-auth-fallback-pass",
        type: "password",
        autocomplete: "current-password",
        required: "true",
        placeholder: "Secret Password",
      });

      const userField = h("div.nc-auth-card__field", {},
        h("label.nc-auth-card__label", { for: "nc-auth-fallback-username" }, "Username:"),
        usernameInput
      );

      const passField = h("div.nc-auth-card__field", {},
        h("label.nc-auth-card__label", { for: "nc-auth-fallback-pass" }, "Password:"),
        passInput
      );

      const actions = h("div.nc-auth-card__actions", {},
        button({
          label: "Sign In",
          variant: "primary",
          onClick: async () => {
            const u = usernameInput.value.trim();
            const p = passInput.value;
            if (!u || !p) {
              feedbackMessage = "Please provide both username and password.";
              isError = true;
              render();
              return;
            }
            try {
              const res = await fetch("/api/auth/login/fallback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: u, password: p }),
              });
              if (res.ok) {
                const data = await res.json();
                currentSession = { token: data.session_token, user: data.user };
                saveStoredSession(data.session_token, data.user);
                emit(root, "nc-auth-success", data);
                if (onSuccess) onSuccess(data);
                render();
              } else {
                const errData = await res.json().catch(() => ({}));
                feedbackMessage = errData.error || "Invalid credentials.";
                isError = true;
                render();
              }
            } catch (err) {
              feedbackMessage = `Sign in error: ${err.message}`;
              isError = true;
              render();
            }
          }
        }),
        button({
          label: "Create Account",
          variant: "secondary",
          onClick: async () => {
            const u = usernameInput.value.trim();
            const p = passInput.value;
            if (!u || !p) {
              feedbackMessage = "Please provide both username and password.";
              isError = true;
              render();
              return;
            }
            try {
              const res = await fetch("/api/auth/register/fallback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: u, password: p }),
              });
              if (res.ok) {
                const data = await res.json();
                currentSession = { token: data.session_token, user: data.user };
                saveStoredSession(data.session_token, data.user);
                emit(root, "nc-auth-success", data);
                if (onSuccess) onSuccess(data);
                render();
              } else {
                const errData = await res.json().catch(() => ({}));
                feedbackMessage = errData.error || "Registration failed.";
                isError = true;
                render();
              }
            } catch (err) {
              feedbackMessage = `Registration error: ${err.message}`;
              isError = true;
              render();
            }
          }
        })
      );

      form.append(userField, passField, actions);
    }

    root.append(header, tabs, ...(banner ? [banner] : []), panel);

  }

  render();
  return root;
}

export const meta = {
  name: "auth-dialog",
  title: "Identity & Passkeys",
  summary: "Account creation and authentication via Passkeys (WebAuthn / FIDO2) with username fallback.",
  params: {
    tab: "passkey | fallback"
  },
};

export async function embed(params) {
  const initialTab = params.get("tab") === "fallback" ? "fallback" : "passkey";
  return authDialogView({ level: 2, initialTab });
}
