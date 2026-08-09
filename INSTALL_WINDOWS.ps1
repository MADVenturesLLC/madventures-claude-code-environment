[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ProjectPath,

    [ValidateSet('auto', 'generic', 'doctrine', 'runtime', 'console')]
    [string]$Profile = 'auto',

    [switch]$InstallGlobal,
    [switch]$FullValidation
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $ProjectPath) {
    $ProjectPath = Read-Host 'Absolute path to the target repository'
}
if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
    throw "Target repository does not exist: $ProjectPath"
}

$Python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Python) { $Python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $Python) { throw 'Python 3.10+ is required.' }

if ($Python.Name -like 'py*') {
    & $Python.Source -3 (Join-Path $Root 'scripts\quick-validate.py')
} else {
    & $Python.Source (Join-Path $Root 'scripts\quick-validate.py')
}
if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }

$Arguments = @(
    '-ProjectPath', $ProjectPath,
    '-Profile', $Profile,
    '-InstallPythonControlPlane'
)
if ($InstallGlobal) { $Arguments += '-InstallGlobal' }
if ($FullValidation) { $Arguments += '-FullValidation' }

& (Join-Path $Root 'scripts\install.ps1') @Arguments
if ($LASTEXITCODE -ne 0) { throw 'Installation failed.' }

$InstalledClaude = Join-Path (Resolve-Path -LiteralPath $ProjectPath).Path '.claude'
Write-Host "Installed environment: $InstalledClaude"
Write-Host 'Next: run claude doctor, complete .claude\PROJECT_PROFILE.md, then run the madclaude auth check.'
if (Test-Path -LiteralPath $InstalledClaude) {
    Start-Process explorer.exe $InstalledClaude
}
