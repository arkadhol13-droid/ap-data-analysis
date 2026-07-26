import json
import os

from config.security_settings import (
    BOOTSTRAP_ADMIN_PASSWORD,
    BOOTSTRAP_ADMIN_USERNAME,
    USERS_JSON_PATH,
)
from security.passwords import hash_password, is_bcrypt_hash
VALID_ROLES = ("Admin", "Manager", "User")
def _default_users():
    """
    Seeds a single admin account on first run. If BOOTSTRAP_ADMIN_PASSWORD
    is not set in the environment, a random one is generated and printed
    to the server console ONCE so an operator can capture it -- the app
    never ships with a hard-coded default admin password.
    """
    import secrets
    admin_password = BOOTSTRAP_ADMIN_PASSWORD
    generated = False
    if not admin_password:
        admin_password = secrets.token_urlsafe(12)
        generated = True
    users = {
        BOOTSTRAP_ADMIN_USERNAME: {
            "password": hash_password(admin_password),
            "role": "Admin",
        }
    }
    if generated:
        print(
            "=" * 70
            + f"\n[SECURITY] No BOOTSTRAP_ADMIN_PASSWORD set. Generated a "
              f"one-time admin password for '{BOOTSTRAP_ADMIN_USERNAME}':\n"
              f"    {admin_password}\n"
              f"Log in once and change it immediately, or set "
              f"BOOTSTRAP_ADMIN_PASSWORD in your environment instead.\n" + "=" * 70
        )
    return users
def _migrate_plaintext_if_needed(users: dict) -> tuple[dict, bool]:
    changed = False
    for username, record in users.items():
        pwd = record.get("password", "")
        if not is_bcrypt_hash(pwd):
            record["password"] = hash_password(pwd)
            changed = True
        record.setdefault("role", "User")
        if record["role"] not in VALID_ROLES:
            record["role"] = "User"
    return users, changed
def load_users() -> dict:
    if not os.path.exists(USERS_JSON_PATH):
        users = _default_users()
        save_users(users)
        return users
    with open(USERS_JSON_PATH, "r") as f:
        users = json.load(f)
    users, changed = _migrate_plaintext_if_needed(users)
    if changed:
        save_users(users)
    return users
def save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_JSON_PATH) or ".", exist_ok=True)
    with open(USERS_JSON_PATH, "w") as f:
        json.dump(users, f, indent=4)
def verify_credentials(username: str, password: str):
    """Returns the user's role string if valid, else None. Never raises
    on unknown username (avoids leaking which usernames exist)."""
    from security.passwords import verify_password
    users = load_users()
    record = users.get(username)
    if record is None:
        verify_password(password, "$2b$12$C6UzMDM.H6dfI/f8IjCUu.Y4Xi.OmnB2S9pQmKDMdU7QzcTt7X3rG")
        return None
    if verify_password(password, record["password"]):
        return record["role"]
    return None
def change_password(username, old_password, new_password) -> tuple[bool, str]:
    from security.passwords import validate_password_strength, verify_password
    users = load_users()
    if username not in users:
        return False, "User not found."
    if not verify_password(old_password, users[username]["password"]):
        return False, "Current password incorrect."
    valid, msg = validate_password_strength(new_password)
    if not valid:
        return False, msg
    users[username]["password"] = hash_password(new_password)
    save_users(users)
    return True, "Password updated successfully."
def admin_reset_password(target_user, new_password) -> tuple[bool, str]:
    from security.passwords import validate_password_strength
    users = load_users()
    if target_user not in users:
        return False, "User not found."
    valid, msg = validate_password_strength(new_password)
    if not valid:
        return False, msg
    users[target_user]["password"] = hash_password(new_password)
    save_users(users)
    return True, "Password reset successfully."
def admin_set_role(target_user, new_role) -> tuple[bool, str]:
    if new_role not in VALID_ROLES:
        return False, f"Role must be one of {VALID_ROLES}."
    users = load_users()
    if target_user not in users:
        return False, "User not found."
    users[target_user]["role"] = new_role
    save_users(users)
    return True, "Role updated successfully."
def create_user(username, password, role="User") -> tuple[bool, str]:
    from security.passwords import validate_password_strength
    from security.validators import validate_username

    valid, msg = validate_username(username)
    if not valid:
        return False, msg

    valid, msg = validate_password_strength(password)
    if not valid:
        return False, msg

    if role not in VALID_ROLES:
        return False, f"Role must be one of {VALID_ROLES}."

    users = load_users()
    if username in users:
        return False, "Username already exists."

    users[username] = {"password": hash_password(password), "role": role}
    save_users(users)
    return True, "User created."

