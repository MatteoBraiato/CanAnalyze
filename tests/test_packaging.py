from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class PackagingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_icon_assets_and_generator_exist(self) -> None:
        self.assertTrue((self.repo_root / "icon" / "icon.png").is_file())
        self.assertTrue((self.repo_root / "icon" / "icon.ico").is_file())
        self.assertTrue((self.repo_root / "scripts" / "generate_windows_icon.py").is_file())

    def test_bundle_script_bootstraps_visual_studio_and_invokes_nuitka_directly(self) -> None:
        script_text = (self.repo_root / "scripts" / "build_windows_bundle.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("[switch]$SkipVsDevShellBootstrap", script_text)
        self.assertIn('[string]$BundleOutputRoot', script_text)
        self.assertIn('[string]$ResolvedBundlePathFile', script_text)
        self.assertIn('[switch]$PassThru', script_text)
        self.assertIn("$script:BundleScriptBoundParameters = @{} + $PSBoundParameters", script_text)
        self.assertIn("function Restore-BootstrapParameters", script_text)
        self.assertIn("function Get-BootstrapParameterState", script_text)
        self.assertIn("CANALYZE_BUNDLE_BOOTSTRAP_PARAMETERS", script_text)
        self.assertIn("ConvertTo-Json -InputObject $forwardedParameters -Compress", script_text)
        self.assertIn("ConvertFrom-Json -InputObject $json", script_text)
        self.assertIn("$env:VSCMD_VER", script_text)
        self.assertIn("vswhere.exe", script_text)
        self.assertIn("VsDevCmd.bat", script_text)
        self.assertIn("Initializing Visual Studio developer environment", script_text)
        self.assertIn('$iconSourcePath = Join-Path $repoRoot "icon\\icon.png"', script_text)
        self.assertIn('$iconTargetPath = Join-Path $repoRoot "icon\\icon.ico"', script_text)
        self.assertIn('$iconGeneratorPath = Join-Path $PSScriptRoot "generate_windows_icon.py"', script_text)
        self.assertIn("& $pythonExe $iconGeneratorPath --source $iconSourcePath --output $iconTargetPath", script_text)
        self.assertIn('$tempBuildRoot = Join-Path $buildRoot "windows-bundle"', script_text)
        self.assertIn('$legacyDeployRoot = Join-Path $repoRoot "src\\canalyze\\deployment"', script_text)
        self.assertIn('$nuitkaCrashReportPath = Join-Path $repoRoot "nuitka-crash-report.xml"', script_text)
        self.assertIn("function Remove-PathWithRetry", script_text)
        self.assertIn("function Ensure-CleanDirectory", script_text)
        self.assertIn("function Remove-OptionalPath", script_text)
        self.assertIn('$stagedBundleRoot = Join-Path $tempBuildRoot "bundle-stage\\CanAnalyze.dist"', script_text)
        self.assertIn('$smokeTestLogPath = Join-Path $tempBuildRoot "smoke-test-startup.log"', script_text)
        self.assertIn('"-m"', script_text)
        self.assertIn('"nuitka"', script_text)
        self.assertIn('"--enable-plugin=pyside6"', script_text)
        self.assertIn('"--include-package=pyqtgraph"', script_text)
        self.assertIn('"--include-data-dir=$($repoRoot)\\icon=icon"', script_text)
        self.assertIn('"--include-module=PySide6.QtOpenGL"', script_text)
        self.assertIn('"--include-module=PySide6.QtSvg"', script_text)
        self.assertIn('"--include-module=PySide6.QtOpenGLWidgets"', script_text)
        self.assertNotIn("pyside6-deploy", script_text)
        self.assertIn('$defaultBundleRoot = Join-Path (Join-Path $repoRoot "dist") "CanAnalyze.dist"', script_text)
        self.assertIn('$bundleExe = Join-Path $bundleRoot "CanAnalyze.exe"', script_text)
        self.assertIn('$resolvedBundleRoot = $bundleRoot', script_text)
        self.assertIn('$resolvedBundleExe = $bundleExe', script_text)
        self.assertIn('$env:CANALYZE_SMOKE_TEST = "1"', script_text)
        self.assertIn('$env:CANALYZE_STARTUP_LOG_PATH = $smokeTestLogPath', script_text)
        self.assertIn("Using the staged validated bundle", script_text)
        self.assertIn('Write-Warning "Intermediate build artifacts were kept at \'$tempBuildRoot\' because the staged bundle is being used as the final output."', script_text)
        self.assertIn("function Write-ResolvedBundlePath", script_text)
        self.assertIn("[System.IO.File]::WriteAllText($ResolvedBundlePathFile, $BundlePath.Trim(), [System.Text.Encoding]::UTF8)", script_text)
        self.assertIn("Write-ResolvedBundlePath -BundlePath $resolvedBundleRoot", script_text)
        self.assertIn("if ($PassThru)", script_text)
        self.assertIn("Write-Output $resolvedBundleRoot", script_text)
        self.assertIn("Packaged smoke test failed with exit code", script_text)
        self.assertIn("if ($LASTEXITCODE -ne 0)", script_text)
        self.assertIn("Expected packaged executable was not found at '$resolvedBundleExe'", script_text)
        self.assertIn("Windows bundle build failed after initializing the Visual Studio developer environment", script_text)

    def test_installer_script_checks_for_packaged_executable(self) -> None:
        script_text = (self.repo_root / "scripts" / "build_windows_installer.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('$installerBundleRoot = Join-Path $buildRoot "windows-installer-bundle\\CanAnalyze.dist"', script_text)
        self.assertIn('$resolvedBundlePathFile = Join-Path $buildRoot "windows-installer-bundle-path.txt"', script_text)
        self.assertIn('-BundleOutputRoot $installerBundleRoot `', script_text)
        self.assertIn('-ResolvedBundlePathFile $resolvedBundlePathFile', script_text)
        self.assertIn("did not write the resolved bundle path file", script_text)
        self.assertIn("$resolvedBundleRoot = (Get-Content -Path $resolvedBundlePathFile -Raw).Trim()", script_text)
        self.assertIn("returned an empty resolved bundle path", script_text)
        self.assertNotIn("Select-Object -Last 1", script_text)
        self.assertIn('$bundleExe = Join-Path $resolvedBundleRoot "CanAnalyze.exe"', script_text)
        self.assertIn('"/DSourceDir=$resolvedBundleRoot"', script_text)
        self.assertIn("if ($resolvedBundleRoot.StartsWith($installerBundleRoot", script_text)
        self.assertIn('Remove-OptionalPath -Path $resolvedBundlePathFile -Description "Temporary installer bundle path file"', script_text)
        self.assertIn('Remove-OptionalPath -Path $installerBundleRoot -Description "Temporary installer bundle artifacts"', script_text)
        self.assertIn("Expected packaged executable not found", script_text)

    def test_installer_shortcuts_set_app_user_model_id(self) -> None:
        script_text = (self.repo_root / "installer" / "CanAnalyze.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn('AppUserModelID: "MatteoBraiatoLTE.CanAnalyze"', script_text)

    def test_packaging_dependencies_include_icon_generator_requirement(self) -> None:
        with (self.repo_root / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)

        packaging_deps = pyproject["project"]["optional-dependencies"]["packaging"]
        self.assertIn("Pillow>=10.0", packaging_deps)


if __name__ == "__main__":
    unittest.main()
