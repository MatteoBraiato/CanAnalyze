$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$buildRoot = Join-Path $repoRoot "build"
$installerBundleRoot = Join-Path $buildRoot "windows-installer-bundle\CanAnalyze.dist"
$resolvedBundlePathFile = Join-Path $buildRoot "windows-installer-bundle-path.txt"
$issPath = Join-Path $repoRoot "installer\CanAnalyze.iss"
$isccExe = $null

function Remove-PathWithRetry {
    param(
        [string]$Path,
        [int]$MaxAttempts = 10,
        [int]$DelayMilliseconds = 500,
        [switch]$IgnoreMissing
    )

    if (-not (Test-Path $Path)) {
        if ($IgnoreMissing) {
            return
        }

        throw "Path '$Path' was not found."
    }

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq $MaxAttempts) {
                throw "Failed to remove '$Path' after $MaxAttempts attempts. Last error: $($_.Exception.Message)"
            }

            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
}

function Remove-OptionalPath {
    param(
        [string]$Path,
        [string]$Description
    )

    try {
        Remove-PathWithRetry -Path $Path -IgnoreMissing
    }
    catch {
        Write-Warning "$Description could not be removed from '$Path'. $($_.Exception.Message)"
    }
}

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

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
Remove-OptionalPath -Path $resolvedBundlePathFile -Description "Previous installer bundle path file"

& (Join-Path $PSScriptRoot "build_windows_bundle.ps1") `
    -BundleOutputRoot $installerBundleRoot `
    -ResolvedBundlePathFile $resolvedBundlePathFile

if (-not (Test-Path $resolvedBundlePathFile)) {
    throw "The bundle build script did not write the resolved bundle path file at '$resolvedBundlePathFile'."
}

$resolvedBundleRoot = (Get-Content -Path $resolvedBundlePathFile -Raw).Trim()
if (-not $resolvedBundleRoot) {
    throw "The bundle build script returned an empty resolved bundle path."
}

if (-not (Test-Path $resolvedBundleRoot)) {
    throw "Expected Windows bundle not found at '$resolvedBundleRoot'."
}

$bundleExe = Join-Path $resolvedBundleRoot "CanAnalyze.exe"
if (-not (Test-Path $bundleExe)) {
    throw "Expected packaged executable not found at '$bundleExe'."
}

$appVersion = & $pythonExe -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"

Push-Location $repoRoot
try {
    & $isccExe "/DAppVersion=$appVersion" "/DSourceDir=$resolvedBundleRoot" $issPath
}
finally {
    Pop-Location
    Remove-OptionalPath -Path $resolvedBundlePathFile -Description "Temporary installer bundle path file"
}

if ($resolvedBundleRoot.StartsWith($installerBundleRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-OptionalPath -Path $installerBundleRoot -Description "Temporary installer bundle artifacts"
}

Write-Host ""
Write-Host "Windows installer created under:"
Write-Host "  $repoRoot\release"
