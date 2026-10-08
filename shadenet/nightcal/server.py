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

    def _events(self, method: str) -> bool:
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path != "/api/events" and not path.startswith("/api/events/"):
            return False
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

    def do_GET(self) -> None:  # noqa: N802
        if self._events("GET"):
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body = (STATIC / "static" / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/catalog.json":
            self._send(200, (STATIC / "catalog.json").read_bytes(), "application/json; charset=utf-8")
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
        body = self._read_json()
        if body is None:
            return

        if path == "/api/action":
            name = str(body.get("name") or "")
            context = body.get("context") if isinstance(body.get("context"), dict) else {}
            if name == "refresh":
                self._refresh()
                return
            if name == "vote":
                with _lock:
                    store = open_store(_db_path())
                    try:
                        record_vote(
                            store,
                            str(context.get("eventId") or ""),
                            str(context.get("direction") or ""),
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
