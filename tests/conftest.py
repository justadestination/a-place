"""Shared fixtures: a live server plus a signed-in operator client.

The ops state (operators, audit, settings) goes to a temp dir so tests never
touch shadenet/data/ops.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


class OpsClient:
    """Minimal HTTP client that carries the operator cookie + CSRF token by hand
    (urllib's cookie jar won't send Secure cookies over plain http)."""

    def __init__(self, base: str):
        self.base = base
        self.cookie = ""
        self.csrf = ""

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None, auth: bool = True):
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        if auth and self.cookie:
            hdrs["Cookie"] = self.cookie
        if auth and self.csrf and method != "GET":
            hdrs.setdefault("X-Ops-CSRF", self.csrf)
        data = json.dumps(body).encode() if body is not None else (b"{}" if method != "GET" else None)
        req = urllib.request.Request(self.base + path, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read() or b"{}"), resp.headers
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, (json.loads(raw) if raw.startswith(b"{") else {}), e.headers

    def login(self, username: str, password: str, totp: str):
        status, data, headers = self.request("POST", "/api/ops/login",
                                             {"username": username, "password": password, "totp": totp}, auth=False)
        if status == 200:
            self.cookie = headers["Set-Cookie"].split(";", 1)[0]
            self.csrf = data["csrf"]
        return status, data


@pytest.fixture(autouse=True)
def _reset_login_throttle():
    """The ops login limiter (10 tries) is shared across tests in one process."""
    yield
    from shadenet.ratelimit import limiter

    for key in [k for k in limiter._buckets if k.startswith("ops_login:")]:
        del limiter._buckets[key]


@pytest.fixture(scope="module")
def ops_env(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("SHADENET_OPS_DIR", str(tmp_path_factory.mktemp("ops")))
    yield
    mp.undo()


@pytest.fixture(scope="module")
def live_server(ops_env):
    from shadenet.nightcal.server import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


OPERATOR = ("test-operator", "correct horse battery staple")


@pytest.fixture(scope="module")
def operator_account(ops_env):
    from shadenet.ops import auth

    return auth.add_operator(*OPERATOR)


def fresh_totp(secret: str, offset_steps: int = 0) -> str:
    import time

    from shadenet.ops import auth

    return auth.totp_now(secret, at=time.time() + offset_steps * auth.TOTP_STEP)


def rearm(username: str = OPERATOR[0]) -> None:
    """TOTP codes are single-use per 30 s step; let a test use the current one again."""
    from shadenet.ops import ops_dir

    path = ops_dir() / "operators.json"
    data = json.loads(path.read_text())
    data[username]["totp_last_counter"] = 0
    path.write_text(json.dumps(data))


@pytest.fixture(scope="module")
def ops_client(live_server, operator_account):
    rearm()
    client = OpsClient(live_server)
    status, data = client.login(OPERATOR[0], OPERATOR[1], fresh_totp(operator_account["totp_secret"]))
    assert status == 200, data
    return client
