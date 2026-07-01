$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& ".venv\Scripts\python.exe" "scripts\backup_restore.py" backup --version "1.0.0" @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
