# Install the latest local release, preserving the previous installed binary.
$ErrorActionPreference = "Stop"
$desktopUpdateRoot = Split-Path -Parent $PSScriptRoot
$desktopBuiltExe = Join-Path $desktopUpdateRoot "desktop\src-tauri\target\release\desktop.exe"
$desktopInstallRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) "Programs\ZAENIA"
$desktopInstalledExe = Join-Path $desktopInstallRoot "ZAENIA.exe"
if (-not (Test-Path -LiteralPath $desktopBuiltExe -PathType Leaf)) { throw "Build the desktop release before updating." }

$desktopUpdateBackup = Join-Path $desktopUpdateRoot ("backups\desktop-installed-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (Test-Path -LiteralPath $desktopInstalledExe) {
    New-Item -ItemType Directory -Path $desktopUpdateBackup -Force | Out-Null
    Copy-Item -LiteralPath $desktopInstalledExe -Destination (Join-Path $desktopUpdateBackup "ZAENIA.exe")
}
$desktopOldProcesses = @(Get-Process -Name ZAENIA,desktop -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -eq $desktopInstalledExe -or $_.Path -eq $desktopBuiltExe
})
foreach ($desktopOldProcess in $desktopOldProcesses) {
    if (-not $desktopOldProcess.CloseMainWindow()) { throw "Close the running Zae window, then retry the update." }
    if (-not $desktopOldProcess.WaitForExit(10000)) { throw "Zae is still closing. Finish closing it, then retry the update." }
}
& (Join-Path $PSScriptRoot "install_start_menu.ps1")
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "The desktop install did not finish." }
if ((Get-FileHash -LiteralPath $desktopBuiltExe -Algorithm SHA256).Hash -ne
    (Get-FileHash -LiteralPath $desktopInstalledExe -Algorithm SHA256).Hash) {
    throw "The installed desktop app does not match the new release. Retry the update."
}
Start-Process -FilePath $desktopInstalledExe -WorkingDirectory $desktopInstallRoot -WindowStyle Normal
Write-Output "The installed desktop app has been updated and reopened."
