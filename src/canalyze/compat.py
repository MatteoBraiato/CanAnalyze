"""Optional dependency helpers."""

from __future__ import annotations

from importlib.util import find_spec


def dependency_available(module_name: str) -> bool:
    return find_spec(module_name) is not None


HAS_CANTOOLS = dependency_available("cantools")
HAS_NUMPY = dependency_available("numpy")
HAS_PANDAS = dependency_available("pandas")
HAS_PYSIDE6 = dependency_available("PySide6")
HAS_PYQTGRAPH = dependency_available("pyqtgraph")
