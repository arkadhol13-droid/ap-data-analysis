"""
Sliding-window rate limiter backed by SQLite so limits are enforced
across the whole server (all Streamlit sessions), not per-tab.

`check_rate_limit(bucket, identifier, limit, window_seconds)` returns
an object describing whether the caller is allowed, and if not, how
many seconds until they should retry -- the Streamlit-native
equivalent of an HTTP 429 + `Retry-After` header (Streamlit has no
per-request HTTP response layer for a page render, so we surface this
as a blocking UI message with a live countdown instead).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from security.db import get_conn, init_db
from security.audit import log_event, EVENT_RATE_LIMIT_VIOLATION

init_db()


def _now():
    return datetime.now(timezone.utc)


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


def check_rate_limit(bucket: str, identifier: str, limit: int, window_seconds: int) -> RateLimitResult:
    """
    Checks (without recording) whether `identifier` has capacity left in
    `bucket` under `limit` requests per `window_seconds`.
    """
    window_start = (_now() - timedelta(seconds=window_seconds)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT occurred_at FROM rate_limit_events "
            "WHERE bucket = ? AND identifier = ? AND occurred_at >= ? "
            "ORDER BY occurred_at ASC",
            (bucket, identifier, window_start),
        ).fetchall()

    count = len(rows)
    if count < limit:
        return RateLimitResult(allowed=True, remaining=limit - count, retry_after_seconds=0)

    oldest = datetime.fromisoformat(rows[0]["occurred_at"])
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    retry_after = int((oldest + timedelta(seconds=window_seconds) - _now()).total_seconds())
    retry_after = max(retry_after, 1)

    log_event(
        EVENT_RATE_LIMIT_VIOLATION,
        username=identifier,
        details={"bucket": bucket, "limit": limit, "window_seconds": window_seconds},
    )
    return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)


def record_request(bucket: str, identifier: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rate_limit_events (bucket, identifier, occurred_at) VALUES (?, ?, ?)",
            (bucket, identifier, _now().isoformat()),
        )
        # Housekeeping: drop events older than 1 hour for this bucket/identifier
        # so the table doesn't grow unbounded.
        cutoff = (_now() - timedelta(hours=1)).isoformat()
        conn.execute(
            "DELETE FROM rate_limit_events WHERE bucket = ? AND identifier = ? AND occurred_at < ?",
            (bucket, identifier, cutoff),
        )


def enforce_rate_limit(bucket: str, identifier: str, limit: int, window_seconds: int) -> RateLimitResult:
    """Checks AND records in one call -- use this at the point of actual use."""
    result = check_rate_limit(bucket, identifier, limit, window_seconds)
    if result.allowed:
        record_request(bucket, identifier)
    return result
