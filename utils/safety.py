"""Fail-closed, local safety checks for graph nodes. No commercial eval products."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DATA_ROOTS = (
    (PROJECT_ROOT / "data" / "extract").resolve(),
    (PROJECT_ROOT / "data" / "transform").resolve(),
    (PROJECT_ROOT / "data").resolve(),
)
ALLOWED_FORMATS = {"csv", "json", "parquet"}
UNSAFE_SQL_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|EXECUTE|CALL|MERGE)\b",
    re.IGNORECASE,
)
UNSAFE_PYTHON_SNIPPETS = (
    "os.system",
    "os.popen",
    "subprocess",
    "eval(",
    "exec(",
    "__import__",
    "compile(",
    "socket",
    "requests.",
    "http.client",
    "open('/etc",
    "open(\"/etc",
    "pathlib.Path('/')",
)


def as_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content) if content is not None else ""


def normalize_sql(sql: str) -> str:
    text = as_text(sql).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def sql_keyword_eval(sql: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Fail closed on writes or stacked statements."""
    text = normalize_sql(sql)
    if not text:
        return False, "Generated SQL was empty."
    statements = [part.strip() for part in text.split(";") if part.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements are not allowed."
    match = UNSAFE_SQL_KEYWORDS.search(text)
    if match:
        return False, f"Blocked SQL keyword: {match.group(1).upper()}."
    return True, "SQL keyword check passed."


def path_is_under_data(path_str: str) -> tuple[bool, str]:
    if not path_str or not str(path_str).strip():
        return False, "Path is empty."
    raw = Path(path_str)
    resolved = raw.resolve() if raw.is_absolute() else (PROJECT_ROOT / raw).resolve()
    for root in ALLOWED_DATA_ROOTS:
        if resolved == root or root in resolved.parents:
            return True, ""
    return False, f"Path {resolved} is outside data/extract and data/transform."


def format_is_allowed(fmt: str) -> tuple[bool, str]:
    value = (fmt or "").lower().lstrip(".")
    if value in ALLOWED_FORMATS:
        return True, ""
    return False, f"Unsupported format: {fmt}. Allowed: {sorted(ALLOWED_FORMATS)}."


def url_is_http(url: str) -> tuple[bool, str]:
    parsed = urlparse(url or "")
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return True, ""
    return False, f"URL must be http(s) with a host: {url!r}."


def pandas_code_is_safe(code: str) -> tuple[bool, str]:
    text = as_text(code)
    lowered = text.lower()
    for snippet in UNSAFE_PYTHON_SNIPPETS:
        if snippet.lower() in lowered:
            return False, f"Blocked Python pattern: {snippet}."
    return True, "Pandas code check passed."


def validate_etl_tool(name: str, args: dict) -> tuple[bool, str]:
    args = args or {}
    if name == "extract_load_tool":
        ok, reason = url_is_http(str(args.get("url", "")))
        if not ok:
            return ok, reason
        ok, reason = path_is_under_data(str(args.get("output_folder", "")))
        if not ok:
            return ok, reason
        return format_is_allowed(str(args.get("format", "")))
    if name == "transform_load_tool":
        ok, reason = path_is_under_data(str(args.get("input_file_path", "")))
        if not ok:
            return ok, reason
        ok, reason = path_is_under_data(str(args.get("output_folder", "")))
        if not ok:
            return ok, reason
        return format_is_allowed(str(args.get("output_format", "")))
    return False, f"Unknown ETL tool: {name}."
