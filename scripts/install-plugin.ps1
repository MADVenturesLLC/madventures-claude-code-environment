[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('user', 'project')]
    [string]$Scope = 'user',

    [string]$ProjectPath,

    [switch]$Force,
    [switch]$AllowCoexistence,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$Source = Join-Path $Root 'plugin\madventures-founderos'
$Manifest = Join-Path $Source '.claude-plugin\plugin.json'
if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
    throw 'Built plugin is missing. Run: python scripts/build-plugin.py'
}

if ($Scope -eq 'user') {
    if (-not $HOME) { throw 'HOME is required for user scope.' }
    $Target = Join-Path $HOME '.claude\skills\madventures-founderos'
    $BackupBase = Join-Path $HOME '.claude\backups'
}
else {
    if (-not $ProjectPath) { throw '-ProjectPath is required for project scope.' }
    if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) { throw "Project directory does not exist: $ProjectPath" }
    $ProjectPath = (Resolve-Path $ProjectPath).Path
    if ((Test-Path -LiteralPath (Join-Path $ProjectPath '.claude\FOUNDEROS.md')) -and -not $AllowCoexistence) {
        throw 'The full project environment is already present. Use it instead, or pass -AllowCoexistence intentionally.'
    }
    $Target = Join-Path $ProjectPath '.claude\skills\madventures-founderos'
    $BackupBase = Join-Path $ProjectPath '.claude-backups'
}

if ($DryRun) {
    Write-Host "[MAD-PLUGIN] DRY RUN: would install plugin to $Target"
    exit 0
}

if ((Test-Path -LiteralPath $Target) -and -not $Force) {
    throw "Target already exists: $Target. Use -Force after reviewing the current copy."
}

$Timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
if (Test-Path -LiteralPath $Target) {
    New-Item -ItemType Directory -Force -Path $BackupBase | Out-Null
    $Backup = Join-Path $BackupBase "madventures-founderos-plugin-$Timestamp"
    Copy-Item -LiteralPath $Target -Destination $Backup -Recurse -Force
    Write-Host "[MAD-PLUGIN] Backed up existing plugin to $Backup"
    Remove-Item -LiteralPath $Target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
Copy-Item -LiteralPath $Source -Destination $Target -Recurse -Force
Write-Host "[MAD-PLUGIN] Installed portable plugin to $Target"
Write-Host "[MAD-PLUGIN] Restart Claude Code or run /reload-plugins. Verify with 'claude plugin list' and invoke /madventures-founderos:founder-command."
