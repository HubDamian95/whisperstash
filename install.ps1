$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:WHISPERSTASH_REPO_URL) { $env:WHISPERSTASH_REPO_URL } else { "https://github.com/HubDamian95/whisperstash.git" }
$InstallDir = if ($env:WHISPERSTASH_HOME) { $env:WHISPERSTASH_HOME } else { Join-Path $env:LOCALAPPDATA "whisperstash" }
$BinDir = if ($env:WHISPERSTASH_BIN) { $env:WHISPERSTASH_BIN } else { Join-Path $env:USERPROFILE "bin" }

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

Require-Command git
Require-Command python

if (Test-Path (Join-Path $InstallDir ".git")) {
    git -C $InstallDir pull --ff-only | Out-Host
}
else {
    if (Test-Path $InstallDir) {
        Remove-Item -Recurse -Force $InstallDir
    }
    git clone $RepoUrl $InstallDir | Out-Host
}

python -m venv (Join-Path $InstallDir ".venv")
$Py = Join-Path $InstallDir ".venv\Scripts\python.exe"

& $Py -m pip install --upgrade pip | Out-Host
& $Py -m pip install cryptography | Out-Host

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$Launcher = Join-Path $BinDir "whisperstash.cmd"
@"
@echo off
"$Py" "$InstallDir\whisperstash.py" %*
"@ | Set-Content -Path $Launcher -Encoding ascii

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ([string]::IsNullOrEmpty($UserPath)) {
    $UserPath = ""
}

$BinDirNorm = [System.IO.Path]::GetFullPath($BinDir).TrimEnd('\')
$PathParts = $UserPath.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { $_.TrimEnd('\') }

if (-not ($PathParts -contains $BinDirNorm)) {
    $NewPath = if ([string]::IsNullOrEmpty($UserPath)) { $BinDirNorm } else { "$UserPath;$BinDirNorm" }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "Added $BinDirNorm to user PATH."
}

$SessionPathParts = $env:Path.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { $_.TrimEnd('\') }
if (-not ($SessionPathParts -contains $BinDirNorm)) {
    $env:Path = "$env:Path;$BinDirNorm"
    Write-Host "Updated PATH for current PowerShell session."
}

Write-Host ""
Write-Host "Installed WhisperStash."
Write-Host "Launcher: $Launcher"
Write-Host "Try now: whisperstash --help"
