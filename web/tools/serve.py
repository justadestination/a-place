#!/usr/bin/env python3
"""Local dev server for web/: static files plus /api/* proxied to nightcal.

    python3 web/tools/serve.py [--port 8080] [--api http://127.0.0.1:8765]

Production does the same with Caddy (see web/deploy/Caddyfile.snippet).
If the API is down, /api/* answers 502 and the front-end falls back to
web/data/sample-model.json, so the site still renders.
"""

from __future__ import annotations

import argparse
import http.server
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    api = "http://127.0.0.1:8765"
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml"}

    def log_message(self, fmt, *args):  # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _proxy(self, method: str):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        for name in ("Authorization", "X-Session-Token", "X-ZKP-Token"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        req = urllib.request.Request(self.api + self.path, data=body, method=method, headers=headers)
        try:
            try:
                res = urllib.request.urlopen(req, timeout=10)
            except urllib.error.HTTPError as res:
                pass
            with res:
                data = res.read()
                status = getattr(res, "status", None) or getattr(res, "code", 502)
                self.send_response(status)
                self.send_header("Content-Type", res.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except (urllib.error.URLError, OSError):
            msg = b'{"error":"nightcal API unavailable"}'
            try:
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        if self.path.startswith("/api/venues/edit"):
            try:
                import sys
                import json
                from pathlib import Path
                ROOT = Path(__file__).resolve().parent.parent.parent
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from shadenet.nightcal.venue_edits import get_overlay
                import urllib.parse
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                venue_id = qs.get("id", [""])[0]
                data = json.dumps(get_overlay(venue_id)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                pass
        if self.path.startswith("/api/chat/") or self.path.startswith("/_matrix/"):
            try:
                import sys
                import json
                import urllib.parse
                from pathlib import Path
                ROOT = Path(__file__).resolve().parent.parent.parent
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from shadenet.chat import (
                    DOMAIN as CHAT_DOMAIN,
                    EXTERNAL_MATRIX_URL,
                    get_db as get_chat_db,
                    get_pseudonym_for_user,
                    list_rooms as list_chat_rooms,
                    get_room_messages,
                )
                db_path = ROOT / "shadenet" / "data" / "shadenet.db"
                conn = get_chat_db(db_path)
                path = self.path.split("?", 1)[0]
                if path == "/_matrix/client/versions":
                    data = json.dumps({"versions": ["v1.1", "v1.5", "v1.6"], "unstable_features": {}}).encode()
                elif path in ("/_matrix/client/v3/publicRooms", "/api/chat/rooms"):
                    rooms = list_chat_rooms(conn)
                    if path.startswith("/_matrix/"):
                        chunk = [{"room_id": r["room_id"], "name": r["name"], "topic": r["topic"], "canonical_alias": r["alias"], "num_joined_members": 2} for r in rooms]
                        data = json.dumps({"chunk": chunk, "total_room_count_estimate": len(chunk)}).encode()
                    else:
                        data = json.dumps({"rooms": rooms, "server": CHAT_DOMAIN, "external_matrix_url": EXTERNAL_MATRIX_URL}).encode()
                elif path == "/api/chat/auth":
                    auth_hdr = self.headers.get("Authorization", "") or self.headers.get("X-Session-Token", "")
                    token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else auth_hdr.strip()
                    user_id = "user_" + token[:8] if token else "anon_patron"
                    pseudonym = get_pseudonym_for_user(conn, user_id)
                    data = json.dumps({"pseudonym": pseudonym, "server": CHAT_DOMAIN, "external_matrix_url": EXTERNAL_MATRIX_URL, "matrix_user_id": pseudonym}).encode()
                elif "/messages" in path:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    limit = int(qs.get("limit", [50])[0])
                    since = int(qs.get("since", [0])[0])
                    parts = path.split("/")
                    room_id = urllib.parse.unquote(parts[parts.index("rooms") + 1])
                    auth_hdr = self.headers.get("Authorization", "") or self.headers.get("X-Session-Token", "")
                    token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else auth_hdr.strip()
                    user_id = "user_" + token[:8] if token else "anon_patron"
                    viewer = get_pseudonym_for_user(conn, user_id)
                    try:
                        msgs = get_room_messages(conn, room_id, limit=limit, since_ts=since, viewer=viewer)
                    except PermissionError as exc:
                        data = json.dumps({"error": str(exc)}).encode()
                        self.send_response(403)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    if path.startswith("/_matrix/"):
                        chunk = [{"event_id": m["event_id"], "sender": m["sender"], "origin_server_ts": m["timestamp"], "type": "m.room.message", "content": {"body": m["content"], "msgtype": "m.text"}} for m in msgs]
                        data = json.dumps({"chunk": chunk, "start": str(since), "end": str(msgs[-1]["timestamp"] if msgs else since)}).encode()
                    else:
                        data = json.dumps({"room_id": room_id, "messages": msgs}).encode()
                else:
                    data = b"{}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                pass
        if self.path.startswith("/api/"):
            return self._proxy("GET")
        return super().do_GET()

    def _json(self, status: int, payload: dict) -> None:
        import json
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _accord_read(self) -> None:
        import json
        import sys
        length = int(self.headers.get("Content-Length") or 0)
        if length > 65536:
            self._json(400, {"ok": False, "message": "I have not read the room."})
            return
        root = Path(__file__).resolve().parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from shadenet.serendipilyst.intents import hear_side
            from shadenet.serendipilyst.store import FlagError
            body = json.loads(self.rfile.read(length) or b"{}")
            heard = hear_side(
                body.get("messages") or [],
                side=str(body.get("side") or ""),
                buyer=str(body.get("buyer") or ""),
                seller=str(body.get("seller") or ""),
            )
        except FlagError as exc:
            self._json(400, {"ok": False, "message": str(exc)})
            return
        except Exception:
            self._json(400, {"ok": False, "message": "I have not read the room."})
            return
        self._json(200, {"ok": True, **heard})

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/api/accord-read":
            self._accord_read()
            return
        if self.path.startswith("/api/chat/") or self.path.startswith("/_matrix/"):
            try:
                import sys
                import json
                import urllib.parse
                from pathlib import Path
                ROOT = Path(__file__).resolve().parent.parent.parent
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from shadenet.chat import (
                    get_db as get_chat_db,
                    get_pseudonym_for_user,
                    post_message as post_chat_message,
                    moderate_message as moderate_chat_message,
                )
                db_path = ROOT / "shadenet" / "data" / "shadenet.db"
                conn = get_chat_db(db_path)
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else {}
                path = self.path.split("?", 1)[0]
                auth_hdr = self.headers.get("Authorization", "") or self.headers.get("X-Session-Token", "")
                token = auth_hdr.replace("Bearer ", "").strip() if "Bearer " in auth_hdr else auth_hdr.strip()
                user_id = "user_" + token[:8] if token else "anon_patron"
                pseudonym = get_pseudonym_for_user(conn, user_id)
                if "/send" in path:
                    parts = path.split("/")
                    room_id = urllib.parse.unquote(parts[parts.index("rooms") + 1])
                    raw = body.get("content")
                    content = str(raw.get("body") if isinstance(raw, dict) else (raw or body.get("body") or ""))
                    try:
                        res = post_chat_message(conn, room_id, pseudonym, content)
                        data = json.dumps(res).encode()
                        status = 200
                    except PermissionError as exc:
                        data = json.dumps({"error": str(exc)}).encode()
                        status = 403
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                elif path == "/api/chat/moderate":
                    op = str(body.get("op") or "redact")
                    target = str(body.get("target_id") or body.get("message_id") or body.get("pseudonym") or "")
                    res = moderate_chat_message(conn, "operator", op, target)
                    data = json.dumps(res).encode()
                else:
                    data = b"{}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                pass
        if self.path.startswith("/api/venues/edit"):
            try:
                import sys
                import json
                from pathlib import Path
                ROOT = Path(__file__).resolve().parent.parent.parent
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))
                from shadenet.nightcal.venue_edits import update_info, add_event, add_blurb, get_overlay
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else {}
                venue_id = body.get("venue_id", "")
                op = body.get("op", "")
                owner = {"id": "dev_user", "username": "dev"}
                if op == "info":
                    update_info(venue_id, owner, body.get("info", {}))
                elif op == "event":
                    add_event(venue_id, owner, body.get("event", {}))
                elif op == "blurb":
                    add_blurb(venue_id, owner, body.get("title", ""), body.get("content", ""))
                data = json.dumps(get_overlay(venue_id)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                pass
        if self.path.startswith("/api/"):
            return self._proxy("POST")
        self.send_error(405)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--api", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    Handler.api = args.api.rstrip("/")
    server = http.server.ThreadingHTTPServer((args.host, args.port), partial(Handler, directory=str(WEB)))
    print(f"nightcal web  http://{args.host}:{args.port}  (api -> {Handler.api})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
