# Connect Gmail (read-only) so ZAENIA can summarise important email. One time only.
# Uses the same OAuth client as Google Calendar: data\google_calendar\credentials.json.
# First, in Google Cloud Console (same project): enable the "Gmail API" and add the
# scope ".../auth/gmail.readonly" to the OAuth consent screen.
# Your browser opens; sign in and click Allow. The sign-in stays on this PC.

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "ZAENIA - Connect Gmail (read-only)"

$Client = Join-Path $ProjectRoot "data\google_calendar\credentials.json"
if (-not (Test-Path $Client)) {
    Write-Host "First create a Google OAuth client (type: Desktop app) and save its JSON file as:"
    Write-Host "  $Client"
    Write-Host "Then run this again."
    Start-Sleep -Seconds 20
    exit 1
}

& $Python -m core.email_watch.gmail connect
Write-Host ""
Write-Host "You can close this window."
Start-Sleep -Seconds 8
