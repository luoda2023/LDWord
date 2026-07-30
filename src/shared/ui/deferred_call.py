"""Safe next-event-loop calls for Qt lifecycle-sensitive UI mutations."""

from __future__ import annotations

import weakref

from shiboken6 import isValid

from src.qt_api import QTimer


_PENDING_CALLS: set[tuple[int, str, str, str]] = set()


def defer_qt_method(target, method_name: str, *args, **kwargs) -> None:
    """Invoke a Qt object's method later, provided its C++ object still exists."""

    target_ref = weakref.ref(target)
    pending_key = (
        id(target),
        str(method_name),
        repr(args),
        repr(tuple(sorted(kwargs.items(), key=lambda item: str(item[0])))),
    )
    if pending_key in _PENDING_CALLS:
        return
    _PENDING_CALLS.add(pending_key)

    def invoke() -> None:
        try:
            owner = target_ref()
            if owner is None or not isValid(owner):
                return
            method = getattr(owner, method_name, None)
            if callable(method):
                method(*args, **kwargs)
        finally:
            _PENDING_CALLS.discard(pending_key)

    QTimer.singleShot(0, invoke)


__all__ = ["defer_qt_method"]
