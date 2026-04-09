from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canalyze import __version__
from canalyze.version import APP_NAME


class VersionTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with pyproject_path.open("rb") as handle:
            project_version = tomllib.load(handle)["project"]["version"]

        self.assertEqual(__version__, project_version)

    def test_app_name_is_defined(self) -> None:
        self.assertEqual(APP_NAME, "CAN Log Analyzer")


if __name__ == "__main__":
    unittest.main()
