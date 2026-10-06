# Builds dist\PhyloMapper.exe in a local virtual environment.
# Usage (from the project folder):  powershell -ExecutionPolicy Bypass -File .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
$python = ".venv\Scripts\python.exe"

& $python -m pip install --quiet -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed" }

& $python -m unittest
if ($LASTEXITCODE -ne 0) { throw "Tests failed, not building" }

& $python -m PyInstaller phylo-mapper.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "Built $(Resolve-Path dist\PhyloMapper.exe)"
