$ErrorActionPreference = "Stop"

Set-Location "C:\Projects\ZAENIA"

$Python = ".\.venv\Scripts\python.exe"

Write-Host ""
Write-Host "ZÆNIA OneDrive CarPlay Bridge"
Write-Host "============================="
Write-Host ""

& $Python -m core.carplay_trigger.onedrive_bridge watch --poll 1.0