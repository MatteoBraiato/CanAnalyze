param(
    [switch]$SkipVsDevShellBootstrap
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$deployExe = Join-Path $venvPath "Scripts\pyside6-deploy.exe"
$specPath = Join-Path $repoRoot "pysidedeploy.spec"
$buildRoot = Join-Path $repoRoot "build"
$generatedSpecPath = Join-Path $buildRoot "pysidedeploy.generated.spec"
$iconSourcePath = Join-Path $repoRoot "icon\icon.png"
$iconTargetPath = Join-Path $repoRoot "icon\icon.ico"
$iconGeneratorPath = Join-Path $PSScriptRoot "generate_windows_icon.py"
$distRoot = Join-Path $repoRoot "dist"
$bundleRoot = Join-Path $distRoot "CanAnalyze.dist"
$bundleExe = Join-Path $bundleRoot "CanAnalyze.exe"

function Test-CommandAvailable {
    param([string]$CommandName)

    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Get-VsWherePath {
    $vswherePath = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswherePath) {
        return $vswherePath
    }

    return $null
}

function Get-VsDevCmdPath {
    $vswherePath = Get-VsWherePath
    if ($vswherePath) {
        $installationPath = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -eq 0 -and $installationPath) {
            $candidate = Join-Path $installationPath "Common7\Tools\VsDevCmd.bat"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    $vsBasePath = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio"
    if (-not (Test-Path $vsBasePath)) {
        return $null
    }

    $editions = @("BuildTools", "Community", "Professional", "Enterprise")
    $versions = Get-ChildItem -Path $vsBasePath -Directory | Sort-Object Name -Descending

    foreach ($version in $versions) {
        foreach ($edition in $editions) {
            $candidate = Join-Path $version.FullName "$edition\Common7\Tools\VsDevCmd.bat"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    return $null
}

function Ensure-VisualStudioShell {
    if ($env:VSCMD_VER -or (Test-CommandAvailable "cl.exe") -or (Test-CommandAvailable "gcc.exe") -or (Test-CommandAvailable "clang.exe")) {
        return
    }

    if ($SkipVsDevShellBootstrap) {
        throw "No supported compiler is available after Visual Studio shell bootstrap. Install Microsoft C++ Build Tools with the VC tools component and Windows SDK."
    }

    $vsDevCmd = Get-VsDevCmdPath
    if (-not $vsDevCmd) {
        throw "Visual Studio developer shell was not found. Install Visual Studio Build Tools with the 'MSVC v143 x64/x86 build tools' component."
    }

    Write-Host "Initializing Visual Studio developer environment..."
    $scriptPath = $PSCommandPath
    $bootstrapCommand = "call `"$vsDevCmd`" -arch=x64 -host_arch=x64 && powershell.exe -ExecutionPolicy Bypass -File `"$scriptPath`" -SkipVsDevShellBootstrap"
    & cmd.exe /d /s /c $bootstrapCommand
    $bootstrapExitCode = $LASTEXITCODE
    if ($bootstrapExitCode -ne 0) {
        throw "Windows bundle build failed after initializing the Visual Studio developer environment with exit code $bootstrapExitCode."
    }

    exit 0
}

Ensure-VisualStudioShell

if (-not (Test-Path $pythonExe)) {
    throw "Windows virtual environment not found at '.venv-win'. Run .\scripts\setup_windows.ps1 first."
}

& $pythonExe -m pip install -e "${repoRoot}[packaging]"

if (-not (Test-Path $iconGeneratorPath)) {
    throw "Windows icon generator script was not found at '$iconGeneratorPath'."
}

if (-not (Test-Path $iconSourcePath)) {
    throw "PNG icon source was not found at '$iconSourcePath'."
}

& $pythonExe $iconGeneratorPath --source $iconSourcePath --output $iconTargetPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate Windows icon from '$iconSourcePath'."
}

if (-not (Test-Path $deployExe)) {
    throw "pyside6-deploy was not found in '.venv-win'. Ensure PySide6 is installed correctly."
}

if (-not (Test-CommandAvailable "cl.exe") -and -not (Test-CommandAvailable "gcc.exe") -and -not (Test-CommandAvailable "clang.exe")) {
    throw "No supported C compiler was found. Install Microsoft C++ Build Tools or a supported GCC/Clang toolchain before packaging with Nuitka."
}

if (-not (Test-CommandAvailable "dumpbin.exe")) {
    Write-Warning "dumpbin.exe was not found. Dependency discovery may be incomplete; install Visual Studio Build Tools if deployment misses Qt dependencies."
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
Copy-Item -Path $specPath -Destination $generatedSpecPath -Force

Push-Location $repoRoot
try {
    & $deployExe --force --config-file $generatedSpecPath
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

$smokeTestExitCode = -1
$env:CANALYZE_SMOKE_TEST = "1"
try {
    & $bundleExe
    $smokeTestExitCode = $LASTEXITCODE
}
finally {
    Remove-Item Env:CANALYZE_SMOKE_TEST -ErrorAction SilentlyContinue
}

if ($smokeTestExitCode -ne 0) {
    throw "Packaged smoke test failed with exit code $smokeTestExitCode."
}

Write-Host ""
Write-Host "Windows bundle created under:"
Write-Host "  $bundleRoot"
