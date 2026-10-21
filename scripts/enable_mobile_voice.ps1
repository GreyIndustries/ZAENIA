$ErrorActionPreference = "Stop"
$mobileVoiceRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $mobileVoiceRoot
& (Join-Path $mobileVoiceRoot ".venv\Scripts\python.exe") -m core.api.mobile_voice_profile enable
if ($LASTEXITCODE -ne 0) { Write-Host "Mobile voice setup was not completed. Your existing token sign-in still works." }
Read-Host "Press Enter to close"
