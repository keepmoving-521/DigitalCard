param(
    [Parameter(Mandatory = $true)][string]$Backup,
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$arguments = @("scripts\backup_restore.py", "restore", $Backup)
if ($Force) { $arguments += "--force" }
& ".venv\Scripts\python.exe" @arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
