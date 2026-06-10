# scripts/build_layer.ps1  — build the Lambda dependency layer (no Docker)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$dest = Join-Path $root "build/layer/python"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
& (Join-Path $root "backend/.venv/Scripts/python") -m pip install `
    -r (Join-Path $root "backend/requirements-lambda.txt") -t $dest
Write-Host "Layer built at $dest"
