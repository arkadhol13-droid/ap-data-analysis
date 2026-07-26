
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
