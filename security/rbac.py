"""
Role-Based Access Control helpers.

Every check reads the role from `st.session_state.role`, which is only
ever set in one place (auth/login.py, immediately after a successful
bcrypt credential check) from the server-side user store
(auth/users.py). The frontend never supplies or overrides a role -- a
person editing browser devtools or Streamlit's client-side state has
no way to change what's stored server-side in the session registry
(security/session_manager.py), and app.py re-validates that server-side
session on every single rerun before any page code executes.

Roles: Admin > Manager > User (Admin has all Manager+User permissions).
"""

import streamlit as st

ROLE_HIERARCHY = {"User": 0, "Manager": 1, "Admin": 2}


def current_role() -> str:
    return st.session_state.get("role", "User")


def has_role_at_least(minimum_role: str) -> bool:
    return ROLE_HIERARCHY.get(current_role(), -1) >= ROLE_HIERARCHY.get(minimum_role, 99)


def require_role(minimum_role: str) -> bool:
    """Renders a blocking error and returns False if the current session's
    role does not meet the minimum required role. Use at the top of any
    page/function that needs access control beyond the sidebar button
    visibility check."""
    if not has_role_at_least(minimum_role):
        st.error(f"🚫 Access denied. This section requires {minimum_role} role or higher.")
        return False
    return True
