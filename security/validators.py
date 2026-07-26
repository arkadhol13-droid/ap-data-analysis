
import re
import unicodedata

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")

# SQL keywords that have no legitimate place in a read-only "run a SELECT
# against your own uploaded data" query studio. Blocking these mitigates
# SQL injection / data destruction / arbitrary file access via ATTACH.
_SQL_FORBIDDEN_KEYWORDS = re.compile(
    r"(?i)\b(ATTACH|DETACH|PRAGMA|DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|"
    r"REPLACE|VACUUM|REINDEX|EXEC|EXECUTE)\b"
)
def validate_username(username: str) -> tuple[bool, str]:
    if not username:
        return False, "Username is required."
    if not USERNAME_RE.match(username):
        return False, "Username must be 3-32 characters: letters, numbers, _ . -"
    return True, ""
def sanitize_text_input(value: str, max_length: int = 500) -> str:
    """
    Generic sanitizer for free-text fields (e.g. AI Insights question box).
    - Normalizes unicode (defends against homoglyph / normalization tricks)
    - Strips control/non-printable characters (defends against terminal
      injection, log injection, null-byte tricks)
    - Enforces a max length (defends against DoS via pathological input)
    NOTE: this does not attempt to strip HTML/JS -- that's Streamlit's
    job at render time. We only ever render user text via st.write /
    st.success / st.dataframe, which auto-escape by default. Never pass
    raw user input to unsafe_allow_html=True.
    """
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    value = "".join(ch for ch in value if ch.isprintable() or ch in ("\n", "\t"))
    return value[:max_length].strip()
def is_safe_sql_select(query: str) -> tuple[bool, str]:
    """
    Sandboxes the SQL Studio feature: only a single, read-only SELECT
    statement is permitted against the in-memory `dataset` table.
    Rejects multi-statement queries, DDL/DML, PRAGMA, and ATTACH (which
    can otherwise be used to open/write arbitrary files on disk).
    """
    if not query or not query.strip():
        return False, "Query cannot be empty."

    stripped = query.strip().rstrip(";")

    if ";" in stripped:
        return False, "Only a single SQL statement is allowed."

    if not re.match(r"(?is)^\s*(SELECT|WITH)\b", stripped):
        return False, "Only SELECT (or WITH ... SELECT) queries are allowed."

    if _SQL_FORBIDDEN_KEYWORDS.search(stripped):
        return False, "Query contains a keyword that is not permitted in read-only mode."

    return True, ""
def validate_uploaded_filename(filename: str, allowed_extensions=(".csv", ".xlsx")) -> tuple[bool, str]:
    """
    Defends against path traversal / unexpected file types even though
    Streamlit's file_uploader already sandboxes uploads to memory. This
    is a belt-and-suspenders check on the name itself.
    """
    if not filename:
        return False, "No filename provided."
    if "/" in filename or "\\" in filename or ".." in filename:
        return False, "Invalid filename."
    if not filename.lower().endswith(tuple(allowed_extensions)):
        return False, f"Only {', '.join(allowed_extensions)} files are allowed."
    return True, ""
