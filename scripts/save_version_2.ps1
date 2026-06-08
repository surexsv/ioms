# Save Infomates OMS Version 2.0.0 (Document Number Generator)
# Run: powershell -ExecutionPolicy Bypass -File scripts\save_version_2.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "Infomates OMS - Saving Version 2.0.0"
$releasesDir = Join-Path $ProjectRoot "releases"
New-Item -ItemType Directory -Force -Path $releasesDir | Out-Null
$zipPath = Join-Path $releasesDir "IOMS-v2.0.0.zip"
$tempDir = Join-Path $env:TEMP "ioms-v2-staging"

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
Write-Host "Version 2.0.0 save complete."
