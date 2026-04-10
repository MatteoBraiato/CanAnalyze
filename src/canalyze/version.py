from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
import tomllib


APP_NAME = "CAN Log Analyzer"
PACKAGE_NAME = "can-log-analyzer"
FALLBACK_VERSION = "0.2.0"


def _read_pyproject_version() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    with pyproject_path.open("rb") as handle:
        pyproject = tomllib.load(handle)
    return pyproject["project"]["version"]


def get_app_version() -> str:
    pyproject_version = _read_pyproject_version()
    if pyproject_version:
        return pyproject_version
    try:
        return package_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION
    except Exception:
        return FALLBACK_VERSION


__version__ = get_app_version()
