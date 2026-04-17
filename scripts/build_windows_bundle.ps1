param(
    [switch]$SkipVsDevShellBootstrap,
    [string]$BundleOutputRoot,
    [string]$ResolvedBundlePathFile,
    [switch]$PassThru
)

$ErrorActionPreference = "Stop"
$script:BundleScriptBoundParameters = @{} + $PSBoundParameters

function Restore-BootstrapParameters {
    if (-not $SkipVsDevShellBootstrap) {
        return
    }

    $encodedParameters = $env:CANALYZE_BUNDLE_BOOTSTRAP_PARAMETERS
    if ([string]::IsNullOrWhiteSpace($encodedParameters)) {
        return
    }

    try {
        $json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encodedParameters))
        $forwardedParameters = ConvertFrom-Json -InputObject $json

        foreach ($property in $forwardedParameters.PSObject.Properties) {
            switch ($property.Name) {
                "BundleOutputRoot" {
                    if ([string]::IsNullOrWhiteSpace($script:BundleOutputRoot)) {
                        $script:BundleOutputRoot = [string]$property.Value
                    }
                }
                "ResolvedBundlePathFile" {
                    if ([string]::IsNullOrWhiteSpace($script:ResolvedBundlePathFile)) {
                        $script:ResolvedBundlePathFile = [string]$property.Value
                    }
                }
                "PassThru" {
                    if (-not $script:PassThru -and [bool]$property.Value) {
                        $script:PassThru = $true
                    }
                }
            }
        }
    }
    finally {
        Remove-Item Env:CANALYZE_BUNDLE_BOOTSTRAP_PARAMETERS -ErrorAction SilentlyContinue
    }
}

function Get-BootstrapParameterState {
    param([hashtable]$BoundParameters)

    $forwardedParameters = [ordered]@{}
    foreach ($entry in $BoundParameters.GetEnumerator()) {
        if ($entry.Key -eq "SkipVsDevShellBootstrap") {
            continue
        }

        if ($entry.Value -is [System.Management.Automation.SwitchParameter]) {
            if ($entry.Value.IsPresent) {
                $forwardedParameters[$entry.Key] = $true
            }

            continue
        }

        if ($null -eq $entry.Value) {
            continue
        }

        if ($entry.Value -is [string] -and [string]::IsNullOrWhiteSpace($entry.Value)) {
            continue
        }

        $forwardedParameters[$entry.Key] = [string]$entry.Value
    }

    return $forwardedParameters
}

Restore-BootstrapParameters

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $repoRoot ".venv-win"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$buildRoot = Join-Path $repoRoot "build"
$tempBuildRoot = Join-Path $buildRoot "windows-bundle"
$nuitkaOutputRoot = Join-Path $tempBuildRoot "output"
$stagedBundleRoot = Join-Path $tempBuildRoot "bundle-stage\CanAnalyze.dist"
$legacyDeployRoot = Join-Path $repoRoot "src\canalyze\deployment"
$nuitkaCrashReportPath = Join-Path $repoRoot "nuitka-crash-report.xml"
$iconSourcePath = Join-Path $repoRoot "icon\icon.png"
$iconTargetPath = Join-Path $repoRoot "icon\icon.ico"
$iconGeneratorPath = Join-Path $PSScriptRoot "generate_windows_icon.py"
$entryPointPath = Join-Path $repoRoot "src\canalyze\app.py"
$defaultBundleRoot = Join-Path (Join-Path $repoRoot "dist") "CanAnalyze.dist"
if ([string]::IsNullOrWhiteSpace($BundleOutputRoot)) {
    $BundleOutputRoot = $defaultBundleRoot
}

$bundleRoot = $BundleOutputRoot
$bundleExe = Join-Path $bundleRoot "CanAnalyze.exe"
$stagedBundleExe = Join-Path $stagedBundleRoot "CanAnalyze.exe"
$smokeTestLogPath = Join-Path $tempBuildRoot "smoke-test-startup.log"
$resolvedBundleRoot = $bundleRoot
$resolvedBundleExe = $bundleExe
$publishWarning = $null

