# ZAENIA voice training: retrain how ZAE recognises your voice.
# Run at the PC with SteelSeries GG (Sonar) open. Keep ASCII only.
#
#   1. Retrain your voice profile on the approved microphone (passkey, then type REPLACE).
#      Your old profile is kept in data\secure\profile_backups, not deleted.
#   2. Calibrate: you read a few lines, then play someone else's voice
#      (a video or another person) for the "not you" samples.
#   3. Refresh the app-microphone voice check with the new profile.

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "ZAENIA - Voice training"

Write-Host "ZAENIA voice training"
Write-Host "Use a quiet room and your normal speaking voice. Keep SteelSeries GG (Sonar) running."
Write-Host ""

$answer = Read-Host "Step 1 of 3: retrain your voice profile now? (y/n)"
if ($answer -eq "y") {
    & $Python -m core.foundation.auth.speaker_profile replace
    if ($LASTEXITCODE -ne 0) { Write-Host "Retraining stopped. Nothing else was changed."; Read-Host "Press Enter to close"; exit 1 }
} else {
    Write-Host "Keeping your current profile."
}

Write-Host ""
Write-Host "Step 2 of 3: calibration. Have a video of another person talking ready for the 'not you' samples."
& $Python -m core.voice_security.calibrate
if ($LASTEXITCODE -ne 0) { Write-Host "Calibration did not pass. Try again in a quieter room."; Read-Host "Press Enter to close"; exit 1 }

Write-Host ""
Write-Host "Step 3 of 3: refreshing the app-microphone voice check."
& $Python -m core.api.mobile_voice_profile enable
if ($LASTEXITCODE -ne 0) { Write-Host "The app-microphone check was not refreshed."; Read-Host "Press Enter to close"; exit 1 }

Write-Host ""
Write-Host "Done. Restart PC Voice and the server so they use your new voice profile."
Read-Host "Press Enter to close"
