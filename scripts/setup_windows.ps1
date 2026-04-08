$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "The Windows Python launcher 'py' was not found. Install Python 3.12+ for Windows first."
}

if (-not (Test-Path $pythonExe)) {
    & py -3.12 -m venv $venvPath
}

& $pythonExe -m pip install --upgrade pip setuptools wheel
& $pythonExe -m pip install -e "${repoRoot}[dev]"

Write-Host ""
Write-Host "Windows environment is ready:"
Write-Host "  $pythonExe -m canalyze"
