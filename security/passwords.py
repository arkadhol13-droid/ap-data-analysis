
import bcrypt
from config.security_settings import MIN_PASSWORD_LENGTH
def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")
def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False
def is_bcrypt_hash(value: str) -> bool:
    """Detects legacy plaintext passwords so we can auto-migrate them."""
    return isinstance(value, str) and value.startswith(("$2a$", "$2b$", "$2y$"))
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Server-side password policy check. Returns (is_valid, error_message).
    Intentionally simple and predictable rather than "clever" regex --
    clear rules are easier to communicate to users and to audit.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.lower() in ("password", "12345678", "admin123", "letmein"):
        return False, "This password is too common. Choose a stronger one."
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "Password must contain both letters and numbers."
    return True, ""
