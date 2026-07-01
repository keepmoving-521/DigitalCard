$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$trackedEnv = git ls-files .env
if ($trackedEnv) {
    throw ".env must not be tracked by Git"
}
& ".venv\Scripts\python.exe" -m pytest backend/tests/test_security.py --no-cov
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Security release checks passed." -ForegroundColor Green
