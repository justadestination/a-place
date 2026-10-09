"""Health checks and status page tests for Task 6.8.

Verifies:
  1. Internal health check diagnostics for database, rate limiter, sync mesh, scrapers.
  2. [int] Induced component outage immediately flips status to degraded (HTTP 503).
  3. Outage recovery returns status to operational (HTTP 200).
  4. Public status page serves design-system status dashboard.
"""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

from shadenet.health import (
    check_subsystems,
    set_simulated_failure,
    clear_simulated_failures,
)
from shadenet.nightcal.server import Handler


@pytest.fixture(autouse=True)
def cleanup_health():
    clear_simulated_failures()
    yield
    clear_simulated_failures()


def test_subsystems_healthy_by_default():
    rep = check_subsystems()
    assert rep["status"] == "operational"
    assert rep["healthy"] is True
    assert rep["http_code"] == 200
    assert "database" in rep["components"]
    assert "mesh_sync" in rep["components"]
    assert rep["components"]["database"]["status"] == "operational"


def test_induced_outage_flips_status_to_degraded():
    # Induce database failure
    set_simulated_failure("database", True)
    rep = check_subsystems()
    assert rep["status"] == "degraded"
    assert rep["healthy"] is False
    assert rep["http_code"] == 503
    assert rep["components"]["database"]["status"] == "outage"

    # Recover from failure
    clear_simulated_failures()
    recovered = check_subsystems()
    assert recovered["status"] == "operational"
    assert recovered["healthy"] is True
    assert recovered["http_code"] == 200


@pytest.fixture(scope="module")
def health_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_http_healthz_endpoint_normal_and_outage(health_server):
    # Normal operation -> 200 OK
    req = urllib.request.Request(f"{health_server}/healthz")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["status"] == "operational"

    # Induced outage -> 503 Service Unavailable
    set_simulated_failure("database", True)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 503
        data = json.loads(exc_info.value.read().decode())
        assert data["status"] == "degraded"
        assert data["components"]["database"]["status"] == "outage"
    finally:
        clear_simulated_failures()


def test_http_status_page_html(health_server):
    req = urllib.request.Request(f"{health_server}/status")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "ShadeNet Status" in html
        assert "NightCal Public Web & Agenda" in html
        assert "status-banner" in html
