"""Persistent password accounts, opaque bearer sessions, and scoped media grants."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Callable

from fastapi import HTTPException

# None denotes a direct in-process helper call, never an HTTP authentication bypass.
REQUEST_SESSION: ContextVar[dict | None] = ContextVar("cutflow_request_session", default=None)


class AuthStore:
    def __init__(self, db_path: Callable[[], Path]):
        self.db_path = db_path

    @contextmanager
    def connection(self):
        path = self.db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS auth_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS auth_rate_limits (subject_hash TEXT PRIMARY KEY, attempts INTEGER NOT NULL, expires_at REAL NOT NULL)")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def normalize_email(email: str) -> str:
        email = email.strip().lower()
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise HTTPException(400, "Enter a valid email address.")
        return email

    @staticmethod
    def password_hash(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
        return f"scrypt${salt.hex()}${digest.hex()}"

    def register(self, email: str, password: str) -> dict:
        email = self.normalize_email(email)
        if not 10 <= len(password) <= 1024:
            raise HTTPException(400, "Use a password between 10 and 1024 characters.")
        user = {"id": uuid.uuid4().hex, "email": email}
        hashed = self.password_hash(password)
        try:
            with self.connection() as db:
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user["id"], email, hashed, time.time()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with that email already exists.") from None
        return self.issue_session(user)

    def login(self, email: str, password: str) -> dict:
        if not 1 <= len(password) <= 1024:
            raise HTTPException(400, "Password must be between 1 and 1024 characters.")
        email = self.normalize_email(email)
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        # Run scrypt for unknown accounts too, avoiding a fast account-existence path.
        encoded = row["password_hash"] if row else "scrypt$" + "00" * 16 + "$" + "00" * 32
        try:
            salt = bytes.fromhex(encoded.split("$")[1])
            valid = hmac.compare_digest(self.password_hash(password, salt), encoded)
        except (ValueError, IndexError):
            valid = False
        if not row or not valid:
            raise HTTPException(401, "Email or password is incorrect.")
        return self.issue_session({"id": row["id"], "email": row["email"]})

    def check_rate_limit(self, client_address: str) -> None:
        """Share a durable fixed window across register/login for each client IP."""
        subject = hashlib.sha256(("auth:" + client_address).encode()).hexdigest()
        now = time.time()
        window = max(1, int(os.getenv("CUTFLOW_AUTH_RATE_WINDOW_SECONDS", "60")))
        limit = max(1, int(os.getenv("CUTFLOW_AUTH_MAX_ATTEMPTS", "10")))
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM auth_rate_limits WHERE expires_at <= ?", (now,))
            row = db.execute("SELECT attempts, expires_at FROM auth_rate_limits WHERE subject_hash = ?", (subject,)).fetchone()
            if row and row["attempts"] >= limit:
                raise HTTPException(429, "Too many sign-in attempts. Try again shortly.", headers={"Retry-After": str(max(1, int(row["expires_at"] - now + 1)))})
            if row:
                db.execute("UPDATE auth_rate_limits SET attempts = attempts + 1 WHERE subject_hash = ?", (subject,))
            else:
                db.execute("INSERT INTO auth_rate_limits VALUES (?, 1, ?)", (subject, now + window))

    def issue_session(self, user: dict) -> dict:
        token = secrets.token_urlsafe(32)
        ttl = max(60, int(os.getenv("CUTFLOW_SESSION_TTL_SECONDS", "2592000")))
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], time.time() + ttl))
        return {"token": token, "user": user}

    def authenticate_hash(self, token_hash: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT users.id, users.email, sessions.expires_at FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND sessions.expires_at > ?", (token_hash, time.time())).fetchone()
        if row:
            return {"user": {"id": row["id"], "email": row["email"]}, "session_hash": token_hash, "expires_at": row["expires_at"]}
        return None

    def authenticate(self, token: str) -> dict | None:
        if not token or len(token) > 256:
            return None
        return self.authenticate_hash(hashlib.sha256(token.encode()).hexdigest())

    def logout(self, session: dict) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (session["session_hash"],))

    def signing_key(self) -> bytes:
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO auth_metadata VALUES ('media_signing_key', ?)", (secrets.token_hex(32),))
            row = db.execute("SELECT value FROM auth_metadata WHERE key = 'media_signing_key'").fetchone()
        return bytes.fromhex(row["value"])

    def media_token(self, session: dict, path: str) -> str:
        ttl = min(900, max(1, int(os.getenv("CUTFLOW_MEDIA_TTL_SECONDS", "300"))))
        payload = {"path": path, "sid": session["session_hash"], "exp": min(session["expires_at"], time.time() + ttl)}
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        signature = hmac.new(self.signing_key(), encoded.encode(), hashlib.sha256).hexdigest()
        return encoded + "." + signature

    def authenticate_media(self, token: str, path: str) -> dict | None:
        if not token or len(token) > 2048:
            return None
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(self.signing_key(), encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                return None
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if payload["path"] != path or payload["exp"] <= time.time():
                return None
            return self.authenticate_hash(payload["sid"])
        except (ValueError, KeyError, TypeError, UnicodeError):
            return None
