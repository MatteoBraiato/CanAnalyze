$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv-win\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Windows virtual environment not found at '.venv-win'. Run .\scripts\setup_windows.ps1 first."
}

& $pythonExe -c "import PySide6"
& $pythonExe -m canalyze
