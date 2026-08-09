[CmdletBinding()]
param(
    [string]$InstallHome = (Join-Path $HOME '.madclaude'),
    [string]$BinDir = (Join-Path $HOME '.local\bin'),
    [string]$Python,
    [switch]$WithSdk,
    [switch]$NoDeps,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$SdkVersion = '0.2.131'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$SourceRoot = Join-Path $PackageRoot 'python-control-plane'

if (-not (Test-Path (Join-Path $SourceRoot 'bin\madclaude.py'))) {
    throw "Control-plane source not found: $SourceRoot"
}
if ($NoDeps) {
    Write-Host '[MADCLAUDE] NOTE: -NoDeps is deprecated; dependency-free installation is already the default.'
}

$PythonCommand = $null
$UsePyLauncher = $false
if ($Python) {
    $PythonCommand = $Python
    $UsePyLauncher = ((Split-Path -Leaf $PythonCommand) -match '^py(\.exe)?$')
} else {
    foreach ($Candidate in @('python3', 'python', 'py')) {
        $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
        if ($Command) {
            $PythonCommand = $Command.Source
            $UsePyLauncher = ($Candidate -eq 'py')
            break
        }
    }
}
if (-not $PythonCommand) { throw 'Python 3.10 or later is required.' }

function Invoke-BasePython {
    param([string[]]$Arguments)
    if ($UsePyLauncher) { & $PythonCommand -3 @Arguments }
    else { & $PythonCommand @Arguments }
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $($Arguments -join ' ')" }
}

Invoke-BasePython @('-c', 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)')
$InstallHome = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($InstallHome))
$BinDir = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($BinDir))
$Dest = Join-Path $InstallHome 'app'
$Venv = Join-Path $InstallHome 'venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$Wrapper = Join-Path $BinDir 'madclaude.cmd'

if ($DryRun) {
    Write-Host "[MADCLAUDE] DRY RUN: would create isolated Python environment at $Venv"
    Write-Host "[MADCLAUDE] DRY RUN: would atomically copy source to $Dest"
    Write-Host "[MADCLAUDE] DRY RUN: would install the package-identity manifest at $(Join-Path $InstallHome 'MANIFEST.json')"
    Write-Host "[MADCLAUDE] DRY RUN: would install wrapper at $Wrapper"
    Write-Host '[MADCLAUDE] DRY RUN: native `claude -p` subscription execution requires no Python dependencies'
    if ($WithSdk) {
        Write-Host "[MADCLAUDE] DRY RUN: would additionally install optional claude-agent-sdk==$SdkVersion for explicit API-billed SDK runs"
    } else {
        Write-Host '[MADCLAUDE] DRY RUN: would not install the optional Agent SDK'
    }
    Write-Host '[MADCLAUDE] DRY RUN: would not modify credentials or Claude authentication settings'
    return
}

New-Item -ItemType Directory -Path $InstallHome -Force | Out-Null
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
if (-not (Test-Path $VenvPython)) {
    Write-Host "[MADCLAUDE] Creating isolated environment: $Venv"
    Invoke-BasePython @('-m', 'venv', $Venv)
}

if ($WithSdk) {
    Write-Host "[MADCLAUDE] Installing optional Agent SDK $SdkVersion for the explicit API-billed backend..."
    & $VenvPython -m pip install --disable-pip-version-check --upgrade "claude-agent-sdk==$SdkVersion"
    if ($LASTEXITCODE -ne 0) { throw 'Agent SDK dependency installation failed.' }
    & $VenvPython -c "from importlib.metadata import version; actual=version('claude-agent-sdk'); assert actual == '$SdkVersion', actual; print('[MADCLAUDE] Verified optional claude-agent-sdk ' + actual)"
    if ($LASTEXITCODE -ne 0) { throw 'Agent SDK version verification failed.' }
} else {
    Write-Host '[MADCLAUDE] Dependency-free default: skipping Agent SDK installation.'
}

$Staging = Join-Path $InstallHome ".app.staging.$PID"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Path $Staging -Force | Out-Null
Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Staging -Recurse -Force
}
Get-ChildItem -LiteralPath $Staging -Directory -Filter '__pycache__' -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $Staging -File -Filter '*.pyc' -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force
if (Test-Path $Dest) {
    $Backup = Join-Path $InstallHome "app.backup.$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))"
    Move-Item -LiteralPath $Dest -Destination $Backup
    Write-Host "[MADCLAUDE] Backed up existing control plane: $Backup"
}
Move-Item -LiteralPath $Staging -Destination $Dest

# Package-identity manifest (R6-04): the immutable identity input hashed for
# release identity derivation, installed deliberately at the single explicit
# location the CLI resolves ($InstallHome\MANIFEST.json).
$IdentityManifest = Join-Path $PackageRoot 'MANIFEST.json'
if (-not (Test-Path $IdentityManifest)) { throw "Package identity manifest not found: $IdentityManifest" }
Copy-Item -LiteralPath $IdentityManifest -Destination (Join-Path $InstallHome 'MANIFEST.json') -Force

if (Test-Path $Wrapper) {
    $Backup = "$Wrapper.backup.$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))"
    Copy-Item -LiteralPath $Wrapper -Destination $Backup -Force
    Write-Host "[MADCLAUDE] Backed up existing wrapper: $Backup"
}
"@echo off`r`n`"$VenvPython`" `"$Dest\bin\madclaude.py`" %*`r`n" | Set-Content -LiteralPath $Wrapper -Encoding ascii

& $VenvPython (Join-Path $Dest 'bin\madclaude.py') --version
if ($LASTEXITCODE -ne 0) { throw 'Installed control-plane self-check failed.' }
Write-Host "[MADCLAUDE] Installed source: $Dest"
Write-Host "[MADCLAUDE] Installed wrapper: $Wrapper"
if ($WithSdk) {
    Write-Host "[MADCLAUDE] Optional Agent SDK $SdkVersion installed; the native CLI subscription backend remains the default."
} else {
    Write-Host '[MADCLAUDE] Installed with no third-party Python dependencies; native `claude -p` subscription execution is ready.'
}
Write-Host '[MADCLAUDE] Next: remove API/provider credential overrides from this process, run `claude auth login`, then `madclaude auth-check --repo C:\path\to\repo`.'
Write-Host '[MADCLAUDE] Credential preflight cannot prove model-specific entitlement, remaining allowance, or whether account-level usage credits are enabled. Python Fable routes add a separate fail-closed acknowledgement gate.'
