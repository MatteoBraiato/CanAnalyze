$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$deployExe = Join-Path $venvPath "Scripts\pyside6-deploy.exe"
$specPath = Join-Path $repoRoot "pysidedeploy.spec"

if (-not (Test-Path $pythonExe)) {
    throw "Windows virtual environment not found at '.venv-win'. Run .\scripts\setup_windows.ps1 first."
}

& $pythonExe -m pip install -e "${repoRoot}[packaging]"

if (-not (Test-Path $deployExe)) {
    throw "pyside6-deploy was not found in '.venv-win'. Ensure PySide6 is installed correctly."
}

Push-Location $repoRoot
try {
    & $deployExe --force $specPath
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Windows bundle created under:"
Write-Host "  $repoRoot\dist"
