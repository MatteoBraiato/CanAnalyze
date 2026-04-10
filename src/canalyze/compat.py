"""Optional dependency helpers."""

from __future__ import annotations

from importlib import import_module


def dependency_available(module_name: str) -> bool:
    try:
        import_module(module_name)
    except ImportError:
        return False
    return True


HAS_CANTOOLS = dependency_available("cantools")
HAS_NUMPY = dependency_available("numpy")
HAS_PANDAS = dependency_available("pandas")
HAS_PYSIDE6 = dependency_available("PySide6")
HAS_PYQTGRAPH = dependency_available("pyqtgraph")