function Test-CommandAvailable {
    param([string]$CommandName)

    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

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

function Ensure-CleanDirectory {
    param([string]$Path)

    Remove-PathWithRetry -Path $Path -IgnoreMissing
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
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

function Write-ResolvedBundlePath {
    param([string]$BundlePath)

    if ([string]::IsNullOrWhiteSpace($ResolvedBundlePathFile)) {
        return
    }

    $resolvedBundlePathDirectory = Split-Path -Parent $ResolvedBundlePathFile
    if ($resolvedBundlePathDirectory) {
        New-Item -ItemType Directory -Path $resolvedBundlePathDirectory -Force | Out-Null
    }

    [System.IO.File]::WriteAllText($ResolvedBundlePathFile, $BundlePath.Trim(), [System.Text.Encoding]::UTF8)
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
    $forwardedParameters = Get-BootstrapParameterState -BoundParameters $script:BundleScriptBoundParameters

    if ($forwardedParameters.Count -gt 0) {
        $bootstrapParameterJson = ConvertTo-Json -InputObject $forwardedParameters -Compress
        $env:CANALYZE_BUNDLE_BOOTSTRAP_PARAMETERS = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($bootstrapParameterJson))
    }
    else {
        Remove-Item Env:CANALYZE_BUNDLE_BOOTSTRAP_PARAMETERS -ErrorAction SilentlyContinue
    }

    try {
        $bootstrapCommand = "call `"$vsDevCmd`" -arch=x64 -host_arch=x64 && powershell.exe -ExecutionPolicy Bypass -File `"$scriptPath`" -SkipVsDevShellBootstrap"
        & cmd.exe /d /s /c $bootstrapCommand
        $bootstrapExitCode = $LASTEXITCODE
        if ($bootstrapExitCode -ne 0) {
            throw "Windows bundle build failed after initializing the Visual Studio developer environment with exit code $bootstrapExitCode."
        }

        exit 0
    }
    finally {
        Remove-Item Env:CANALYZE_BUNDLE_BOOTSTRAP_PARAMETERS -ErrorAction SilentlyContinue
    }
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

Remove-OptionalPath -Path $legacyDeployRoot -Description "Legacy deploy artifacts"
Remove-OptionalPath -Path $nuitkaCrashReportPath -Description "Previous Nuitka crash report"

& $pythonExe $iconGeneratorPath --source $iconSourcePath --output $iconTargetPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate Windows icon from '$iconSourcePath'."
}

if (-not (Test-CommandAvailable "cl.exe") -and -not (Test-CommandAvailable "gcc.exe") -and -not (Test-CommandAvailable "clang.exe")) {
    throw "No supported C compiler was found. Install Microsoft C++ Build Tools or a supported GCC/Clang toolchain before packaging with Nuitka."
}

if (-not (Test-CommandAvailable "dumpbin.exe")) {
    Write-Warning "dumpbin.exe was not found. Dependency discovery may be incomplete; install Visual Studio Build Tools if deployment misses Qt dependencies."
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
Ensure-CleanDirectory -Path $tempBuildRoot
Remove-OptionalPath -Path $smokeTestLogPath -Description "Previous smoke-test log"

$nuitkaArguments = @(
    "-m",
    "nuitka",
    $entryPointPath,
    "--follow-imports",
    "--enable-plugin=pyside6",
    "--output-dir=$nuitkaOutputRoot",
    "--output-filename=CanAnalyze.exe",
    "--windows-console-mode=disable",
    "--include-package=pyqtgraph",
    "--include-data-dir=$($repoRoot)\icon=icon",
    "--include-module=PySide6.QtOpenGL",
    "--include-module=PySide6.QtSvg",
    "--include-module=PySide6.QtOpenGLWidgets",
    "--include-qt-plugins=platforminputcontexts",
    "--windows-icon-from-ico=$iconTargetPath",
    "--standalone",
    "--noinclude-dlls=*.cpp.o",
    "--noinclude-dlls=*.qsb"
)

$keepBuildArtifacts = $true
try {
    Push-Location $repoRoot
    try {
        & $pythonExe @nuitkaArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Nuitka packaging failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    $nuitkaDistRoot = Join-Path $nuitkaOutputRoot "app.dist"
    if (-not (Test-Path $nuitkaDistRoot)) {
        throw "Expected Nuitka bundle directory was not found at '$nuitkaDistRoot'."
    }

    New-Item -ItemType Directory -Path $stagedBundleRoot -Force | Out-Null
    Copy-Item -Path (Join-Path $nuitkaDistRoot "*") -Destination $stagedBundleRoot -Recurse -Force

    if (-not (Test-Path $stagedBundleExe)) {
        throw "Expected staged packaged executable was not found at '$stagedBundleExe'."
    }

    $smokeTestExitCode = -1
    $env:CANALYZE_SMOKE_TEST = "1"
    $env:CANALYZE_STARTUP_LOG_PATH = $smokeTestLogPath
    try {
        & $stagedBundleExe
        $smokeTestExitCode = $LASTEXITCODE
    }
    finally {
        Remove-Item Env:CANALYZE_SMOKE_TEST -ErrorAction SilentlyContinue
        Remove-Item Env:CANALYZE_STARTUP_LOG_PATH -ErrorAction SilentlyContinue
    }

    if ($smokeTestExitCode -ne 0) {
        $smokeTestError = ""
        if (Test-Path $smokeTestLogPath) {
            $smokeTestError = Get-Content -Path $smokeTestLogPath -Raw
        }

        if ($smokeTestError) {
            throw "Packaged smoke test failed with exit code $smokeTestExitCode.`n$smokeTestError"
        }

        throw "Packaged smoke test failed with exit code $smokeTestExitCode."
    }

    $bundleOutputParent = Split-Path -Parent $bundleRoot
    if ($bundleOutputParent) {
        New-Item -ItemType Directory -Path $bundleOutputParent -Force | Out-Null
    }

    try {
        if (Test-Path $bundleRoot) {
            Remove-PathWithRetry -Path $bundleRoot
        }

        New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null
        Copy-Item -Path (Join-Path $stagedBundleRoot "*") -Destination $bundleRoot -Recurse -Force
        $resolvedBundleRoot = $bundleRoot
        $resolvedBundleExe = $bundleExe
    }
    catch {
        $resolvedBundleRoot = $stagedBundleRoot
        $resolvedBundleExe = $stagedBundleExe
        $publishWarning = "Failed to publish the validated bundle to '$bundleRoot'. Using the staged validated bundle at '$stagedBundleRoot' instead. Last error: $($_.Exception.Message)"
    }

    if (-not (Test-Path $resolvedBundleExe)) {
        throw "Expected packaged executable was not found at '$resolvedBundleExe'."
    }

    Write-ResolvedBundlePath -BundlePath $resolvedBundleRoot

    Remove-OptionalPath -Path $legacyDeployRoot -Description "Legacy deploy artifacts"
    Remove-OptionalPath -Path $nuitkaCrashReportPath -Description "Nuitka crash report"
    $keepBuildArtifacts = $null -ne $publishWarning
}
finally {
    if ($keepBuildArtifacts) {
        Write-Warning "Intermediate build artifacts were kept at '$tempBuildRoot' because the staged bundle is being used as the final output."
    }
    else {
        Remove-OptionalPath -Path $tempBuildRoot -Description "Temporary Nuitka build artifacts"
    }
}

if ($publishWarning) {
    Write-Warning $publishWarning
}

Write-Host ""
Write-Host "Windows bundle created under:"
Write-Host "  $resolvedBundleRoot"

if ($PassThru) {
    Write-Output $resolvedBundleRoot
}
