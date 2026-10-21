# ZÆNIA PC voice service: always listening on your approved microphone.
# It answers only your verified voice. After voice-only setup, startup uses
# Windows-protected enrollment. Leave this window open. Ctrl+C stops voice.

$ProjectRoot = "C:\Projects\ZAENIA"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "ZAENIA Voice"

# Only one voice service at a time.
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*voice_listener_main*' }
if ($running) {
    Write-Host "ZÆNIA voice is already running."
    Start-Sleep -Seconds 4
    exit 0
}

Write-Host ""
Write-Host "ZÆNIA Voice"
Write-Host "==========="
if (Test-Path -LiteralPath (Join-Path $ProjectRoot 'data/secure/voice_startup.dpapi')) {
    Write-Host 'Starting with Windows-protected enrollment. No passkey prompt; requests still verify your voice.'
} else {
    Write-Host 'Starting with your current passkey authentication. Voice requests also verify the enrolled speaker.'
}
Write-Host ""

& $Python -m core.voice_listener.voice_listener_main start
$code = $LASTEXITCODE

Write-Host ""
Write-Host "ZÆNIA voice stopped (exit $code)."
Read-Host "Press Enter to close this window"
exit $code
