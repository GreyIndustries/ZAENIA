$ErrorActionPreference = "Stop"

# Opens the ZÆNIA voice window each time you sign in to Windows, so ZÆNIA is
# always listening once you enter your passkey in that window.

$TaskName = "ZAENIA Voice"
$ProjectRoot = "C:\Projects\ZAENIA"
$VoiceScript = Join-Path $ProjectRoot "scripts\start_zaenia_voice.ps1"

if (-not (Test-Path $VoiceScript)) {
    throw "Voice startup script not found: $VoiceScript"
}

$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

# Visible window on purpose: the passkey is typed there, never in the UI.
$ActionArguments = @(
    "-NoProfile"
    "-ExecutionPolicy Bypass"
    "-File `"$VoiceScript`""
) -join " "

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $ActionArguments `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -AtLogOn `
    -User $CurrentUser

$Trigger.Delay = "PT30S"

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$Principal = New-ScheduledTaskPrincipal `
    -UserId $CurrentUser `
    -LogonType Interactive `
    -RunLevel Limited

$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal

Register-ScheduledTask `
    -TaskName $TaskName `
    -InputObject $Task `
    -Force | Out-Null

Write-Host ""
Write-Host "ZÆNIA voice startup installed."
Write-Host "Task: $TaskName"
Write-Host "After each Windows sign-in, the ZAENIA Voice window opens and asks for your passkey."
