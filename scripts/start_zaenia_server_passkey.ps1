# Start the ZAENIA API server unlocked with the owner passkey (full mode).
# Opened by the desktop app in its own window, so you can type the passkey.
# If the server is already running in token mode it is stopped first.

$ProjectRoot = "C:\Projects\ZAENIA"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Port = 8766
$TaskName = "ZAENIA API Server"

Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "ZAENIA Server (passkey)"

function Test-Listening {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (Test-Listening) {
    Write-Host "Stopping the server that is already running..."
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*core.api.server*server*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 20 -and (Test-Listening); $i++) { Start-Sleep -Milliseconds 500 }
}

Write-Host ""
Write-Host "ZAENIA Server"
Write-Host "============"
Write-Host "Enter your passkey below to start ZAENIA with full owner features."
Write-Host "Leave this window open (you can minimise it). Ctrl+C stops the server."
Write-Host ""

& $Python -m core.api.server server
$code = $LASTEXITCODE
Write-Host ""
Write-Host "ZAENIA server stopped (exit $code)."
Start-Sleep -Seconds 5
