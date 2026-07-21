import json
import os

USER_FILE = "auth/users.json"


def load_users():

    if not os.path.exists(USER_FILE):

        default_users = {
            "admin": {
                "password": "admin123",
                "role": "Admin"
            },
            "user": {
                "password": "user123",
                "role": "User"
            }
        }

        with open(USER_FILE, "w") as f:
            json.dump(default_users, f, indent=4)

        return default_users

    with open(USER_FILE, "r") as f:
        return json.load(f)


def save_users(users):

    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)


def change_password(
    username,
    old_password,
    new_password
):

    users = load_users()

    if username not in users:
        return False

    if users[username]["password"] != old_password:
        return False

    users[username]["password"] = new_password

    save_users(users)

    return True


def admin_reset_password(
    target_user,
    new_password
):

    users = load_users()

    if target_user not in users:
        return False

    users[target_user]["password"] = new_password

    save_users(users)

    return True
