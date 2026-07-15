$ErrorActionPreference = "Continue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PidFile = Join-Path $Root ".dev-pids.json"

function Stop-ProcessTree {
    param([int]$ProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $ProcessId -Force
    }
}

if (-not (Test-Path $PidFile)) {
    Write-Host "No .dev-pids.json found. Nothing to stop." -ForegroundColor Yellow
    exit 0
}

$processes = Get-Content $PidFile -Raw | ConvertFrom-Json
foreach ($item in $processes) {
    $proc = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Stopping $($item.name) pid=$($item.pid)"
        Stop-ProcessTree -ProcessId $item.pid
    }
}

Remove-Item $PidFile -Force
Write-Host "Stopped LLM-VulnHub dev processes." -ForegroundColor Green
