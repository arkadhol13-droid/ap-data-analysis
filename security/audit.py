
import json
import re
from datetime import datetime, timezone

from security.db import get_conn, init_db

init_db()

EVENT_LOGIN_SUCCESS = "LOGIN_SUCCESS"
EVENT_LOGIN_FAILURE = "LOGIN_FAILURE"
EVENT_ACCOUNT_LOCKOUT = "ACCOUNT_LOCKOUT"
EVENT_CAPTCHA_FAILURE = "CAPTCHA_FAILURE"
EVENT_PASSWORD_RESET = "PASSWORD_RESET"
EVENT_PASSWORD_CHANGE = "PASSWORD_CHANGE"
EVENT_TOKEN_REFRESH = "TOKEN_REFRESH"
EVENT_SESSION_EXPIRED = "SESSION_EXPIRED"
EVENT_SESSION_IDLE_TIMEOUT = "SESSION_IDLE_TIMEOUT"
EVENT_ADMIN_FORCE_LOGOUT = "ADMIN_FORCE_LOGOUT"
EVENT_ROLE_CHANGE = "ROLE_CHANGE"
EVENT_RATE_LIMIT_VIOLATION = "RATE_LIMIT_VIOLATION"
EVENT_LOGOUT = "LOGOUT"

_SECRET_LIKE = re.compile(
    r"(?i)(password|secret|token|apikey|api_key|bearer)\s*[:=]\s*\S+"
)
def _scrub(text: str) -> str:
    if not text:
        return text
    return _SECRET_LIKE.sub(lambda m: m.group(0).split(":")[0].split("=")[0] + "=***", text)
def log_event(event_type: str, username: str = None, actor: str = None, details: dict | str = None):
    if isinstance(details, dict):
        details_str = json.dumps(details, default=str, ensure_ascii=False)
    else:
        details_str = details or ""

    details_str = _scrub(details_str)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_logs (occurred_at, event_type, username, actor, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                event_type,
                username,
                actor,
                details_str,
            ),
        )
def get_recent_logs(limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT occurred_at, event_type, username, actor, details "
            "FROM audit_logs ORDER BY occurred_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
