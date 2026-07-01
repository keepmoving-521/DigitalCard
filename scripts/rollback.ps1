param(
    [Parameter(Mandatory = $true)][string]$Backup
)
$ErrorActionPreference = "Stop"
Write-Host "Stop the API before continuing. This restores the selected database backup." -ForegroundColor Yellow
$confirmation = Read-Host "Type RESTORE to continue"
if ($confirmation -ne "RESTORE") { throw "Rollback cancelled" }
& "$PSScriptRoot\restore.ps1" -Backup $Backup -Force
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Database restored. Deploy the matching application version, run migrations, then verify readiness." -ForegroundColor Yellow
