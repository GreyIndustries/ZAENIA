# ZAE watchdog (scheduled every 5 minutes by Self-Sustain): restarts her server
# in token mode if it stops answering twice in a row. Never touches passkey mode
# while the server is answering. Plain ASCII on purpose (Windows PowerShell 5).

$Root = Split-Path -Parent $PSScriptRoot
$State = Join-Path $Root "data\backups\watchdog.json"

function Answering {
    try { $null = Invoke-RestMethod -Uri "http://127.0.0.1:8766/health" -TimeoutSec 8; return $true } catch { return $false }
}

if (Answering) {
    Set-Content -Path $State -Value '{"misses": 0}' -Encoding ASCII
    exit 0
}
$misses = 0
try { $misses = [int]((Get-Content $State -Raw | ConvertFrom-Json).misses) } catch { }
$misses += 1
if ($misses -ge 2) {
    & (Join-Path $PSScriptRoot "restart_zaenia_server.ps1") | Out-Null
    $stamp = (Get-Date).ToUniversalTime().ToString("s")
    Set-Content -Path $State -Value ('{"misses": 0, "restartedAt": "' + $stamp + 'Z"}') -Encoding ASCII
} else {
    Set-Content -Path $State -Value ('{"misses": ' + $misses + '}') -Encoding ASCII
}
