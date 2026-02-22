$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m venv .venv-build
$Py = Join-Path $Root ".venv-build\Scripts\python.exe"

& $Py -m pip install --upgrade pip
& $Py -m pip install pyinstaller cryptography pillow

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

$IconPng = Join-Path $Root "Whisperstash_logo_small_128.png"
$IconIco = Join-Path $Root "dist\whisperstash.ico"

if (-not (Test-Path $IconPng)) {
    throw "Icon source not found: $IconPng"
}

New-Item -ItemType Directory -Force -Path dist | Out-Null
# Build a multi-size .ico to avoid generic icon fallback in some Windows views/caches.
& $Py -c "from PIL import Image; img = Image.open(r'$IconPng').convert('RGBA'); img.save(r'$IconIco', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

& $Py -m PyInstaller --clean --noconfirm --onefile --name whisperstash --icon "$IconIco" --add-data "whisperstash_ui;whisperstash_ui" whisperstash.py

New-Item -ItemType Directory -Force -Path dist\release | Out-Null
Copy-Item dist\whisperstash.exe dist\release\whisperstash-windows-x86_64.exe -Force
Write-Host "Built: dist\\release\\whisperstash-windows-x86_64.exe"
