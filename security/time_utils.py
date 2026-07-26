
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
        return iso_timestamp  
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(DISPLAY_TIMEZONE)
    return local_dt.strftime(f"%d %b %Y, %I:%M:%S %p {DISPLAY_TZ_LABEL}")
