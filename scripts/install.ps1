[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectPath,
    [ValidateSet('install', 'update', 'status', 'doctor', 'uninstall', 'restore')]
    [string]$Action = 'install',
    [ValidateSet('auto', 'generic', 'doctrine', 'runtime', 'console')]
    [string]$Profile = 'auto',
    [string]$Workspace,
    [switch]$ForceSettings,
    [switch]$InstallGlobal,
    [switch]$InstallManaged,
    [string]$ManagedDir,
    [switch]$InstallPythonControlPlane,
    [switch]$WithPythonSdk,
    [switch]$FullValidation,
    [switch]$SkipValidation,
    [switch]$DryRun,
    [switch]$Force,
    [string]$Backup,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Lifecycle = Join-Path $ScriptDir 'environment-lifecycle.py'
$Python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Python) { $Python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $Python) { throw 'Python 3.10 or later is required.' }

$Arguments = @($Lifecycle, $Action, $ProjectPath)
if ($Action -in @('install', 'update')) {
    $Arguments += @('--profile', $Profile)
    if ($Workspace) { $Arguments += @('--workspace', $Workspace) }
    if ($ForceSettings) { $Arguments += '--force-settings' }
    if ($InstallGlobal) { $Arguments += '--install-global' }
    if ($InstallManaged) { $Arguments += '--install-managed' }
    if ($ManagedDir) { $Arguments += @('--managed-dir', $ManagedDir) }
    if ($InstallPythonControlPlane) { $Arguments += '--install-python-control-plane' }
    if ($WithPythonSdk) { $Arguments += '--with-python-sdk' }
    if ($FullValidation) { $Arguments += '--full-validation' }
    if ($SkipValidation) { $Arguments += '--skip-validation' }
    if ($DryRun) { $Arguments += '--dry-run' }
} elseif ($Action -eq 'uninstall') {
    if ($Force) { $Arguments += '--force' }
    if ($DryRun) { $Arguments += '--dry-run' }
} elseif ($Action -eq 'restore') {
    if (-not $Backup) { throw '-Backup is required for restore.' }
    $Arguments += @('--backup', $Backup)
    if ($DryRun) { $Arguments += '--dry-run' }
} elseif ($Json) {
    $Arguments += '--json'
}

if ($Python.Name -match '^py(?:\.exe)?$') { & $Python.Source -3 @Arguments }
else { & $Python.Source @Arguments }
if ($LASTEXITCODE -ne 0) { throw "MAD Ventures environment $Action failed with exit code $LASTEXITCODE." }
