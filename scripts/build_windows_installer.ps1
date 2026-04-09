$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$issPath = Join-Path $repoRoot "installer\CanAnalyze.iss"
$distPath = Join-Path $repoRoot "dist\CanAnalyze"
$isccExe = $null

$candidateIscc = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

foreach ($candidate in $candidateIscc) {
    if (Test-Path $candidate) {
        $isccExe = $candidate
        break
    }
}

if (-not $isccExe) {
    $isccExe = (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
}

if (-not (Test-Path $pythonExe)) {
    throw "Windows virtual environment not found at '.venv-win'. Run .\scripts\setup_windows.ps1 first."
}

if (-not $isccExe) {
    throw "Inno Setup Compiler (ISCC.exe) was not found. Install Inno Setup 6 for Windows first."
}

& (Join-Path $PSScriptRoot "build_windows_bundle.ps1")

if (-not (Test-Path $distPath)) {
    throw "Expected Windows bundle not found at '$distPath'."
}

$appVersion = & $pythonExe -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"

Push-Location $repoRoot
try {
    & $isccExe "/DAppVersion=$appVersion" "/DSourceDir=$distPath" $issPath
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Windows installer created under:"
Write-Host "  $repoRoot\release"
