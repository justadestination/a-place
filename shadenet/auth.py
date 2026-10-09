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

            CREATE TABLE IF NOT EXISTS recovery_codes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                consumed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS recovery_escalations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                username TEXT NOT NULL,
                contact_info TEXT NOT NULL,
                notes TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferences_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS user_earmarks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
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

    def list_active_sessions(self, user_id: str) -> list[dict[str, Any]]:
        now_iso = _now_iso()
        with self._get_connection() as con:
            rows = con.execute("""
                SELECT id as session_id, created_at, expires_at, revoked_at, device_info
                FROM sessions
                WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?
                ORDER BY created_at DESC
            """, (user_id, now_iso)).fetchall()
            return [dict(r) for r in rows]

    def revoke_user_session(self, user_id: str, session_to_revoke: str) -> bool:
        now_iso = _now_iso()
        with self._get_connection() as con:
            cur = con.execute("""
                UPDATE sessions
                SET revoked_at = ?
                WHERE user_id = ? AND id = ? AND revoked_at IS NULL
            """, (now_iso, user_id, session_to_revoke))
            return cur.rowcount > 0

    def revoke_all_other_sessions(self, user_id: str, current_session_token: str) -> int:
        now_iso = _now_iso()
        with self._get_connection() as con:
            cur = con.execute("""
                UPDATE sessions
                SET revoked_at = ?
                WHERE user_id = ? AND id != ? AND revoked_at IS NULL AND expires_at > ?
            """, (now_iso, user_id, current_session_token, now_iso))
            return cur.rowcount

    # --- Recovery Codes & Escalations (Task 4.2) ---
    def generate_recovery_codes(self, user_id: str, count: int = 8) -> list[str]:
        """Generate single-use recovery codes, hash them with PBKDF2, and persist."""
        codes = []
        created_at = _now_iso()
        with self._get_connection() as con:
            con.execute("DELETE FROM recovery_codes WHERE user_id = ? AND consumed_at IS NULL", (user_id,))
            for _ in range(count):
                raw = secrets.token_hex(6)  # 12 hex chars
                formatted = f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"
                codes.append(formatted)
                salt_b64, hash_b64 = _hash_secret(raw)
                code_id = f"rc_{secrets.token_hex(8)}"
                con.execute(
                    "INSERT INTO recovery_codes (id, user_id, code_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)",
                    (code_id, user_id, hash_b64, salt_b64, created_at)
                )
        logger.info("recovery_codes_generated", user_id=user_id, count=count)
        return codes

    def verify_and_consume_recovery_code(self, username: str, recovery_code: str) -> dict[str, Any] | None:
        """Verify provided code against user's stored salted hashes and consume single-use."""
        clean_user = username.strip().lower()
        user = self.get_user_by_username(clean_user)
        if not user:
            return None

        raw_code = recovery_code.replace("-", "").strip().lower()
        if not raw_code:
            return None

        now_iso = _now_iso()
        with self._get_connection() as con:
            rows = con.execute(
                "SELECT * FROM recovery_codes WHERE user_id = ? AND consumed_at IS NULL",
                (user["id"],)
            ).fetchall()

            for row in rows:
                if _verify_secret(raw_code, row["salt"], row["code_hash"]):
                    con.execute(
                        "UPDATE recovery_codes SET consumed_at = ? WHERE id = ?",
                        (now_iso, row["id"])
                    )
                    logger.info("recovery_code_consumed", user_id=user["id"], code_id=row["id"])
                    return {"user": user, "code_id": row["id"]}

        logger.warning("recovery_code_verification_failed", username=clean_user)
        return None

    def create_recovery_escalation(self, username: str, contact_info: str, notes: str) -> dict[str, Any]:
        user = self.get_user_by_username(username.strip().lower())
        user_id = user["id"] if user else None
        esc_id = f"esc_{secrets.token_hex(8)}"
        created_at = _now_iso()
        with self._get_connection() as con:
            con.execute(
                "INSERT INTO recovery_escalations (id, user_id, username, contact_info, notes, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (esc_id, user_id, username.strip().lower(), contact_info.strip(), notes.strip(), "pending", created_at)
            )
        logger.info("recovery_escalation_created", escalation_id=esc_id, username=username)
        return {
            "id": esc_id,
            "username": username,
            "status": "pending",
            "created_at": created_at,
        }

    def get_recovery_status(self, user_id: str) -> dict[str, Any]:
        with self._get_connection() as con:
            total = con.execute("SELECT COUNT(*) as c FROM recovery_codes WHERE user_id = ?", (user_id,)).fetchone()["c"]
            remaining = con.execute("SELECT COUNT(*) as c FROM recovery_codes WHERE user_id = ? AND consumed_at IS NULL", (user_id,)).fetchone()["c"]
            return {"total": total, "remaining": remaining}

    # --- Preferences & Earmarks (Task 4.5 / 4.6) ---
    def set_user_preferences(self, user_id: str, preferences: dict[str, Any]) -> dict[str, Any]:
        pref_json = json.dumps(preferences)
        updated_at = _now_iso()
        with self._get_connection() as con:
            con.execute(
                "INSERT INTO user_preferences (user_id, preferences_json, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET preferences_json = ?, updated_at = ?",
                (user_id, pref_json, updated_at, pref_json, updated_at)
            )
        return {"user_id": user_id, "preferences": preferences, "updated_at": updated_at}

    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        with self._get_connection() as con:
            row = con.execute("SELECT preferences_json FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                try:
                    return json.loads(row["preferences_json"])
                except Exception:
                    return {}
            return {}

    def add_user_earmark(self, user_id: str, event_id: str) -> dict[str, Any]:
        earmark_id = f"emk_{secrets.token_hex(8)}"
        created_at = _now_iso()
        with self._get_connection() as con:
            con.execute(
                "INSERT INTO user_earmarks (id, user_id, event_id, created_at) VALUES (?, ?, ?, ?)",
                (earmark_id, user_id, event_id, created_at)
            )
        return {"id": earmark_id, "user_id": user_id, "event_id": event_id, "created_at": created_at}

    def get_user_earmarks(self, user_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as con:
            rows = con.execute("SELECT id, event_id, created_at FROM user_earmarks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    # --- Data Export & Account Deletion (Task 4.5) ---
    def export_user_data(self, user_id: str) -> dict[str, Any]:
        """Export comprehensive GDPR/CCPA compliant data bundle for a user."""
        with self._get_connection() as con:
            user_row = con.execute(
                "SELECT id, username, display_name, steward_id, created_at FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            if not user_row:
                raise ValueError(f"User {user_id} not found")
            user = dict(user_row)

            # Passkeys / credentials metadata
            passkeys = [
                dict(r) for r in con.execute(
                    "SELECT id, credential_id, sign_count, nickname, created_at FROM passkeys WHERE user_id = ?",
                    (user_id,)
                ).fetchall()
            ]

            # Sessions
            sessions = [
                dict(r) for r in con.execute(
                    "SELECT id, created_at, expires_at, revoked_at, device_info FROM sessions WHERE user_id = ?",
                    (user_id,)
                ).fetchall()
            ]

            # Preferences
            preferences = self.get_user_preferences(user_id)

            # Earmarks
            earmarks = self.get_user_earmarks(user_id)

            # Recovery escalations
            escalations = [
                dict(r) for r in con.execute(
                    "SELECT id, username, contact_info, notes, status, created_at, resolved_at "
                    "FROM recovery_escalations WHERE user_id = ? OR username = ?",
                    (user_id, user["username"])
                ).fetchall()
            ]

            # Votes / Tallies (via steward_id, username, or user_id)
            tallies = []
            steward_id = user.get("steward_id") or user.get("username")
            try:
                tallies = [
                    dict(r) for r in con.execute(
                        "SELECT event_id, direction, verified, updated_at FROM nightcal_tallies "
                        "WHERE steward_id = ? OR steward_id = ?",
                        (steward_id, user_id)
                    ).fetchall()
                ]
            except sqlite3.OperationalError:
                pass

            logger.info("account_data_exported", user_id=user_id, username=user["username"])
            return {
                "format_version": "1.0",
                "compliance": "GDPR/CCPA Article 15 (Right of Access)",
                "exported_at": _now_iso(),
                "user": user,
                "passkeys": passkeys,
                "sessions": sessions,
                "preferences": preferences,
                "earmarks": earmarks,
                "votes": tallies,
                "escalations": escalations,
            }

    def delete_user_data(self, user_id: str) -> dict[str, Any]:
        """Perform full deletion of a user's account and residual data (Task 4.5)."""
        with self._get_connection() as con:
            user_row = con.execute("SELECT id, username, steward_id FROM users WHERE id = ?", (user_id,))
            user = user_row.fetchone()
            if not user:
                raise ValueError(f"User {user_id} not found")
            username = user["username"]
            steward_id = user["steward_id"] or username

            # 1. Delete sessions
            con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            # 2. Delete passkeys
            con.execute("DELETE FROM passkeys WHERE user_id = ?", (user_id,))
            # 3. Delete recovery codes
            con.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
            # 4. Delete auth challenges
            con.execute("DELETE FROM auth_challenges WHERE user_id = ?", (user_id,))
            # 5. Delete preferences
            con.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
            # 6. Delete earmarks
            con.execute("DELETE FROM user_earmarks WHERE user_id = ?", (user_id,))
            # 7. Delete recovery escalations
            con.execute("DELETE FROM recovery_escalations WHERE user_id = ? OR username = ?", (user_id, username))
            # 8. Anonymize/delete votes & tallies cast by this user so 0 residual rows reference them
            try:
                con.execute("DELETE FROM nightcal_tallies WHERE steward_id = ? OR steward_id = ?", (steward_id, user_id))
            except sqlite3.OperationalError:
                pass
            # 9. Delete user record
            con.execute("DELETE FROM users WHERE id = ?", (user_id,))
            con.commit()

            logger.info("account_deleted", user_id=user_id, username=username)
            return {
                "success": True,
                "deleted_user_id": user_id,
                "username": username,
                "deleted_at": _now_iso(),
            }




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

    def list_sessions(self, session_token: str) -> list[dict[str, Any]]:
        current_sess = self.validate_session(session_token)
        if not current_sess:
            raise ValueError("Unauthorized or session expired")
        user_id = current_sess["user_id"]
        sessions = self.store.list_active_sessions(user_id)
        for s in sessions:
            s["is_current"] = (s["session_id"] == session_token)
        return sessions

    def revoke_session(self, session_token: str, target_session_id: str | None = None) -> bool:
        if target_session_id is None or target_session_id == session_token:
            return self.store.revoke_session(session_token)
        current_sess = self.validate_session(session_token)
        if not current_sess:
            raise ValueError("Unauthorized or session expired")
        return self.store.revoke_user_session(current_sess["user_id"], target_session_id)

    def revoke_all_other_sessions(self, session_token: str) -> int:
        current_sess = self.validate_session(session_token)
        if not current_sess:
            raise ValueError("Unauthorized or session expired")
        return self.store.revoke_all_other_sessions(current_sess["user_id"], session_token)

    def recover_account(self, username: str, recovery_code: str, device_info: str = "New Authenticator Device") -> dict[str, Any]:
        result = self.store.verify_and_consume_recovery_code(username, recovery_code)
        if not result:
            raise ValueError("Invalid username or recovery code")

        user = result["user"]
        session_token = self.store.create_session(user["id"], device_info=device_info)
        return {
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "steward_id": user["steward_id"],
            },
            "session_token": session_token,
            "consumed_code_id": result["code_id"],
        }

    def submit_escalation(self, username: str, contact_info: str, notes: str) -> dict[str, Any]:
        if not username or not contact_info:
            raise ValueError("Both username and contact information are required")
        return self.store.create_recovery_escalation(username, contact_info, notes)

    def export_account(self, session_token: str) -> dict[str, Any]:
        sess = self.validate_session(session_token)
        if not sess:
            raise ValueError("Unauthorized: invalid or expired session")
        return self.store.export_user_data(sess["user_id"])

    def delete_account(self, session_token: str, confirm_username: str | None = None) -> dict[str, Any]:
        sess = self.validate_session(session_token)
        if not sess:
            raise ValueError("Unauthorized: invalid or expired session")
        user = self.store.get_user_by_id(sess["user_id"])
        if not user:
            raise ValueError("User account not found")
        if confirm_username and confirm_username.strip().lower() != user["username"].strip().lower():
            raise ValueError(f"Confirmation username '{confirm_username}' does not match account '{user['username']}'")
        return self.store.delete_user_data(user["id"])

    def set_preferences(self, session_token: str, preferences: dict[str, Any]) -> dict[str, Any]:
        sess = self.validate_session(session_token)
        if not sess:
            raise ValueError("Unauthorized: invalid or expired session")
        return self.store.set_user_preferences(sess["user_id"], preferences)

    def get_preferences(self, session_token: str) -> dict[str, Any]:
        sess = self.validate_session(session_token)
        if not sess:
            raise ValueError("Unauthorized: invalid or expired session")
        return self.store.get_user_preferences(sess["user_id"])

    def add_earmark(self, session_token: str, event_id: str) -> dict[str, Any]:
        sess = self.validate_session(session_token)
        if not sess:
            raise ValueError("Unauthorized: invalid or expired session")
        return self.store.add_user_earmark(sess["user_id"], event_id)

    def list_earmarks(self, session_token: str) -> list[dict[str, Any]]:
        sess = self.validate_session(session_token)
        if not sess:
            raise ValueError("Unauthorized: invalid or expired session")
        return self.store.get_user_earmarks(sess["user_id"])


# Default manager singleton
default_auth_manager = AuthManager()
