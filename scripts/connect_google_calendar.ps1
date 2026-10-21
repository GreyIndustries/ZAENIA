# Connect Google Calendar for writing (two-way). One time only.
# Needs your OAuth client file (Desktop app) at data\google_calendar\credentials.json.
# Your browser opens; sign in and click Allow. The sign-in stays on this PC.

$ProjectRoot = "C:\Projects\ZAENIA"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "ZAENIA - Connect Google Calendar"

$Client = Join-Path $ProjectRoot "data\google_calendar\credentials.json"
if (-not (Test-Path $Client)) {
    Write-Host "First create a Google OAuth client (type: Desktop app) and save its JSON file as:"
    Write-Host "  $Client"
    Write-Host "Then run this again."
    Start-Sleep -Seconds 20
    exit 1
}

& $Python -m core.google_calendar_sync.google_calendar_api connect
Write-Host ""
Write-Host "You can close this window."
Start-Sleep -Seconds 8
