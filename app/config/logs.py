"""The project log formatter (PR 78 review R1 P2, UNI-09). A traceback keeps its frames and each
exception's class, but never an exception's message: a database error can quote a row's values
(`Key (email)=(…) already exists`), and so can any message built from request data. Chained
exceptions (`__cause__`, `__context__`) are printed the same way."""

import logging
import traceback
from types import TracebackType

ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
CAUSE = "\nThe above exception was the direct cause of the following exception:\n\n"
CONTEXT = "\nDuring handling of the above exception, another exception occurred:\n\n"


def _name(exc: BaseException) -> str:
    kind = type(exc)
    if kind.__module__ in ("builtins", "__main__"):
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"


def _chain(exc: BaseException) -> list[tuple[BaseException, str]]:
    """Oldest first, each with the text that leads from it to the next (newer) one."""
    found: list[tuple[BaseException, str]] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    link = ""
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        found.append((current, link))
        if current.__cause__ is not None:
            current, link = current.__cause__, CAUSE
        elif current.__context__ is not None and not current.__suppress_context__:
            current, link = current.__context__, CONTEXT
        else:
            current = None
    return found[::-1]


class NoExceptionText(logging.Formatter):
    def formatException(self, ei: ExcInfo) -> str:
        if ei[1] is None:
            return ""
        parts: list[str] = []
        for exc, link in _chain(ei[1]):
            parts.append("Traceback (most recent call last):\n")
            parts.extend(traceback.format_list(traceback.extract_tb(exc.__traceback__)))
            parts.append(_name(exc) + "\n" + link)
        return "".join(parts).rstrip("\n")
