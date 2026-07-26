"""
Security data store.

Why SQLite instead of st.session_state for security data:
Streamlit's `st.session_state` is scoped to a single browser session
(one tab/connection) on the server process. Login-attempt counters,
active sessions, rate limits, and audit logs must be visible to EVERY
session on the server (e.g. so an admin's "force logout" in tab A is
enforced the next time the target user's browser reruns in tab B).
SQLite gives us that shared, server-side, tamper-proof store without
adding external infra.

All statements below use parameterized queries exclusively -- never
f-string / % interpolation of user input into SQL -- to eliminate SQL
injection risk in this module.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager

from config.security_settings import DATA_DIR, SECURITY_DB_PATH

_lock = threading.Lock()
_initialized = False


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


@contextmanager
def get_conn():
    """Yields a SQLite connection with sane defaults, always closed after use."""
    _ensure_dir()
    conn = sqlite3.connect(SECURITY_DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Creates all required tables if they do not already exist. Idempotent."""
    global _initialized
    with _lock:
        if _initialized:
            return
        with get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id      TEXT PRIMARY KEY,
                    username        TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    last_activity   TEXT NOT NULL,
                    device          TEXT,
                    ip_address      TEXT,
                    revoked         INTEGER NOT NULL DEFAULT 0,
                    revoked_reason  TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_username
                    ON sessions (username);

                CREATE TABLE IF NOT EXISTS login_attempts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier      TEXT NOT NULL,
                    attempted_at    TEXT NOT NULL,
                    success         INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_login_attempts_identifier
                    ON login_attempts (identifier, attempted_at);

                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket          TEXT NOT NULL,
                    identifier      TEXT NOT NULL,
                    occurred_at     TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket
                    ON rate_limit_events (bucket, identifier, occurred_at);

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at     TEXT NOT NULL,
                    event_type      TEXT NOT NULL,
                    username        TEXT,
                    actor            TEXT,
                    details         TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_logs_time
                    ON audit_logs (occurred_at);
                """
            )
        _initialized = True
