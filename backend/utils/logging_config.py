import logging
import logging.config
import os
from contextvars import ContextVar
from typing import Optional


# Context variable to track the current session id
SESSION_ID_VAR: ContextVar[str] = ContextVar("session_id", default="-")


class SessionContextFilter(logging.Filter):
    """Logging filter that injects a session_id into every record.

    - Uses a contextvar to populate session id across async tasks.
    - Falls back to '-' when not set.
    - Respects an explicit record.session_id if provided via the 'extra' dict.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if not hasattr(record, "session_id") or record.session_id in (None, ""):
            try:
                record.session_id = SESSION_ID_VAR.get()
            except Exception:
                record.session_id = "-"
        return True


_CONFIGURED = False


def _level_from_env() -> str:
    lvl = os.getenv("LOG_LEVEL", "INFO").upper()
    valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
    return lvl if lvl in valid else "INFO"


def configure_logging(force: bool = False) -> None:
    """Configure application logging in a centralized, idempotent way.

    - Text format with clear timestamp by default.
    - Ensures every record has a session id in output.
    - Applies to uvicorn and application loggers without breaking propagation.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    # Optional: allow future extension for JSON format
    log_format = os.getenv("LOG_FORMAT", "text").lower()

    if log_format != "text":
        # For now default/fallback to text format
        log_format = "text"

    # Clear root handlers if forcing reconfigure
    if force:
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)

    level = _level_from_env()

    # Common, human-readable format with timestamp and session id
    fmt_text = "%(asctime)s %(levelname)s %(name)s [session=%(session_id)s]: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S%z"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "session": {
                    "()": SessionContextFilter,
                }
            },
            "formatters": {
                "text": {
                    "format": fmt_text,
                    "datefmt": datefmt,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": "text",
                    "filters": ["session"],
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
            # Ensure uvicorn loggers inherit config and get the session filter
            "loggers": {
                "uvicorn": {"level": level, "propagate": True},
                "uvicorn.error": {"level": level, "propagate": True},
                "uvicorn.access": {"level": level, "propagate": True},
            },
        }
    )

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger using the centralized configuration."""
    return logging.getLogger(name) if name else logging.getLogger()


def set_session_id(session_id: str):
    """Set the session id for the current context and return the token."""
    return SESSION_ID_VAR.set(session_id or "-")


def reset_session_id(token) -> None:
    """Reset the session id using the provided token returned by set_session_id."""
    try:
        SESSION_ID_VAR.reset(token)
    except Exception:
        # If reset fails, ensure a safe default
        SESSION_ID_VAR.set("-")

