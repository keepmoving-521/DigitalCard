param(
    [string]$BaseUrl = "http://localhost:8000",
    [switch]$SkipLivePerformance
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& ".\scripts\check.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& ".\scripts\security-check.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& ".venv\Scripts\python.exe" -m alembic -c backend/alembic.ini heads
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $SkipLivePerformance) {
    & ".\scripts\performance-baseline.ps1" -BaseUrl $BaseUrl
}
Write-Host "V1.0 release gates passed." -ForegroundColor Green
