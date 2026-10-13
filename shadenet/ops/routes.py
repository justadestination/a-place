"""HTTP routes for /api/ops/* and the gate in front of legacy /api/operator/*.

The server calls handle_ops() for any /api/ops/ path and require_operator() in
front of the legacy operator endpoints. Every mutation is CSRF-checked and
audited; dangerous ones also need a fresh TOTP code (X-Ops-Step-Up).
"""

from __future__ import annotations

import json
import traceback
import urllib.parse
from http.cookies import SimpleCookie
from typing import Any, Callable

from shadenet.logging import get_logger
from shadenet.ops import agegate, audit, auth, logs, metrics, recovery, settings, steward, succession

logger = get_logger("ops")

# Legacy operator endpoints that must stay public: bar door nodes call this one.
PUBLIC_OPERATOR_PATHS = {"/api/operator/door-verify"}

# Separate, strict budget for login attempts (the general operator bucket is 1000 burst).
LOGIN_RATE = (10.0, 10 / 900)  # 10 tries, refilling one per 90 s


class Ctx:
    """What the routes need from the server, without importing it (avoids a cycle)."""

    def __init__(self, venues: Callable[[], list[dict]], operator_status: Callable[[], dict]):
        self.venues = venues
        self.operator_status = operator_status


def _ip(h) -> str:
    return auth.client_ip(h.client_address[0], h.headers.get("X-Forwarded-For"))


def _token(h) -> str | None:
    c = SimpleCookie()
    try:
        c.load(h.headers.get("Cookie", ""))
    except Exception:  # noqa: BLE001 - malformed cookie header = no session
        return None
    m = c.get(auth.COOKIE)
    return m.value if m else None


def _send(h, code: int, payload: Any, cookie: str | None = None) -> None:
    headers = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
    if cookie is not None:
        headers["Set-Cookie"] = cookie
    h._send(code, json.dumps(payload, default=str).encode(), "application/json; charset=utf-8",
            cache_control="no-store", extra_headers=headers)


def _session(h) -> auth.Session | None:
    return auth.session_for(_token(h))


def require_operator(h, method: str) -> auth.Session | None:
    """Gate for /api/operator/*. Sends the error response itself and returns None on failure."""
    ip = _ip(h)
    if not auth.network_allowed(ip):
        _send(h, 404, {"error": "not found"})
        return None
    sess = _session(h)
    if not sess:
        _send(h, 401, {"error": "operator sign-in required", "login": "/ops/"})
        return None
    if method != "GET" and h.headers.get("X-Ops-CSRF", "") != sess.csrf:
        _send(h, 403, {"error": "missing or invalid CSRF token"})
        return None
    return sess


def _stepped_up(h, sess: auth.Session) -> bool:
    code = h.headers.get("X-Ops-Step-Up", "")
    return bool(code) and auth.step_up(sess, code)


