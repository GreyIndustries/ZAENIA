$ErrorActionPreference = "Stop"

Set-Location "C:\Projects\ZAENIA"

$Python = ".\.venv\Scripts\python.exe"

Write-Host ""
Write-Host "ZÆNIA CarPlay briefing refresh"
Write-Host "=============================="
Write-Host ""

# WSDOT remains the temporary traffic provider.
# Google Maps becomes the primary traffic provider in a
# later CarPlay step.
$env:WSDOT_API_KEY = [Environment]::GetEnvironmentVariable(
    "WSDOT_API_KEY",
    "User"
)

Write-Host "Refreshing Google Calendar..."

& $Python -m core.google_calendar_sync.google_calendar_sync_main sync --days 2

if ($LASTEXITCODE -ne 0) {
    Write-Warning "Google Calendar refresh failed. ZÆNIA will continue using locally available calendar data."
}

Write-Host ""
Write-Host "Generating fresh briefing with local Piper..."

& $Python -m core.carplay_audio.carplay_audio_main generate --force-traffic

if ($LASTEXITCODE -ne 0) {
    throw "ZÆNIA CarPlay briefing generation failed."
}

Write-Host ""
Write-Host "CarPlay briefing refresh complete."