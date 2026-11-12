# Restart the ZÆNIA API server (token mode) and check that it is listening.
# If it doesn't come up, it runs here in this window so you can see why.

$TaskName = "ZAENIA API Server"
$ProjectRoot = "C:\Projects\ZAENIA"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Port = 8766

function Test-Listening {
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host "Stopping the ZÆNIA server..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*core.api.server*server*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
# The task can't start again while its previous run is still finishing.
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
for ($i = 0; $i -lt 20 -and (Test-Listening); $i++) { Start-Sleep -Milliseconds 500 }

Write-Host "Starting the ZÆNIA server..."
Start-ScheduledTask -TaskName $TaskName
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Listening) {
        Write-Host ""
        Write-Host "ZÆNIA server is running (port $Port)."
        exit 0
    }
}

Write-Host ""
Write-Host "The server didn't start in the background. Running it here so you can see why."
Write-Host "If it starts, leave this window open (Ctrl+C stops it)."
Write-Host ""
Set-Location $ProjectRoot
& $Python -m core.api.server server --unattended
