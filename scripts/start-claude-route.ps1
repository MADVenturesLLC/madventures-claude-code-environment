[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('fanout','everyday','deep','planning','judgment','max-judgment','best-available','advisor','ultracode','review')]
    [string]$Profile,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ClaudeArgs
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    throw 'claude CLI was not found in PATH.'
}

$oldEffort = $env:CLAUDE_CODE_EFFORT_LEVEL
try {
    Remove-Item Env:CLAUDE_CODE_EFFORT_LEVEL -ErrorAction SilentlyContinue
    $baseArgs = @()

    switch ($Profile) {
        'fanout' {
            $baseArgs = @('--model', 'haiku')
        }
        'everyday' {
            $baseArgs = @('--model', 'sonnet', '--effort', 'high')
        }
        'deep' {
            $baseArgs = @('--model', 'opus', '--effort', 'xhigh')
        }
        'planning' {
            $baseArgs = @('--model', 'fable', '--effort', 'high', '--permission-mode', 'plan')
        }
        'judgment' {
            $baseArgs = @('--model', 'fable', '--effort', 'xhigh')
        }
        'max-judgment' {
            $baseArgs = @('--model', 'fable', '--effort', 'max')
        }
        'best-available' {
            $baseArgs = @('--model', 'best', '--effort', 'xhigh')
        }
        'advisor' {
            $baseArgs = @('--model', 'sonnet', '--effort', 'high', '--advisor', 'opus')
        }
        'ultracode' {
            $baseArgs = @('--model', 'best', '--effort', 'ultracode')
        }
        'review' {
            $settings = Join-Path (Get-Location) '.claude\profiles\review-only.settings.json'
            if (-not (Test-Path -LiteralPath $settings)) {
                throw "Missing $settings; install the full project environment first."
            }
            $baseArgs = @('--settings', $settings, '--model', 'fable', '--effort', 'xhigh', '--permission-mode', 'plan')
        }
    }

    & claude @baseArgs @ClaudeArgs
    exit $LASTEXITCODE
}
finally {
    if ($null -eq $oldEffort) {
        Remove-Item Env:CLAUDE_CODE_EFFORT_LEVEL -ErrorAction SilentlyContinue
    } else {
        $env:CLAUDE_CODE_EFFORT_LEVEL = $oldEffort
    }
}
