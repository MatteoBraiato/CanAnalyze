from __future__ import annotations

import configparser
import unittest
from pathlib import Path


class PackagingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_pyside6_deploy_spec_declares_required_config(self) -> None:
        config = configparser.ConfigParser()
        config.read(self.repo_root / "pysidedeploy.spec", encoding="utf-8")

        self.assertEqual(config.get("app", "input_file"), "src/canalyze/app.py")
        self.assertEqual(config.get("app", "icon"), r"icon\icon.ico")
        self.assertEqual(
            config.get("python", "packages"),
            "nuitka,ordered-set,zstandard",
        )
        self.assertEqual(config.get("nuitka", "mode"), "standalone")
        self.assertEqual(
            config.get("nuitka", "extra_args"),
            "--output-filename=CanAnalyze.exe --windows-console-mode=disable",
        )
        self.assertTrue((self.repo_root / "icon" / "icon.png").is_file())
        self.assertTrue((self.repo_root / "icon" / "icon.ico").is_file())

    def test_bundle_script_bootstraps_visual_studio_and_validates_output(self) -> None:
        script_text = (self.repo_root / "scripts" / "build_windows_bundle.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("[switch]$SkipVsDevShellBootstrap", script_text)
        self.assertIn("$env:VSCMD_VER", script_text)
        self.assertIn("vswhere.exe", script_text)
        self.assertIn("VsDevCmd.bat", script_text)
        self.assertIn("Initializing Visual Studio developer environment", script_text)
        self.assertIn('$generatedSpecPath = Join-Path $buildRoot "pysidedeploy.generated.spec"', script_text)
        self.assertIn("Copy-Item -Path $specPath -Destination $generatedSpecPath -Force", script_text)
        self.assertIn("& $deployExe --force --config-file $generatedSpecPath", script_text)
        self.assertIn('$bundleRoot = Join-Path $distRoot "CanAnalyze.dist"', script_text)
        self.assertIn('$bundleExe = Join-Path $bundleRoot "CanAnalyze.exe"', script_text)
        self.assertIn("if ($LASTEXITCODE -ne 0)", script_text)
        self.assertIn("Expected packaged executable was not found", script_text)
        self.assertIn("Windows bundle build failed after initializing the Visual Studio developer environment", script_text)

    def test_installer_script_checks_for_packaged_executable(self) -> None:
        script_text = (self.repo_root / "scripts" / "build_windows_installer.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$distPath = Join-Path $repoRoot "dist\\CanAnalyze.dist"', script_text)
        self.assertIn('$bundleExe = Join-Path $distPath "CanAnalyze.exe"', script_text)
        self.assertIn("Expected packaged executable not found", script_text)


if __name__ == "__main__":
    unittest.main()
