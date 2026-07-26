"""
Login lockout protection.

Locks an identifier (we use `username` -- optionally combine with IP,
see note below) for LOCKOUT_WINDOW_MINUTES after
MAX_FAILED_LOGIN_ATTEMPTS consecutive failures. A successful login
resets the counter immediately.

Note on identifier choice: locking by username alone prevents a
targeted account-takeover brute force. Locking by IP alone is
trivially bypassed with rotating IPs and can be used to lock out
legitimate users behind a shared corporate NAT (denial of service).
This module locks by username, and separately the rate limiter
(security/rate_limiter.py) throttles the login endpoint per-IP to
blunt distributed credential-stuffing sweeps. Using both together is
the standard mitigation recommended by OWASP's
Credential-Stuffing/Brute-Force cheat sheets.
"""

from datetime import datetime, timedelta, timezone

from config.security_settings import (
    LOCKOUT_WINDOW_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
)
from security.db import get_conn, init_db

init_db()


def _now():
    return datetime.now(timezone.utc)


def record_attempt(identifier: str, success: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO login_attempts (identifier, attempted_at, success) "
            "VALUES (?, ?, ?)",
            (identifier.lower(), _now().isoformat(), 1 if success else 0),
        )
        if success:
            # Successful login: clear prior failures for this identifier so
            # they don't carry over and cause a surprise lockout later.
            conn.execute(
                "DELETE FROM login_attempts WHERE identifier = ? AND success = 0",
                (identifier.lower(),),
            )


def is_locked_out(identifier: str) -> tuple[bool, int]:
    """
    Returns (locked, seconds_remaining). Only consecutive failures within
    the lockout window since the last success count toward the lockout.
    """
    window_start = (_now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)).isoformat()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT attempted_at, success FROM login_attempts "
            "WHERE identifier = ? AND attempted_at >= ? "
            "ORDER BY attempted_at DESC",
            (identifier.lower(), window_start),
        ).fetchall()

    failures = 0
    oldest_relevant_failure = None
    for row in rows:
        if row["success"]:
            break
        failures += 1
        oldest_relevant_failure = row["attempted_at"]

    if failures >= MAX_FAILED_LOGIN_ATTEMPTS:
        locked_since = datetime.fromisoformat(oldest_relevant_failure)
        if locked_since.tzinfo is None:
            locked_since = locked_since.replace(tzinfo=timezone.utc)
        unlock_at = locked_since + timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
        remaining = (unlock_at - _now()).total_seconds()
        if remaining > 0:
            return True, int(remaining)

    return False, 0


def failed_attempt_count(identifier: str) -> int:
    window_start = (_now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT success FROM login_attempts "
            "WHERE identifier = ? AND attempted_at >= ? ORDER BY attempted_at DESC",
            (identifier.lower(), window_start),
        ).fetchall()
    count = 0
    for row in rows:
        if row["success"]:
            break
        count += 1
    return count
