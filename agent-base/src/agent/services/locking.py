"""Nonblocking per-session exclusion for this single-process local server."""

from contextlib import contextmanager
from threading import Lock

_guard = Lock()
_active: set[str] = set()


class SessionBusyError(RuntimeError):
    pass


@contextmanager
def session_guard(session_id: str):
    with _guard:
        if session_id in _active:
            raise SessionBusyError("这个会话正在回复，请稍后再试")
        _active.add(session_id)
    try:
        yield
    finally:
        with _guard:
            _active.discard(session_id)
