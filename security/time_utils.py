"""
Display-time formatting.

All timestamps are stored in the database as UTC (this is deliberate and
correct practice -- storing local time causes bugs across daylight saving
changes, server timezone differences, and multi-region deployments). This
module only converts UTC -> a display timezone at the point of showing
something to a human in the Admin Panel; nothing about how data is stored
changes.

Default display timezone is Asia/Kolkata (IST). Change DISPLAY_TIMEZONE
below if your users are elsewhere, or make it a per-admin preference later.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DISPLAY_TIMEZONE = ZoneInfo("Asia/Kolkata")
DISPLAY_TZ_LABEL = "IST"


def to_display_time(iso_timestamp: str) -> str:
    """
    Converts a stored ISO timestamp (UTC, with or without an explicit
    +00:00 offset -- both forms exist in older rows) into a single
    consistent, human-readable IST string.
    Returns "-" for missing/unparseable values instead of raising, since
    this is only ever used for display.
    """
    if not iso_timestamp:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp  # last resort: show raw value rather than crash

    # Older rows may have been written without an explicit UTC offset.
    # Every timestamp in this app is generated with datetime.now(timezone.utc),
    # so treating a naive value as UTC here is correct, not a guess.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(DISPLAY_TIMEZONE)
    return local_dt.strftime(f"%d %b %Y, %I:%M:%S %p {DISPLAY_TZ_LABEL}")
