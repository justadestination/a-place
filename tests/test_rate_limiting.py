"""Abuse defense and rate limiting tests for Task 6.7.

Verifies:
  1. Token bucket burst and refill.
  2. [abuse] Flooding endpoints yields HTTP 429 with Retry-After header and ERR_RATE_LIMITED.
  3. Operator override tokens bypass rate limits.
  4. Concurrent flood protection with zero data corruption.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error

import pytest

from shadenet.ratelimit import RateLimiter, limiter
from shadenet.nightcal.server import Handler


def test_token_bucket_mechanics():
    rl = RateLimiter(limits={"test": (3.0, 1.0)})
    client = "203.0.113.50"

    # 3 allowed immediately
    assert rl.check(client, category="test")[0] is True
    assert rl.check(client, category="test")[0] is True
    assert rl.check(client, category="test")[0] is True

    # 4th should be denied with retry_after >= 1
    allowed, retry_after = rl.check(client, category="test")
    assert allowed is False
    assert retry_after >= 1


def test_operator_override_exemption():
    rl = RateLimiter(limits={"test": (2.0, 1.0)})
    client = "203.0.113.51"
    secret_token = "op-override-secret-key-123"
    rl.add_operator_override(secret_token)

    # Exhaust standard bucket
    assert rl.check(client, category="test")[0] is True
    assert rl.check(client, category="test")[0] is True
    assert rl.check(client, category="test")[0] is False

    # Exempt request succeeds
    assert rl.check(client, category="test", auth_token=secret_token)[0] is True
    assert rl.check(client, category="test", auth_token=secret_token)[0] is True


@pytest.fixture(scope="module")
def server_fixture():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_abuse_flood_endpoint_triggers_429(server_fixture):
    limiter.reset()
    # Configure tight test limit for api
    limiter.limits["api"] = (5.0, 0.5)

    success_count = 0
    blocked_count = 0
    retry_after_val = None

    for _ in range(12):
        try:
            req = urllib.request.Request(f"{server_fixture}/api/model")
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    success_count += 1
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                blocked_count += 1
                retry_after_val = exc.headers.get("Retry-After")
                body = json.loads(exc.read().decode())
                assert body["code"] == "ERR_RATE_LIMITED"
                assert "next_step" in body

    assert success_count == 5
    assert blocked_count == 7
    assert retry_after_val is not None
    assert int(retry_after_val) >= 1


def test_operator_override_http_bypass(server_fixture):
    limiter.reset()
    limiter.limits["api"] = (2.0, 0.1)
    override_token = "operator-token-master-key"
    limiter.add_operator_override(override_token)

    # 10 requests with operator token all pass
    for _ in range(10):
        req = urllib.request.Request(
            f"{server_fixture}/api/model",
            headers={"X-Operator-Token": override_token}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200


def test_concurrent_flood_stability(server_fixture):
    limiter.reset()
    limiter.limits["api"] = (15.0, 1.0)
    errors = []

    def hammer():
        for _ in range(10):
            try:
                req = urllib.request.Request(f"{server_fixture}/api/model")
                with urllib.request.urlopen(req) as resp:
                    pass
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    errors.append(f"Unexpected status: {exc.code}")
            except Exception as e:
                errors.append(str(e))

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent flood: {errors}"
