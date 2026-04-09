from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
import tomllib


APP_NAME = "CAN Log Analyzer"
PACKAGE_NAME = "can-log-analyzer"


def get_app_version() -> str:
    try:
        return package_version(PACKAGE_NAME)
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject_path.open("rb") as handle:
            pyproject = tomllib.load(handle)
        return pyproject["project"]["version"]


__version__ = get_app_version()
