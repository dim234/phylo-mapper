# Builds dist\SeqGrove\ (the app folder) and dist\SeqGrove-windows.zip in a local virtual environment.
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

& $python -m PyInstaller seqgrove.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# The license files have to ship with the app, mainly for Qt (LGPLv3).
$app = "dist\SeqGrove"
Copy-Item LICENSE, THIRD_PARTY_LICENSES.md $app
Copy-Item licenses $app -Recurse -Force

$zip = "dist\SeqGrove-windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $app -DestinationPath $zip

Write-Host "Built $(Resolve-Path $app)\SeqGrove.exe"
Write-Host "Zipped $(Resolve-Path $zip)"
