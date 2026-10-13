"""Operator authentication: password + TOTP, short sessions, lockout, step-up.

Design:
  - Operators are created only from the server shell (python -m shadenet.ops
    add-operator). There is no web sign-up or bootstrap path to take over.
  - Login needs username + password (scrypt) + a current TOTP code.
  - Sessions are random 256-bit tokens in a __Host- cookie (HttpOnly, Secure,
    SameSite=Strict). Only SHA-256(token) is kept, in memory: a restart signs
    everyone out. Idle timeout 20 min, absolute 8 h.
  - Every state-changing request must echo the per-session CSRF token in
    X-Ops-CSRF.
  - Dangerous actions (key rotation, recovery approval, 21+ overrides, security
    settings) also need a fresh TOTP code in X-Ops-Step-Up. Codes are single-use.
  - Repeated failures lock the username and the client IP with backoff.
  - Optional network allowlist (SHADENET_OPS_ALLOW_CIDRS), e.g. the WireGuard
    subnet, checked before anything else.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import secrets
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from shadenet.ops import now_iso, read_json, write_json

COOKIE = "__Host-shadenet_ops"
IDLE_SECONDS = 20 * 60
ABSOLUTE_SECONDS = 8 * 3600
MAX_FAILURES = 5
LOCK_BASE_SECONDS = 15 * 60
TOTP_STEP = 30
TOTP_WINDOW = 1  # accept the previous/next 30 s step for clock drift

_SCRYPT = {"n": 2**15, "r": 8, "p": 1, "maxmem": 64 * 1024 * 1024}
_OPERATORS_FILE = "operators.json"
_lock = threading.Lock()


# --- password hashing -------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, want = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32,
                            n=int(n), r=int(r), p=int(p), maxmem=_SCRYPT["maxmem"])
        return hmac.compare_digest(dk.hex(), want)
    except (ValueError, TypeError):
        return False


# Burn the same scrypt cost for unknown usernames so timing doesn't reveal which exist.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


# --- TOTP (RFC 6238) ----------------------------------------------------------

def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def totp_now(secret_b32: str, at: float | None = None) -> str:
    return _hotp(secret_b32, int((at or time.time()) // TOTP_STEP))


def totp_uri(username: str, secret_b32: str) -> str:
    return f"otpauth://totp/ShadeNet%20Ops:{username}?secret={secret_b32}&issuer=ShadeNet%20Ops&digits=6&period=30"


def _match_totp(secret_b32: str, code: str, last_counter: int) -> int | None:
    """Return the matched counter if code is valid and newer than last_counter (no replay)."""
    code = (code or "").strip().replace(" ", "")
    if not (len(code) == 6 and code.isdigit()):
        return None
    now = int(time.time() // TOTP_STEP)
    for c in range(now - TOTP_WINDOW, now + TOTP_WINDOW + 1):
        if c > last_counter and hmac.compare_digest(_hotp(secret_b32, c), code):
            return c
    return None


# --- operator records -----------------------------------------------------------

def _operators() -> dict[str, Any]:
    return read_json(_OPERATORS_FILE, {})


def add_operator(username: str, password: str) -> dict:
    if len(password) < 14:
        raise ValueError("operator passwords must be at least 14 characters")
    with _lock:
        ops = _operators()
        if username in ops:
            raise ValueError(f"operator {username!r} already exists")
        secret = new_totp_secret()
        ops[username] = {
            "password": hash_password(password),
            "totp_secret": secret,
            "totp_last_counter": 0,
            "created_at": now_iso(),
            "disabled": False,
        }
        write_json(_OPERATORS_FILE, ops)
    return {"username": username, "totp_secret": secret, "totp_uri": totp_uri(username, secret)}


def set_password(username: str, password: str) -> None:
    if len(password) < 14:
        raise ValueError("operator passwords must be at least 14 characters")
    with _lock:
        ops = _operators()
        ops[username]["password"] = hash_password(password)
        write_json(_OPERATORS_FILE, ops)
    revoke_user_sessions(username)


def reset_totp(username: str) -> dict:
    with _lock:
        ops = _operators()
        secret = new_totp_secret()
        ops[username].update(totp_secret=secret, totp_last_counter=0)
        write_json(_OPERATORS_FILE, ops)
    revoke_user_sessions(username)
    return {"username": username, "totp_secret": secret, "totp_uri": totp_uri(username, secret)}


def set_disabled(username: str, disabled: bool) -> None:
    with _lock:
        ops = _operators()
        ops[username]["disabled"] = disabled
        write_json(_OPERATORS_FILE, ops)
    if disabled:
        revoke_user_sessions(username)


def list_operators() -> list[dict]:
    return [
        {"username": u, "created_at": r.get("created_at"), "disabled": r.get("disabled", False)}
        for u, r in sorted(_operators().items())
    ]


def _consume_totp(username: str, code: str) -> bool:
    """Validate a TOTP code and burn it so it can't be replayed."""
    with _lock:
        ops = _operators()
        rec = ops.get(username)
        if not rec:
            return False
        matched = _match_totp(rec["totp_secret"], code, int(rec.get("totp_last_counter", 0)))
        if matched is None:
            return False
        rec["totp_last_counter"] = matched
        write_json(_OPERATORS_FILE, ops)
        return True


