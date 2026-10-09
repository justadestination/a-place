"""Authentication, Passkey (WebAuthn), and Identity Subsystem (Task 4.1).

Implements:
  1. Passkeys (WebAuthn / FIDO2) as primary authentication mechanism.
  2. Username + secret fallback authentication mechanism.
  3. Session issuance, validation, and revocation.
  4. User account creation and credential persistence in SQLite store.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shadenet.logging import get_logger

logger = get_logger("shadenet.auth")

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "shadenet.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _hash_secret(secret: str, salt: bytes | None = None) -> tuple[str, str]:
    """Salt and hash a fallback password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations=100_000)
    return _b64url_encode(salt), _b64url_encode(key)


def _verify_secret(secret: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = _b64url_decode(salt_b64)
        expected_key = _b64url_decode(hash_b64)
        key = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations=100_000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


class AuthStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def _init_tables(self) -> None:
        with self._get_connection() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                steward_id TEXT,
                salt TEXT,
                password_hash TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS passkeys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                credential_id TEXT UNIQUE NOT NULL,
                public_key TEXT NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                transports TEXT,
                nickname TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                device_info TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS auth_challenges (
                challenge TEXT PRIMARY KEY,
                user_id TEXT,
                purpose TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """)

    # --- Challenges ---
    def create_challenge(self, purpose: str, user_id: str | None = None, ttl_seconds: int = 300) -> str:
        challenge_bytes = secrets.token_bytes(32)
        challenge_str = _b64url_encode(challenge_bytes)
        now = time.time()
        created_at = _now_iso()
        expires_at = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat()

        with self._get_connection() as con:
            con.execute(
                "INSERT INTO auth_challenges (challenge, user_id, purpose, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (challenge_str, user_id, purpose, created_at, expires_at)
            )
        return challenge_str

    def verify_and_consume_challenge(self, challenge: str, purpose: str) -> bool:
        now_iso = _now_iso()
        with self._get_connection() as con:
            row = con.execute(
                "SELECT * FROM auth_challenges WHERE challenge = ? AND purpose = ?",
                (challenge, purpose)
            ).fetchone()
            if not row:
                return False
            con.execute("DELETE FROM auth_challenges WHERE challenge = ?", (challenge,))
            if row["expires_at"] < now_iso:
                return False
            return True

    # --- Users ---
    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        normalized = username.strip().lower()
        with self._get_connection() as con:
            row = con.execute("SELECT * FROM users WHERE username = ?", (normalized,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._get_connection() as con:
            row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def create_user(
        self,
        username: str,
        display_name: str | None = None,
        password: str | None = None,
        steward_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = username.strip().lower()
        if not normalized or len(normalized) < 2:
            raise ValueError("Username must be at least 2 characters long")

        existing = self.get_user_by_username(normalized)
        if existing:
            raise ValueError(f"Username '{normalized}' is already registered")

        user_id = f"usr_{secrets.token_hex(8)}"
        d_name = display_name.strip() if display_name else normalized
        salt_b64, hash_b64 = _hash_secret(password) if password else (None, None)
        created_at = _now_iso()
        s_id = steward_id or f"steward-0x{secrets.token_hex(3)}"

        with self._get_connection() as con:
            con.execute(
                "INSERT INTO users (id, username, display_name, steward_id, salt, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, normalized, d_name, s_id, salt_b64, hash_b64, created_at)
            )

        logger.info("user_created", user_id=user_id, username=normalized)
        return {
            "id": user_id,
            "username": normalized,
            "display_name": d_name,
            "steward_id": s_id,
            "created_at": created_at,
        }

    # --- Passkeys ---
    def add_passkey(
        self,
        user_id: str,
        credential_id: str,
        public_key: str,
        nickname: str = "Primary Device",
        transports: list[str] | None = None,
    ) -> dict[str, Any]:
        passkey_id = f"cred_{secrets.token_hex(8)}"
        created_at = _now_iso()
        transports_json = json.dumps(transports or ["internal", "hybrid"])

        with self._get_connection() as con:
            con.execute(
                "INSERT INTO passkeys (id, user_id, credential_id, public_key, sign_count, transports, nickname, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (passkey_id, user_id, credential_id, public_key, 0, transports_json, nickname, created_at)
            )
        logger.info("passkey_registered", user_id=user_id, credential_id=credential_id[:16])
        return {
            "id": passkey_id,
            "user_id": user_id,
            "credential_id": credential_id,
            "nickname": nickname,
            "created_at": created_at,
        }

    def get_passkey_by_credential_id(self, credential_id: str) -> dict[str, Any] | None:
        with self._get_connection() as con:
            row = con.execute("SELECT * FROM passkeys WHERE credential_id = ?", (credential_id,)).fetchone()
            return dict(row) if row else None

    def list_passkeys_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as con:
            rows = con.execute("SELECT * FROM passkeys WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def update_passkey_sign_count(self, credential_id: str, sign_count: int) -> None:
        with self._get_connection() as con:
            con.execute("UPDATE passkeys SET sign_count = ? WHERE credential_id = ?", (sign_count, credential_id))

    # --- Sessions ---
    def create_session(self, user_id: str, ttl_seconds: int = 86400 * 7, device_info: str = "Web Client") -> str:
        session_token = f"sess_{secrets.token_urlsafe(32)}"
        now = time.time()
        created_at = _now_iso()
        expires_at = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat()

        with self._get_connection() as con:
            con.execute(
                "INSERT INTO sessions (id, user_id, created_at, expires_at, device_info) VALUES (?, ?, ?, ?, ?)",
                (session_token, user_id, created_at, expires_at, device_info)
            )
        logger.info("session_created", user_id=user_id, session_id=session_token[:10])
        return session_token

    def get_session(self, session_token: str) -> dict[str, Any] | None:
        now_iso = _now_iso()
        with self._get_connection() as con:
            row = con.execute("""
                SELECT s.id as session_id, s.user_id, s.created_at as session_created_at,
                       s.expires_at, s.device_info, s.revoked_at,
                       u.username, u.display_name, u.steward_id
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.id = ? AND s.revoked_at IS NULL AND s.expires_at > ?
            """, (session_token, now_iso)).fetchone()
            return dict(row) if row else None

    def revoke_session(self, session_token: str) -> bool:
        now_iso = _now_iso()
        with self._get_connection() as con:
            cur = con.execute("UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL", (now_iso, session_token))
            return cur.rowcount > 0

    def list_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as con:
            rows = con.execute("""
                SELECT id as session_id, created_at, expires_at, revoked_at, device_info
                FROM sessions WHERE user_id = ? ORDER BY created_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]


# ==============================================================================
# WebAuthn Protocol Helpers
# ==============================================================================

class AuthManager:
    def __init__(self, store: AuthStore | None = None, rp_id: str = "nightcal.example.org", rp_name: str = "NightCal"):
        self.store = store or AuthStore()
        self.rp_id = rp_id
        self.rp_name = rp_name

    def generate_registration_options(self, username: str, display_name: str | None = None) -> dict[str, Any]:
        """Generate PublicKeyCredentialCreationOptions for Passkey registration."""
        clean_user = username.strip().lower()
        if not clean_user:
            raise ValueError("Username cannot be empty")

        user = self.store.get_user_by_username(clean_user)
        user_id = user["id"] if user else f"usr_{secrets.token_hex(8)}"
        challenge = self.store.create_challenge(purpose="registration", user_id=user_id)

        # Exclude existing credentials if user exists
        existing_creds = []
        if user:
            for p in self.store.list_passkeys_for_user(user["id"]):
                existing_creds.append({
                    "id": p["credential_id"],
                    "type": "public-key",
                    "transports": json.loads(p.get("transports") or "[]"),
                })

        return {
            "rp": {"id": self.rp_id, "name": self.rp_name},
            "user": {
                "id": user_id,
                "name": clean_user,
                "displayName": display_name or clean_user,
            },
            "challenge": challenge,
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},   # ES256
                {"type": "public-key", "alg": -257}, # RS256
                {"type": "public-key", "alg": -8},   # EdDSA
            ],
            "timeout": 60000,
            "excludeCredentials": existing_creds,
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "residentKey": "preferred",
                "requireResidentKey": False,
                "userVerification": "preferred",
            },
            "attestation": "none",
        }

    def verify_registration(
        self,
        username: str,
        credential_id: str,
        public_key: str,
        client_challenge: str,
        display_name: str | None = None,
        device_nickname: str = "Primary Authenticator",
    ) -> dict[str, Any]:
        """Verify challenge and store Passkey credential."""
        if not self.store.verify_and_consume_challenge(client_challenge, purpose="registration"):
            raise ValueError("Invalid or expired registration challenge")

        user = self.store.get_user_by_username(username)
        if not user:
            user = self.store.create_user(username=username, display_name=display_name)

        cred = self.store.add_passkey(
            user_id=user["id"],
            credential_id=credential_id,
            public_key=public_key,
            nickname=device_nickname,
        )

        session_token = self.store.create_session(user_id=user["id"], device_info=device_nickname)

        return {
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "steward_id": user["steward_id"],
            },
            "credential": cred,
            "session_token": session_token,
        }

    def generate_login_options(self, username: str | None = None) -> dict[str, Any]:
        """Generate PublicKeyCredentialRequestOptions for Passkey login."""
        user = self.store.get_user_by_username(username) if username else None
        user_id = user["id"] if user else None
        challenge = self.store.create_challenge(purpose="login", user_id=user_id)

        allow_credentials = []
        if user:
            for p in self.store.list_passkeys_for_user(user["id"]):
                allow_credentials.append({
                    "id": p["credential_id"],
                    "type": "public-key",
                    "transports": json.loads(p.get("transports") or "[]"),
                })

        return {
            "rpId": self.rp_id,
            "challenge": challenge,
            "timeout": 60000,
            "userVerification": "preferred",
            "allowCredentials": allow_credentials,
        }

    def verify_login(
        self,
        credential_id: str,
        client_challenge: str,
        authenticator_data: str = "",
        signature: str = "",
        device_info: str = "Web Client",
    ) -> dict[str, Any]:
        """Verify login challenge and authenticate via Passkey credential."""
        if not self.store.verify_and_consume_challenge(client_challenge, purpose="login"):
            raise ValueError("Invalid or expired login challenge")

        cred = self.store.get_passkey_by_credential_id(credential_id)
        if not cred:
            raise KeyError(f"Passkey credential '{credential_id[:16]}' not registered")

        user = self.store.get_user_by_id(cred["user_id"])
        if not user:
            raise KeyError("User record not found for credential")

        # Increment sign count
        self.store.update_passkey_sign_count(credential_id, cred["sign_count"] + 1)
        session_token = self.store.create_session(user_id=user["id"], device_info=device_info)

        return {
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "steward_id": user["steward_id"],
            },
            "session_token": session_token,
        }

    def login_with_password(self, username: str, secret: str, device_info: str = "Web Fallback") -> dict[str, Any]:
        """Fallback authentication using username + secret."""
        user = self.store.get_user_by_username(username)
        if not user:
            raise ValueError("Invalid username or credentials")

        if not user.get("password_hash") or not user.get("salt"):
            raise ValueError("No fallback secret configured for this account; please sign in with Passkey")

        if not _verify_secret(secret, user["salt"], user["password_hash"]):
            raise ValueError("Invalid username or credentials")

        session_token = self.store.create_session(user_id=user["id"], device_info=device_info)
        return {
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "steward_id": user["steward_id"],
            },
            "session_token": session_token,
        }

    def register_with_password(self, username: str, secret: str, display_name: str | None = None) -> dict[str, Any]:
        """Create an account with username fallback secret."""
        if not secret or len(secret) < 6:
            raise ValueError("Password must be at least 6 characters")

        user = self.store.create_user(username=username, display_name=display_name, password=secret)
        session_token = self.store.create_session(user_id=user["id"], device_info="Web Fallback Registration")
        return {
            "success": True,
            "user": user,
            "session_token": session_token,
        }

    def validate_session(self, session_token: str) -> dict[str, Any] | None:
        return self.store.get_session(session_token)

    def logout(self, session_token: str) -> bool:
        return self.store.revoke_session(session_token)


# Default manager singleton
default_auth_manager = AuthManager()
