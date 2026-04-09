$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$deployExe = Join-Path $venvPath "Scripts\pyside6-deploy.exe"
$specPath = Join-Path $repoRoot "pysidedeploy.spec"
$distRoot = Join-Path $repoRoot "dist"
$bundleRoot = Join-Path $distRoot "CanAnalyze"
$bundleExe = Join-Path $bundleRoot "CanAnalyze.exe"

function Test-CommandAvailable {
    param([string]$CommandName)

    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

if (-not (Test-Path $pythonExe)) {
    throw "Windows virtual environment not found at '.venv-win'. Run .\scripts\setup_windows.ps1 first."
}

& $pythonExe -m pip install -e "${repoRoot}[packaging]"

if (-not (Test-Path $deployExe)) {
    throw "pyside6-deploy was not found in '.venv-win'. Ensure PySide6 is installed correctly."
}

if (-not (Test-CommandAvailable "cl.exe") -and -not (Test-CommandAvailable "gcc.exe") -and -not (Test-CommandAvailable "clang.exe")) {
    throw "No supported C compiler was found. Install Microsoft C++ Build Tools or a supported GCC/Clang toolchain before packaging with Nuitka."
}

if (-not (Test-CommandAvailable "dumpbin.exe")) {
    Write-Warning "dumpbin.exe was not found. Dependency discovery may be incomplete; install Visual Studio Build Tools if deployment misses Qt dependencies."
}

Push-Location $repoRoot
try {
    & $deployExe --force $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "pyside6-deploy failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path $bundleExe)) {
    throw "Expected packaged executable was not found at '$bundleExe'."
}

Write-Host ""
Write-Host "Windows bundle created under:"
Write-Host "  $bundleRoot"