def handle_ops(h, method: str, raw_path: str, body: dict, ctx: Ctx, login_limiter) -> None:
    parsed = urllib.parse.urlsplit(raw_path)
    path = parsed.path.rstrip("/")
    qs = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query).items()}
    ip = _ip(h)
    if not auth.network_allowed(ip):
        _send(h, 404, {"error": "not found"})
        return

    # --- unauthenticated: login ------------------------------------------------
    if path == "/api/ops/login" and method == "POST":
        allowed, retry = login_limiter.check(ip, category="ops_login")
        if not allowed:
            _send(h, 429, {"error": "too many attempts", "retry_after": retry})
            return
        username = str(body.get("username", ""))[:64]
        try:
            token, sess = auth.login(username, str(body.get("password", "")), str(body.get("totp", "")),
                                     ip, h.headers.get("User-Agent", ""))
        except auth.AuthError as exc:
            audit.record(username or "?", "auth.login", ip=ip, ok=False, reason=str(exc))
            logger.warning("ops_login_failed", username=username, ip=ip, reason=str(exc))
            _send(h, exc.status, {"error": str(exc), "retry_after": round(exc.retry_after)})
            return
        audit.record(sess.username, "auth.login", ip=ip)
        # __Host- cookies must be Secure; browsers still accept them on http://localhost.
        cookie = f"{auth.COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={auth.ABSOLUTE_SECONDS}"
        _send(h, 200, {"username": sess.username, "csrf": sess.csrf, "idle_seconds": auth.IDLE_SECONDS}, cookie)
        return

    sess = require_operator(h, method)
    if not sess:
        return
    actor = sess.username

    def mutate(action: str, fn: Callable[[], Any], *, target: str = "", dangerous: bool = False, **detail: Any) -> None:
        if dangerous and not _stepped_up(h, sess):
            _send(h, 428, {"error": "step-up required: enter a fresh authenticator code", "step_up_required": True})
            return
        try:
            result = fn()
        except PermissionError as exc:
            audit.record(actor, action, target=target, ip=ip, ok=False, reason=str(exc), **detail)
            _send(h, 403, {"error": str(exc)})
            return
        except NotImplementedError as exc:
            _send(h, 501, {"error": str(exc), "not_implemented": True})
            return
        except (KeyError, ValueError) as exc:
            _send(h, 400, {"error": str(exc).strip("'\"")})
            return
        audit.record(actor, action, target=target, ip=ip, **detail)
        _send(h, 200, {"ok": True, "result": result})

    try:
        _route(h, method, path, qs, body, ctx, sess, actor, mutate)
    except Exception:  # noqa: BLE001 - never leak a traceback to the client
        logger.error("ops_route_failed", path=path, method=method, error=traceback.format_exc()[-2000:])
        _send(h, 500, {"error": "internal error (see Errors tab)"})


