
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-only-change-me")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
BOOTSTRAP_ADMIN_USERNAME = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
# Storage locations
DATA_DIR = os.environ.get("APP_DATA_DIR", os.path.join(os.getcwd(), "data"))
SECURITY_DB_PATH = os.path.join(DATA_DIR, "security.db")
USERS_JSON_PATH = os.environ.get("USERS_JSON_PATH", "auth/users.json")
# Login lockout policy
MAX_FAILED_LOGIN_ATTEMPTS = _get_int("MAX_FAILED_LOGIN_ATTEMPTS", 5)
LOCKOUT_WINDOW_MINUTES = _get_int("LOCKOUT_WINDOW_MINUTES", 15)
# Session policy
IDLE_TIMEOUT_MINUTES = _get_int("IDLE_TIMEOUT_MINUTES", 30)
SESSION_AUTOREFRESH_MS = _get_int("SESSION_AUTOREFRESH_MS", 60_000)  # 1 min
# Rate limiting
AI_INSIGHTS_RATE_LIMIT = _get_int("AI_INSIGHTS_RATE_LIMIT", 10)   # requests
AI_INSIGHTS_RATE_WINDOW_SECONDS = _get_int("AI_INSIGHTS_RATE_WINDOW_SECONDS", 60)

LOGIN_RATE_LIMIT = _get_int("LOGIN_RATE_LIMIT", 10)               # requests
LOGIN_RATE_WINDOW_SECONDS = _get_int("LOGIN_RATE_WINDOW_SECONDS", 60)

ADMIN_ACTION_RATE_LIMIT = _get_int("ADMIN_ACTION_RATE_LIMIT", 30)
ADMIN_ACTION_RATE_WINDOW_SECONDS = _get_int("ADMIN_ACTION_RATE_WINDOW_SECONDS", 60)
# Password policy
MIN_PASSWORD_LENGTH = _get_int("MIN_PASSWORD_LENGTH", 8)
# Misc
ENVIRONMENT = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = ENVIRONMENT.lower() == "production"