"""Serve the night calendar.

The page is a renderer. It does not know about Metropolis until the
A2UI stream arrives. Refreshing listings re-reads the public calendar
and OpenStreetMap, writes the towncrier store, and pushes a new data model.

    python3 -m nightcal.server
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shadenet.nightcal.agent_events import (
    EventWriteError,
    create_event,
    get_event,
    list_events,
    remove_event,
    update_event,
)
from shadenet.nightcal.fill import DB_PATH, fill
from shadenet.nightcal.social import social_status
from shadenet.nightcal.votes import record_vote
from shadenet.nightcal.surface import (
    apply_action,
    default_ui,
    dumps,
    messages_for,
    open_store,
    project,
    update_data_message,
    load_rows,
)
from shadenet.operator import (
    get_operator_status,
    moderate_queue_item,
    rotate_active_key,
)
from shadenet.ratelimit import limiter
from shadenet.health import check_subsystems
from shadenet.auth import default_auth_manager

STATIC = Path(__file__).resolve().parent
PORT = int(os.environ.get("NIGHTCAL_PORT", "8765"))


def _db_path() -> Path:
    raw = os.environ.get("NIGHTCAL_DB")
    return Path(raw) if raw else DB_PATH

_lock = threading.Lock()
_ui = default_ui()
_status = ""


def _model(status: str | None = None) -> dict:
    store = open_store(_db_path())
    try:
        venues, events, hidden = load_rows(store)
        text = _status if status is None else status
        return project(venues, events, _ui, status=text or social_status(store), hidden=hidden)
    finally:
        store.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json; charset=utf-8")

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "expected JSON"})
            return None
        if not isinstance(body, dict):
            self._json(400, {"error": "expected a JSON object"})
            return None
        return body

    def _check_rate_limit(self, category: str = "api") -> bool:
        client_ip = self.client_address[0] if getattr(self, "client_address", None) else "127.0.0.1"
        auth = self.headers.get("Authorization") or self.headers.get("X-Operator-Token") or ""
        allowed, retry_after = limiter.check(client_ip, category=category, auth_token=auth)
        if not allowed:
            self.send_response(429)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Retry-After", str(retry_after))
            self.send_header("Cache-Control", "no-store")
            payload = json.dumps({
                "error": "Rate limit exceeded. Please back off.",
                "code": "ERR_RATE_LIMITED",
                "retry_after": retry_after,
                "next_step": f"Wait {retry_after} seconds before retrying this request.",
            }).encode()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return False
        return True

    def _events(self, method: str) -> bool:
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path != "/api/events" and not path.startswith("/api/events/"):
            return False
        cat = "submissions" if method in {"POST", "PATCH", "DELETE"} else "api"
        if not self._check_rate_limit(cat):
            return True
        body: dict = {}
        if method in {"POST", "PATCH", "DELETE"}:
            read = self._read_json()
            if read is None:
                return True
            body = read
        query = urllib.parse.parse_qs(parsed.query)
        try:
            with _lock:
                store = open_store(_db_path())
                try:
                    code, payload = _dispatch_events(method, path, query, body, store)
                finally:
                    store.close()
        except EventWriteError as exc:
            self._json(exc.status, {"error": exc.message})
            return True
        except Exception:  # noqa: BLE001 - the agent gets a failure, the traceback stays on stderr
            traceback.print_exc()
            self._json(500, {"error": "the show was not saved"})
            return True
        self._json(code, payload)
        return True

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if self._events("GET"):
            return
        path = self.path.split("?", 1)[0]
        if path in ("/healthz", "/api/health"):
            rep = check_subsystems(_db_path())
            self._json(rep["http_code"], rep)
            return
        if path in ("/status", "/status/", "/status.html"):
            st_page = STATIC / "static" / "status.html"
            if st_page.is_file():
                self._send(200, st_page.read_bytes(), "text/html; charset=utf-8")
                return
        if path.startswith("/api/"):
            cat = "operator" if path.startswith("/api/operator/") else "api"
            if not self._check_rate_limit(cat):
                return
        if path in ("/", "/index.html"):
            body = (STATIC / "static" / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/catalog.json":
            self._send(200, (STATIC / "catalog.json").read_bytes(), "application/json; charset=utf-8")
            return
        static_file = STATIC / "static" / path.lstrip("/")
        if static_file.is_file() and not path.startswith("/api/"):
            mime = "text/plain"
            if path.endswith(".js"):
                mime = "application/javascript; charset=utf-8"
            elif path.endswith(".css"):
                mime = "text/css; charset=utf-8"
            elif path.endswith(".html"):
                mime = "text/html; charset=utf-8"
            elif path.endswith(".json"):
                mime = "application/json; charset=utf-8"
            elif path.endswith(".webmanifest"):
                mime = "application/manifest+json"
            elif path.endswith(".svg"):
                mime = "image/svg+xml"
            self._send(200, static_file.read_bytes(), mime)
            return
        if path == "/api/surface":
            with _lock:
                store = open_store(_db_path())
                try:
                    payload = dumps(messages_for(store, _ui, status=_status)).encode()
                finally:
                    store.close()
            self._send(200, payload, "application/jsonl; charset=utf-8")
            return
        if path in ("/operator", "/operator/", "/operator.html"):
            op_page = STATIC / "static" / "operator.html"
            if op_page.is_file():
                self._send(200, op_page.read_bytes(), "text/html; charset=utf-8")
                return
        if path == "/api/operator/status":
            with _lock:
                store = open_store(_db_path())
                try:
                    payload = get_operator_status(store)
                finally:
                    store.close()
            self._json(200, payload)
            return
        if path.startswith("/api/auth/"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if path == "/api/auth/register/options":
                u = qs.get("username", [""])[0]
                d = qs.get("displayName", [None])[0]
                try:
                    res = default_auth_manager.generate_registration_options(u, d)
                    self._json(200, res)
                except ValueError as e:
                    self._json(400, {"error": str(e)})
                return
            if path == "/api/auth/login/options":
                u = qs.get("username", [None])[0]
                res = default_auth_manager.generate_login_options(u)
                self._json(200, res)
                return
            if path == "/api/auth/session":
                auth_hdr = self.headers.get("Authorization", "")
                token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else qs.get("session", [""])[0]
                sess = default_auth_manager.validate_session(token) if token else None
                if sess:
                    self._json(200, {"authenticated": True, "session": sess})
                else:
                    self._json(401, {"authenticated": False, "error": "Not authenticated or session expired"})
                return
            if path == "/api/auth/sessions":
                auth_hdr = self.headers.get("Authorization", "")
                token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else qs.get("session", [""])[0]
                if not token:
                    token = self.headers.get("X-Session-Token", "")
                if not token:
                    self._json(401, {"authenticated": False, "error": "Missing session token"})
                    return
                try:
                    sessions = default_auth_manager.list_sessions(token)
                    self._json(200, {"authenticated": True, "sessions": sessions})
                except Exception as e:
                    self._json(401, {"authenticated": False, "error": str(e)})
                return


        if path == "/api/model":
            with _lock:
                message = update_data_message(_model())
            self._send(200, json.dumps(message).encode(), "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        global _ui, _status
        if self._events("POST"):
            return
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            cat = "operator" if path.startswith("/api/operator/") else "submissions"
            if not self._check_rate_limit(cat):
                return
        body = self._read_json()
        if body is None:
            return

        if path.startswith("/api/auth/"):
            if path == "/api/auth/register/verify":
                try:
                    res = default_auth_manager.verify_registration(
                        username=str(body.get("username", "")),
                        credential_id=str(body.get("credentialId", "")),
                        public_key=str(body.get("publicKey", "")),
                        client_challenge=str(body.get("challenge", "")),
                        display_name=body.get("displayName"),
                        device_nickname=str(body.get("nickname", "Primary Authenticator")),
                    )
                    self._json(200, res)
                except Exception as e:
                    self._json(400, {"error": str(e)})
                return
            if path == "/api/auth/login/verify":
                try:
                    res = default_auth_manager.verify_login(
                        credential_id=str(body.get("credentialId", "")),
                        client_challenge=str(body.get("challenge", "")),
                        authenticator_data=str(body.get("authenticatorData", "")),
                        signature=str(body.get("signature", "")),
                        device_info=str(body.get("deviceInfo", "Web Client")),
                    )
                    self._json(200, res)
                except Exception as e:
                    self._json(400, {"error": str(e)})
                return
            if path == "/api/auth/login/fallback":
                try:
                    res = default_auth_manager.login_with_password(
                        username=str(body.get("username", "")),
                        secret=str(body.get("password", "") or body.get("secret", "")),
                    )
                    self._json(200, res)
                except Exception as e:
                    self._json(401, {"error": str(e)})
                return
            if path == "/api/auth/register/fallback":
                try:
                    res = default_auth_manager.register_with_password(
                        username=str(body.get("username", "")),
                        secret=str(body.get("password", "") or body.get("secret", "")),
                        display_name=body.get("displayName"),
                    )
                    self._json(200, res)
                except Exception as e:
                    self._json(400, {"error": str(e)})
                return
            if path == "/api/auth/logout":
                token = str(body.get("sessionToken", "") or body.get("session_token", ""))
                if not token:
                    auth_hdr = self.headers.get("Authorization", "")
                    token = auth_hdr.replace("Bearer ", "").strip()
                revoked = default_auth_manager.logout(token) if token else False
                self._json(200, {"success": True, "revoked": revoked})
                return
            if path == "/api/auth/sessions/revoke":
                auth_hdr = self.headers.get("Authorization", "")
                token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else str(body.get("sessionToken", "") or body.get("session_token", ""))
                if not token:
                    token = self.headers.get("X-Session-Token", "")
                target_id = str(body.get("sessionId", "") or body.get("session_id", "") or body.get("targetSessionId", ""))
                if not token or not target_id:
                    self._json(400, {"error": "Both session token and target sessionId are required"})
                    return
                try:
                    revoked = default_auth_manager.revoke_session(token, target_id)
                    self._json(200, {"success": True, "revoked": revoked, "sessionId": target_id})
                except Exception as e:
                    self._json(401, {"error": str(e)})
                return
            if path == "/api/auth/sessions/revoke-others":
                auth_hdr = self.headers.get("Authorization", "")
                token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else str(body.get("sessionToken", "") or body.get("session_token", ""))
                if not token:
                    token = self.headers.get("X-Session-Token", "")
                if not token:
                    self._json(401, {"error": "Missing session token"})
                    return
                try:
                    count = default_auth_manager.revoke_all_other_sessions(token)
                    self._json(200, {"success": True, "revoked_count": count})
                except Exception as e:
                    self._json(401, {"error": str(e)})
                return


        if path == "/api/operator/moderation":
            item_id = str(body.get("itemId") or body.get("item_id") or "")
            action = str(body.get("action") or "")
            note = str(body.get("note") or "")
            try:
                res = moderate_queue_item(item_id, action, note)
                self._json(200, res)
            except (ValueError, KeyError) as e:
                self._json(400, {"error": str(e), "code": "ERR_BAD_REQUEST"})
            return

        if path == "/api/operator/keys/rotate":
            op_id = str(body.get("operator") or "operator-console")
            res = rotate_active_key(op_id)
            self._json(200, res)
            return

        if path == "/api/action":
            name = str(body.get("name") or "")
            context = body.get("context") if isinstance(body.get("context"), dict) else {}
            if name == "refresh":
                self._refresh()
                return
            if name == "vote":
                event_id = str(context.get("eventId") or context.get("event_id") or "")
                direction = str(context.get("direction") or "")
                steward_id = str(context.get("steward_id") or context.get("stewardId") or "").strip()
                verified = bool(context.get("verified", True))
                with _lock:
                    store = open_store(_db_path())
                    try:
                        record_vote(
                            store,
                            event_id,
                            direction,
                            steward_id=steward_id or None,
                            verified=verified,
                        )
                    finally:
                        store.close()
                    message = update_data_message(_model())
                self._json(200, message)
                return
            with _lock:
                _ui = apply_action(_ui, name, context)
                message = update_data_message(_model())
            self._json(200, message)
            return

        if path == "/api/refresh":
            self._refresh()
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_PATCH(self) -> None:  # noqa: N802
        if not self._events("PATCH"):
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._events("DELETE"):
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def _refresh(self) -> None:
        global _status
        try:
            summary = fill(_db_path())
        except Exception as exc:  # noqa: BLE001 - surface the failure, don't pretend it worked
            traceback.print_exc()
            with _lock:
                _status = f"Listings were not updated. {exc.__class__.__name__}."
                message = update_data_message(_model())
            self._json(200, message)
            return
        rooms = summary.get("rooms") or 0
        cards = (summary.get("shows") or {}).get("cards") or 0
        note = ((summary.get("social") or {}).get("note") or "").strip()
        with _lock:
            if summary.get("room_error"):
                _status = f"Shows updated ({cards}). Room map was not: the gazetteer did not answer."
            else:
                _status = f"Updated. {rooms} rooms, {cards} listings."
            if note:
                _status = f"{_status} {note}"
            message = update_data_message(_model())
        self._json(200, message)


def _dispatch_events(method: str, path: str, query: dict, body: dict, store) -> tuple[int, dict]:
    if path == "/api/events" and method == "GET":
        return 200, list_events(store, query)
    if path == "/api/events" and method == "POST":
        _action, payload = create_event(store, body)
        return (201 if payload["action"] == "created" else 200), payload
    if not path.startswith("/api/events/"):
        return 404, {"error": "not found"}
    event_id = urllib.parse.unquote(path[len("/api/events/"):])
    if "/" in event_id or not event_id:
        return 404, {"error": "not found"}
    if method == "GET":
        return 200, get_event(store, event_id)
    if method == "PATCH":
        return 200, update_event(store, event_id, body)
    if method == "DELETE":
        return 200, remove_event(store, event_id, body)
    return 405, {"error": "that method is not used on shows"}


def _bind_hosts() -> list[str]:
    raw = os.environ.get("NIGHTCAL_HOST", "127.0.0.1")
    hosts = [part.strip() for part in raw.split(",") if part.strip()]
    return hosts or ["127.0.0.1"]


def main() -> int:
    path = _db_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    hosts = _bind_hosts()
    servers = [ThreadingHTTPServer((host, PORT), Handler) for host in hosts]
    for host in hosts:
        print(f"night calendar  http://{host}:{PORT}", flush=True)
    for extra in servers[1:]:
        threading.Thread(target=extra.serve_forever, name="nightcal", daemon=True).start()
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