# --- lockout --------------------------------------------------------------------

@dataclass
class _Failures:
    count: int = 0
    locked_until: float = 0.0
    strikes: int = 0  # how many times this key has been locked; doubles the lock


_failures: dict[str, _Failures] = {}


def _locked(key: str) -> float:
    f = _failures.get(key)
    return max(0.0, f.locked_until - time.time()) if f else 0.0


def _fail(key: str) -> None:
    f = _failures.setdefault(key, _Failures())
    f.count += 1
    if f.count >= MAX_FAILURES:
        f.strikes += 1
        f.locked_until = time.time() + LOCK_BASE_SECONDS * (2 ** (f.strikes - 1))
        f.count = 0


def _succeed(key: str) -> None:
    _failures.pop(key, None)


# --- sessions ----------------------------------------------------------------

@dataclass
class Session:
    username: str
    csrf: str
    ip: str
    user_agent: str
    created: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def expired(self) -> bool:
        now = time.time()
        return now - self.last_seen > IDLE_SECONDS or now - self.created > ABSOLUTE_SECONDS


_sessions: dict[str, Session] = {}


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthError(Exception):
    def __init__(self, status: int, message: str, retry_after: float = 0):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def login(username: str, password: str, totp: str, ip: str, user_agent: str = "") -> tuple[str, Session]:
    for key in (f"user:{username}", f"ip:{ip}"):
        wait = _locked(key)
        if wait:
            raise AuthError(429, "too many failed attempts; try again later", retry_after=wait)
    rec = _operators().get(username)
    pw_ok = check_password(password, rec["password"] if rec else _DUMMY_HASH)
    ok = bool(rec) and pw_ok and not rec.get("disabled") and _consume_totp(username, totp)
    if not ok:
        _fail(f"user:{username}")
        _fail(f"ip:{ip}")
        raise AuthError(401, "invalid credentials")
    _succeed(f"user:{username}")
    _succeed(f"ip:{ip}")
    token = secrets.token_urlsafe(32)
    sess = Session(username=username, csrf=secrets.token_urlsafe(24), ip=ip, user_agent=user_agent[:200])
    with _lock:
        _sessions[_digest(token)] = sess
    return token, sess


def session_for(token: str | None) -> Session | None:
    if not token:
        return None
    key = _digest(token)
    with _lock:
        sess = _sessions.get(key)
        if not sess:
            return None
        if sess.expired() or _operators().get(sess.username, {}).get("disabled", True):
            _sessions.pop(key, None)
            return None
        sess.last_seen = time.time()
        return sess


def logout(token: str | None) -> None:
    if token:
        with _lock:
            _sessions.pop(_digest(token), None)


def revoke_user_sessions(username: str) -> int:
    with _lock:
        doomed = [k for k, s in _sessions.items() if s.username == username]
        for k in doomed:
            del _sessions[k]
    return len(doomed)


def active_sessions() -> list[dict]:
    with _lock:
        return [
            {"username": s.username, "ip": s.ip, "user_agent": s.user_agent,
             "created": s.created, "last_seen": s.last_seen}
            for s in _sessions.values() if not s.expired()
        ]


def step_up(sess: Session, code: str) -> bool:
    return _consume_totp(sess.username, code)


# --- network allowlist -------------------------------------------------------

TRUSTED_PROXIES = {"127.0.0.1", "::1"}


def client_ip(peer: str, forwarded_for: str | None) -> str:
    """Peer address, or the left-most X-Forwarded-For hop when the peer is our own Caddy."""
    if peer in TRUSTED_PROXIES and forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return peer


def network_allowed(ip: str) -> bool:
    raw = os.environ.get("SHADENET_OPS_ALLOW_CIDRS", "").strip()
    if not raw:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in ipaddress.ip_network(c.strip(), strict=False) for c in raw.split(",") if c.strip())
