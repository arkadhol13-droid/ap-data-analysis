
import secrets
from datetime import datetime, timedelta, timezone

from config.security_settings import IDLE_TIMEOUT_MINUTES
from security.db import get_conn, init_db

init_db()
def _now():
    return datetime.now(timezone.utc)
def create_session(username: str, role: str, device: str = "", ip_address: str = "") -> str:
    session_id = secrets.token_urlsafe(32)
    now = _now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(session_id, username, role, created_at, last_activity, device, ip_address, revoked) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (session_id, username, role, now, now, device, ip_address),
        )
    return session_id
def touch_session(session_id: str):
    """Updates last_activity -- call this on every rerun of an authenticated page."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET last_activity = ? WHERE session_id = ? AND revoked = 0",
            (_now().isoformat(), session_id),
        )
def get_session(session_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None
class SessionStatus:
    VALID = "VALID"
    NOT_FOUND = "NOT_FOUND"
    REVOKED = "REVOKED"
    IDLE_TIMEOUT = "IDLE_TIMEOUT"
def validate_session(session_id: str) -> str:
    """
    Returns one of SessionStatus.* Does NOT mutate state -- callers decide
    what to do (e.g. log the event, clear st.session_state, show a message).
    """
    if not session_id:
        return SessionStatus.NOT_FOUND

    session = get_session(session_id)
    if session is None:
        return SessionStatus.NOT_FOUND

    if session["revoked"]:
        return SessionStatus.REVOKED

    last_activity = datetime.fromisoformat(session["last_activity"])
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)

    if _now() - last_activity > timedelta(minutes=IDLE_TIMEOUT_MINUTES):
        return SessionStatus.IDLE_TIMEOUT

    return SessionStatus.VALID


def revoke_session(session_id: str, reason: str = "logout"):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1, revoked_reason = ? WHERE session_id = ?",
            (reason, session_id),
        )


def revoke_all_sessions_for_user(username: str, reason: str = "admin_force_logout"):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1, revoked_reason = ? "
            "WHERE username = ? AND revoked = 0",
            (reason, username),
        )


def revoke_sessions_for_users(usernames: list, reason: str = "admin_force_logout"):
    with get_conn() as conn:
        conn.executemany(
            "UPDATE sessions SET revoked = 1, revoked_reason = ? "
            "WHERE username = ? AND revoked = 0",
            [(reason, u) for u in usernames],
        )


def revoke_all_sessions(reason: str = "admin_force_logout_all"):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1, revoked_reason = ? WHERE revoked = 0",
            (reason,),
        )


def list_active_sessions():
    """Active = not revoked AND not idle-timed-out, ordered by most recently active."""
    cutoff = (_now() - timedelta(minutes=IDLE_TIMEOUT_MINUTES)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE revoked = 0 AND last_activity >= ? "
            "ORDER BY last_activity DESC",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_all_sessions(limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY last_activity DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
