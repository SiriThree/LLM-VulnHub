param(
    [switch]$SkipInstall,
    [switch]$SkipRedis,
    [int]$AnalysisWorkers = 2
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$PidFile = Join-Path $Root ".dev-pids.json"

function Start-DevProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$LogFile
    )

    $escapedCommand = "Set-Location -LiteralPath '$WorkingDirectory'; `$env:PYTHONUNBUFFERED='1'; $Command *> '$LogFile'"
    $process = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $escapedCommand) `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -PassThru

    [pscustomobject]@{
        name = $Name
        pid = $process.Id
        log = $LogFile
    }
}

if (Test-Path $PidFile) {
    Write-Host "Found existing $PidFile. Run scripts\stop-dev.ps1 first if the previous dev stack is still running." -ForegroundColor Yellow
}

if (-not (Test-Path (Join-Path $Backend ".venv\Scripts\python.exe"))) {
    Write-Host "Creating backend virtual environment..."
    Push-Location $Backend
    python -m venv .venv
    Pop-Location
}

if (-not $SkipInstall) {
    Write-Host "Installing backend dependencies..."
    Push-Location $Backend
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    Pop-Location

    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $Frontend
        npm install
        Pop-Location
    }
}

if (-not $SkipRedis) {
    Write-Host "Starting Redis with Docker Compose..."
    Push-Location $Root
    docker compose up -d redis
    Pop-Location
}

Write-Host "Starting LLM-VulnHub dev processes..."
$processes = @()

$processes += Start-DevProcess `
    -Name "backend-api" `
    -WorkingDirectory $Backend `
    -Command ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" `
    -LogFile (Join-Path $Backend "backend-dev.log")

$processes += Start-DevProcess `
    -Name "frontend" `
    -WorkingDirectory $Frontend `
    -Command "npm run dev" `
    -LogFile (Join-Path $Frontend "frontend-dev.log")

$processes += Start-DevProcess `
    -Name "celery-ingestion" `
    -WorkingDirectory $Backend `
    -Command ".\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q ingestion --loglevel=info --pool=solo" `
    -LogFile (Join-Path $Backend "celery-ingestion.log")

for ($i = 1; $i -le $AnalysisWorkers; $i++) {
    $processes += Start-DevProcess `
        -Name "celery-analysis-$i" `
        -WorkingDirectory $Backend `
        -Command ".\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q analysis --loglevel=info --pool=solo" `
        -LogFile (Join-Path $Backend "celery-analysis-$i.log")
}

$processes += Start-DevProcess `
    -Name "celery-review-notification" `
    -WorkingDirectory $Backend `
    -Command ".\.venv\Scripts\celery.exe -A app.worker.celery_app worker -Q review,notification --loglevel=info --pool=solo" `
    -LogFile (Join-Path $Backend "celery-review-notification.log")

$processes += Start-DevProcess `
    -Name "celery-beat" `
    -WorkingDirectory $Backend `
    -Command ".\.venv\Scripts\celery.exe -A app.worker.celery_app beat --loglevel=info --schedule celerybeat-schedule" `
    -LogFile (Join-Path $Backend "celery-beat.log")

$processes | ConvertTo-Json -Depth 3 | Set-Content -Path $PidFile -Encoding UTF8

Write-Host ""
Write-Host "LLM-VulnHub is starting." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:3000"
Write-Host "Backend docs: http://127.0.0.1:8000/docs"
Write-Host "PIDs saved to: $PidFile"
Write-Host "Stop all dev processes with: .\scripts\stop-dev.ps1"
Write-Host ""
Write-Host "Logs:"
$processes | ForEach-Object { Write-Host ("- {0}: {1}" -f $_.name, $_.log) }
