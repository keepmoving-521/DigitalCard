$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python environment not found. Run .\scripts\setup.ps1 or .\scripts\setup-pip.ps1 first."
}

Set-Location $root
$env:PYTHONPATH = Join-Path $root "backend\src"
& $python -m digitalcard.cli create-admin @args

