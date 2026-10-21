# Put ZAENIA in the Windows Start menu.
# Copies the latest built app to %LOCALAPPDATA%\Programs\ZAENIA and adds a
# Start menu shortcut. Run again after rebuilding to update the installed copy.

$ProjectRoot = "C:\Projects\ZAENIA"
$Built = Join-Path $ProjectRoot "desktop\src-tauri\target\release\desktop.exe"
$Icon = Join-Path $ProjectRoot "desktop\src-tauri\icons\icon.ico"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ZAENIA"
$Exe = Join-Path $InstallDir "ZAENIA.exe"
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$Shortcut = Join-Path $StartMenu "ZAENIA.lnk"

if (-not (Test-Path $Built)) {
    Write-Host "Build the app first: in desktop, run npm run tauri build -- --no-bundle"
    exit 1
}

New-Item -ItemType Directory -Force $InstallDir | Out-Null
$running = Get-Process -Name "ZAENIA" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Close ZAENIA first, then run this again so the app can be updated."
    exit 1
}
Copy-Item $Built $Exe -Force
if (Test-Path $Icon) { Copy-Item $Icon (Join-Path $InstallDir "ZAENIA.ico") -Force }

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($Shortcut)
$link.TargetPath = $Exe
$link.WorkingDirectory = $InstallDir
$link.Description = "ZAENIA - Zack's Adaptive, Neural, Intelligent Agent"
if (Test-Path (Join-Path $InstallDir "ZAENIA.ico")) { $link.IconLocation = (Join-Path $InstallDir "ZAENIA.ico") }
$link.Save()

Write-Host "ZAENIA is in the Start menu. Open Start and type ZAENIA (right-click it to pin to Start or the taskbar)."
