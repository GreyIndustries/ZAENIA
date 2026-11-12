# Connect Gmail to ZAENIA with a Google app password. One time only; no Google Cloud project needed.
# ZAE copies your mail to this PC (data\email\mail.db) so she can read and search all of it.
# Replies are drafts until you press Approve in the app.
#
# Before running: turn on 2-Step Verification for your Google account, then create an
# app password at https://myaccount.google.com/apppasswords. You type it here, at the PC only;
# it is sealed to your Windows account (data\secure\gmail_app_password.dpapi).

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "ZAENIA - Connect Gmail"

Start-Process "https://myaccount.google.com/apppasswords"
& $Python -m core.email_watch.imap_mail connect
Write-Host ""
Write-Host "You can close this window."
Start-Sleep -Seconds 12
