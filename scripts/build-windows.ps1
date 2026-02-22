$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m venv .venv-build
$Py = Join-Path $Root ".venv-build\Scripts\python.exe"

& $Py -m pip install --upgrade pip
& $Py -m pip install pyinstaller cryptography

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

& $Py -m PyInstaller --onefile --name whisperstash whisperstash.py

New-Item -ItemType Directory -Force -Path dist\release | Out-Null
Copy-Item dist\whisperstash.exe dist\release\whisperstash-windows-x86_64.exe -Force
Write-Host "Built: dist\\release\\whisperstash-windows-x86_64.exe"
