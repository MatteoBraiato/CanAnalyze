from __future__ import annotations

from typing import Any, Callable

from canalyze.compat import HAS_PYSIDE6

if HAS_PYSIDE6:
    from PySide6.QtCore import QThread, Signal
else:
    QThread = object

    class Signal:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


class FunctionWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)
