import logging
from typing import Optional

import pytest


def _get_console_formatter() -> Optional[logging.Formatter]:
    root = logging.getLogger()
    for h in root.handlers:
        fmt = getattr(h, "formatter", None)
        if isinstance(fmt, logging.Formatter):
            return fmt
    return None


@pytest.mark.asyncio
async def test_session_id_is_always_present(capsys):
    # Import here to avoid import-time side effects before capture is active
    from backend.utils import logging_config as lc

    # Ensure clean configuration
    lc.configure_logging(force=True)

    # When session id is set via context
    token = lc.set_session_id("session-abc123")
    try:
        logger = logging.getLogger("test.logger")
        logger.info("hello with session")
        # Flush handlers
        for h in logging.getLogger().handlers:
            try:
                h.flush()  # type: ignore[attr-defined]
            except Exception:
                pass
        out = capsys.readouterr().out
        assert "session=session-abc123" in out
    finally:
        lc.reset_session_id(token)

    # When session id is not set, default should be '-'
    logger = logging.getLogger("test.logger")
    logger.info("hello without session")
    for h in logging.getLogger().handlers:
        try:
            h.flush()  # type: ignore[attr-defined]
        except Exception:
            pass
    out2 = capsys.readouterr().out
    assert "session=-" in out2


def test_formatter_includes_timestamp_and_session():
    from backend.utils import logging_config as lc

    lc.configure_logging(force=True)

    fmt = _get_console_formatter()
    assert fmt is not None
    # Ensure asctime and session placeholder are part of the format
    f = fmt._fmt  # type: ignore[attr-defined]
    assert "%(asctime)s" in f
    assert "session=%(session_id)s" in f


def test_uvicorn_loggers_have_session_field(capsys):
    from backend.utils import logging_config as lc

    lc.configure_logging(force=True)

    # Emit from uvicorn-style loggers
    logging.getLogger("uvicorn").info("core")
    logging.getLogger("uvicorn.error").warning("err")
    logging.getLogger("uvicorn.access").info("access")

    # Flush handlers and capture stdout
    for h in logging.getLogger().handlers:
        try:
            h.flush()  # type: ignore[attr-defined]
        except Exception:
            pass
    out = capsys.readouterr().out
    assert "uvicorn" in out
    assert "session=-" in out