def _route(h, method, path, qs, body, ctx: Ctx, sess, actor, mutate) -> None:
    get = method == "GET"
    post = method == "POST"

    if path == "/api/ops/logout" and post:
        auth.logout(_token(h))
        audit.record(actor, "auth.logout", ip=sess.ip)
        _send(h, 200, {"ok": True}, f"{auth.COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0; Secure")
    elif path == "/api/ops/session" and get:
        _send(h, 200, {"username": actor, "csrf": sess.csrf, "idle_seconds": auth.IDLE_SECONDS})

    elif path == "/api/ops/overview" and get:
        m = metrics.snapshot()
        _send(h, 200, {
            "operator": ctx.operator_status(),
            "metrics": {k: m[k] for k in ("uptime_seconds", "status", "latency_ms")},
            "errors": logs.error_groups()[:5],
            "log_source": logs.source(),
            "pending_recoveries": len(recovery.listing("pending")),
            "audit_chain": audit.verify(),
        })

    elif path == "/api/ops/logs" and get:
        _send(h, 200, logs.query(level=qs.get("level", ""), service=qs.get("service", ""), q=qs.get("q", ""),
                                 trace_id=qs.get("trace", ""), limit=min(int(qs.get("limit", 200)), 1000)))
    elif path == "/api/ops/errors" and get:
        _send(h, 200, {"source": logs.source(), "groups": logs.error_groups()})
    elif path == "/api/ops/metrics" and get:
        _send(h, 200, metrics.snapshot())

    elif path == "/api/ops/settings" and get:
        _send(h, 200, settings.listing(qs.get("tab", "")))
    elif path == "/api/ops/settings" and post:
        key = str(body.get("key", ""))
        s = settings.lookup(key) if key in {x.key for x in settings.SETTINGS} else None
        mutate("settings.set", lambda: settings.set_value(key, body.get("value"), actor),
               target=key, dangerous=bool(s and s.dangerous), value=body.get("value"))

    elif path == "/api/ops/flags" and get:
        from shadenet.flags import FeatureFlagManager
        _send(h, 200, FeatureFlagManager().get_all_flags())
    elif path == "/api/ops/flags" and post:
        name = str(body.get("name", ""))
        mutate("flags.set", lambda: steward.toggle_flag(name, bool(body.get("enabled"))),
               target=name, enabled=bool(body.get("enabled")))

    elif path == "/api/ops/recovery" and get:
        _send(h, 200, {"requests": recovery.listing(qs.get("status", "")), "evidence_kinds": recovery.EVIDENCE_KINDS})
    elif path == "/api/ops/recovery" and post:
        mutate("recovery.open", lambda: recovery.create(
            str(body.get("account", "")), str(body.get("reason", "")),
            evidence=list(body.get("evidence") or []),
            opened_by=actor), target=str(body.get("account", "")))
    elif path.startswith("/api/ops/recovery/") and post:
        rid, _, verb = path[len("/api/ops/recovery/"):].partition("/")
        if verb == "approve":
            mutate("recovery.approve", lambda: recovery.approve(rid, actor), target=rid, dangerous=True)
        elif verb == "execute":
            mutate("recovery.execute", lambda: recovery.execute(rid, actor), target=rid, dangerous=True)
        elif verb in ("deny", "cancel"):
            mutate(f"recovery.{verb}", lambda: recovery.transition(rid, actor, verb, str(body.get("note", ""))), target=rid)
        else:
            _send(h, 404, {"error": "unknown recovery action"})

    elif path == "/api/ops/venues" and get:
        _send(h, 200, succession.overview(ctx.venues()))
    elif path == "/api/ops/venues/custodians" and post:
        vid, acct = str(body.get("venue_id", "")), str(body.get("account", ""))
        if body.get("remove"):
            mutate("venues.custodian.remove", lambda: succession.remove_custodian(vid, acct, actor), target=vid, account=acct)
        else:
            mutate("venues.custodian.add", lambda: succession.add_custodian(vid, acct, str(body.get("role", "manager")), actor),
                   target=vid, account=acct)
    elif path == "/api/ops/venues/succession" and post:
        verb = str(body.get("action", "open"))
        if verb == "open":
            mutate("venues.succession.open", lambda: succession.open_succession(
                str(body.get("venue_id", "")), str(body.get("add", "")), str(body.get("remove", "")),
                str(body.get("reason", "")), actor), target=str(body.get("venue_id", "")), dangerous=True)
        elif verb == "complete":
            mutate("venues.succession.complete", lambda: succession.complete_succession(str(body.get("id", "")), actor),
                   target=str(body.get("id", "")), dangerous=True)
        else:
            mutate("venues.succession.cancel", lambda: succession.cancel_succession(
                str(body.get("id", "")), actor, str(body.get("note", ""))), target=str(body.get("id", "")))

    elif path == "/api/ops/agegate" and get:
        _send(h, 200, {"mode": settings.get("agegate.mode"), "overrides": agegate.listing(),
                       "enforced": False, "note": "overrides are recorded but not yet consulted by the gate"})
    elif path == "/api/ops/agegate" and post:
        if body.get("revoke"):
            mutate("agegate.revoke", lambda: agegate.revoke(str(body["revoke"]), actor), target=str(body["revoke"]))
        else:
            mutate("agegate.override", lambda: agegate.create(
                str(body.get("subject", "")), str(body.get("kind", "")), str(body.get("reason", "")),
                int(body.get("days", 7)), actor), target=str(body.get("subject", "")), dangerous=True)

    elif path == "/api/ops/security" and get:
        _send(h, 200, {"operators": auth.list_operators(), "sessions": auth.active_sessions(),
                       "allowlist": settings.listing()["env"].get("SHADENET_OPS_ALLOW_CIDRS", ""),
                       "idle_seconds": auth.IDLE_SECONDS, "absolute_seconds": auth.ABSOLUTE_SECONDS})

    elif path == "/api/ops/steward" and post:
        res = steward.run(str(body.get("command", ""))[:500], actor=actor, stepped_up=_stepped_up(h, sess))
        audit.record(actor, "steward.command", command=str(body.get("command", ""))[:200], ok=res["ok"])
        _send(h, 200, res)

    elif path == "/api/ops/audit" and get:
        _send(h, 200, {"chain": audit.verify(), "entries": audit.tail(int(qs.get("limit", 200)),
                                                                       actor=qs.get("actor", ""), action=qs.get("action", ""))})
    else:
        _send(h, 404, {"error": "unknown ops endpoint"})
