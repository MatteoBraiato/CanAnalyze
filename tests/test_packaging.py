from __future__ import annotations

import configparser
import unittest
from pathlib import Path


class PackagingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_pyside6_deploy_spec_declares_required_python_packages(self) -> None:
        config = configparser.ConfigParser()
        config.read(self.repo_root / "pysidedeploy.spec", encoding="utf-8")

        self.assertEqual(
            config.get("python", "packages"),
            "nuitka,ordered-set,zstandard",
        )
        self.assertEqual(config.get("nuitka", "mode"), "standalone")

    def test_bundle_script_validates_exit_code_and_executable(self) -> None:
        script_text = (self.repo_root / "scripts" / "build_windows_bundle.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$bundleExe = Join-Path $bundleRoot "CanAnalyze.exe"', script_text)
        self.assertIn("if ($LASTEXITCODE -ne 0)", script_text)
        self.assertIn("Expected packaged executable was not found", script_text)

    def test_installer_script_checks_for_packaged_executable(self) -> None:
        script_text = (self.repo_root / "scripts" / "build_windows_installer.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$bundleExe = Join-Path $distPath "CanAnalyze.exe"', script_text)
        self.assertIn("Expected packaged executable not found", script_text)


if __name__ == "__main__":
    unittest.main()
