# Save Infomates OMS as Version 1.0.0
# Run: powershell -ExecutionPolicy Bypass -File scripts\save_version_1.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "Infomates OMS - Saving Version 1.0.0"
Write-Host "Project: $ProjectRoot"

$gitExe = $null
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitExe = "git"
}
elseif (Test-Path "C:\Program Files\Git\bin\git.exe") {
    $gitExe = "C:\Program Files\Git\bin\git.exe"
}

$commitMsg = "Release IOMS v1.0.0 - full OMS with quotations and finalized UI shell"

if ($gitExe) {
    & $gitExe add -A
    $status = & $gitExe status --porcelain
    if ($status) {
        & $gitExe commit -m $commitMsg
        Write-Host "Git commit created."
    }
    else {
        Write-Host "No new changes to commit."
    }
    $existingTag = & $gitExe tag -l "v1.0.0"
    if ($existingTag) {
        Write-Host "Tag v1.0.0 already exists."
    }
    else {
        & $gitExe tag -a v1.0.0 -m "IOMS Version 1.0.0 baseline"
        Write-Host "Git tag v1.0.0 created."
    }
}
else {
    Write-Host "Git not found - skipped commit and tag."
}

$releasesDir = Join-Path $ProjectRoot "releases"
New-Item -ItemType Directory -Force -Path $releasesDir | Out-Null
$zipPath = Join-Path $releasesDir "IOMS-v1.0.0.zip"
$tempDir = Join-Path $env:TEMP "ioms-v1-staging"

if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

Get-ChildItem $ProjectRoot -Force | Where-Object {
    $_.Name -ne "venv" -and $_.Name -ne ".git" -and $_.Name -ne "releases"
} | ForEach-Object {
    Copy-Item $_.FullName -Destination (Join-Path $tempDir $_.Name) -Recurse -Force
}

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipPath -Force
Remove-Item $tempDir -Recurse -Force

Write-Host "Archive: $zipPath"
Write-Host "Version 1.0.0 save complete."
