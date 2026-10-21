param(
  [Parameter(Mandatory=$true)][ValidateSet('export','restore','rollback','voice_only')][string]$Mode,
  [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{32}$')][string]$Request
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
Set-Location -LiteralPath $projectRoot
if ($Mode -eq 'voice_only') {
  & $projectPython -m core.voice_security.voice_only enable
  if ($LASTEXITCODE -eq 0) {
    Write-Host 'Migration complete. Normal API and voice starts will no longer ask for your passkey.'
    $apiListener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
    if (-not $apiListener) {
      Start-Process -FilePath $projectPython -ArgumentList '-m','core.api.server','server' -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
    }
    $runningVoice = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop |
      Where-Object { $_.CommandLine -match 'core\.voice_listener\.voice_listener_main\s+start' -and $_.CommandLine -match [regex]::Escape($projectRoot) }
    if (-not $runningVoice) {
      Start-Process -FilePath $projectPython -ArgumentList '-m','core.voice_listener.voice_listener_main','start' -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
    }
    Write-Host 'Requested the updated API and verified voice listener. Startup may take a moment; check ZAE health for readiness.'
  }
} elseif ($Mode -eq 'rollback') {
  & $projectPython -m core.assistant_platform.releases $Request
} else {
  & $projectPython -m core.assistant_platform.profiles $Mode --request $Request
}
Read-Host 'Press Enter to close this owner console'
