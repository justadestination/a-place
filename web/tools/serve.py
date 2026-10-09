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
        if self.path.startswith("/api/"):
            return self._proxy("GET")
        return super().do_GET()

    def do_POST(self):
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
