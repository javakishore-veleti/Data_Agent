import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_APP_LOGGERS = ("agents", "utils", "__main__")
_HTTP_LOGGERS = ("httpx", "httpx2", "httpcore", "openai", "anthropic", "urllib3")
_configured = False


def configure_logging() -> None:
    """Read LOG_LEVEL (default INFO). App loggers follow it; HTTP clients stay WARNING."""
    global _configured
    if _configured:
        return
    _configured = True

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    for name in _APP_LOGGERS:
        logging.getLogger(name).setLevel(level)
    for name in _HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _messages_from(result):
    if result is None:
        return None
    if hasattr(result, "messages"):
        return result.messages
    if isinstance(result, dict):
        return result.get("messages")
    return None


def _content_to_text(content) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        joined = "\n".join(part for part in parts if part).strip()
        return joined or None
    return str(content).strip() or None


def last_ai_content(result) -> str | None:
    """Walk graph state (including nested subgraph dumps) for the last assistant text."""
    messages = _messages_from(result)
    if not messages:
        return None
    for item in reversed(messages):
        nested = _messages_from(item)
        if nested is not None and not hasattr(item, "content"):
            found = last_ai_content(item)
            if found:
                return found
            continue
        name = type(item).__name__
        if name in ("HumanMessage", "ToolMessage"):
            continue
        text = _content_to_text(getattr(item, "content", None))
        if text:
            return text
    return None


def log_run_result(logger: logging.Logger, result) -> None:
    """INFO: last assistant reply. DEBUG: full graph state."""
    text = last_ai_content(result)
    if text:
        logger.info("%s", text)
    else:
        logger.info("Run finished with no assistant message.")
    logger.debug("Full graph state: %s", result)


configure_logging()
