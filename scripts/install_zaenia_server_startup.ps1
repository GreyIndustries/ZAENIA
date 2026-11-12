$ErrorActionPreference = "Stop"

$TaskName = "ZAENIA API Server"

$ProjectRoot = "C:\Projects\ZAENIA"

$ServerScript = Join-Path `
    $ProjectRoot `
    "scripts\start_zaenia_server.ps1"

if (-not (Test-Path $ServerScript)) {
    throw "Server startup script not found: $ServerScript"
}

$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$ActionArguments = @(
    "-NoProfile"
    "-ExecutionPolicy Bypass"
    "-WindowStyle Hidden"
    "-File `"$ServerScript`""
) -join " "

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $ActionArguments `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -AtLogOn `
    -User $CurrentUser

$Trigger.Delay = "PT15S"

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

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
Write-Host "ZÆNIA API Windows startup installed."
Write-Host "Task: $TaskName"
Write-Host "User: $CurrentUser"
Write-Host "Start delay: 15 seconds after Windows logon"