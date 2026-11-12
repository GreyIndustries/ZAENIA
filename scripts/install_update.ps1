# Install a staged update (Settings > Updates > Install). Started by the desktop app, hidden.
# Checks the staged exe against its manifest, backs up the installed app and phone site, closes ZAENIA,
# puts the new versions in place, optionally restarts the server, records the install and reopens ZAENIA.
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Za-z][0-9A-Za-z.\-]{0,63}$')][string]$Id,
    [switch]$RestartServer
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Stage = Join-Path $Root ("updates\pending\" + $Id)
$DataDir = Join-Path $Root "data\updates"
$LogFile = Join-Path $DataDir "installed.json"
$ResultFile = Join-Path $DataDir "last-install.json"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ZAENIA"
$InstalledExe = Join-Path $InstallDir "ZAENIA.exe"
$SiteDir = Join-Path $Root "desktop\dist-web"
New-Item -ItemType Directory -Force $DataDir | Out-Null

function Write-Result($Status, $Message) {
    [ordered]@{ id = $Id; status = $Status; message = $Message; at = (Get-Date).ToString("o") } |
        ConvertTo-Json | Set-Content -Encoding UTF8 $ResultFile
}

$Closed = $false
$Replaced = $false
$Backup = $null
try {
    Write-Result "running" "Installing..."
    $Manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $Stage "manifest.json") | ConvertFrom-Json
    $NewExe = Join-Path $Stage "ZAENIA.exe"
    if (-not (Test-Path -LiteralPath (Join-Path $Stage "dist-web\index.html"))) { throw "The staged phone site is missing." }
    if ((Get-FileHash -LiteralPath $NewExe -Algorithm SHA256).Hash -ne $Manifest.sha256) { throw "The staged app does not match its manifest. Not installed." }

    $Backup = Join-Path $Root ("backups\update-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Force $Backup | Out-Null
    if (Test-Path -LiteralPath $InstalledExe) { Copy-Item -LiteralPath $InstalledExe (Join-Path $Backup "ZAENIA.exe") }
    if (Test-Path -LiteralPath $SiteDir) { Copy-Item -Recurse -LiteralPath $SiteDir (Join-Path $Backup "dist-web") }

    foreach ($App in @(Get-Process -Name ZAENIA -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $InstalledExe })) {
        $Closed = $true
        if ($App.MainWindowHandle -eq [IntPtr]::Zero) { Stop-Process -Id $App.Id -Force -ErrorAction SilentlyContinue } else { [void]$App.CloseMainWindow() }
        if (-not $App.WaitForExit(15000)) { throw "ZAENIA did not close. Close it and press Install again." }
    }
    Copy-Item -LiteralPath $NewExe $InstalledExe -Force
    $Replaced = $true
    if ((Get-FileHash -LiteralPath $InstalledExe -Algorithm SHA256).Hash -ne $Manifest.sha256) { throw "The installed app does not match the update." }

    & robocopy (Join-Path $Stage "dist-web") $SiteDir /MIR /NJH /NJS /NP /NFL /NDL | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "The phone site could not be updated (robocopy $LASTEXITCODE)." }

    $Restarted = $false
    if ($RestartServer) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "restart_zaenia_server.ps1") | Out-Null
        $Restarted = ($LASTEXITCODE -eq 0)
    }

    $History = @()
    if (Test-Path -LiteralPath $LogFile) { $History = @(Get-Content -Raw -Encoding UTF8 $LogFile | ConvertFrom-Json) }
    $History += [pscustomobject][ordered]@{
        releaseNotes = @($Manifest.releaseNotes)
        id = $Id; title = $Manifest.title; notes = $Manifest.notes; part = $Manifest.part; version = $Manifest.version
        versions = $Manifest.versions; installedAt = (Get-Date).ToString("o"); restartedServer = $Restarted; backup = $Backup
    }
    ConvertTo-Json -InputObject @($History) -Depth 6 | Set-Content -Encoding UTF8 $LogFile

    $Done = Join-Path $Root "updates\installed"
    New-Item -ItemType Directory -Force $Done | Out-Null
    Move-Item -LiteralPath $Stage (Join-Path $Done $Id) -Force
    $Note = if ($RestartServer -and -not $Restarted) { " The server did not come back on its own; restart it from Settings." } elseif ($Restarted) { " Server restarted (token mode)." } else { "" }
    Write-Result "ok" ("Installed " + $Manifest.title + " (" + $Manifest.version + ")." + $Note)
}
catch {
    Write-Result "failed" $_.Exception.Message
    if ($Backup -and (Test-Path -LiteralPath (Join-Path $Backup "ZAENIA.exe")) -and $Replaced) {
        Copy-Item -LiteralPath (Join-Path $Backup "ZAENIA.exe") $InstalledExe -Force -ErrorAction SilentlyContinue
    }
}
finally {
    if ((Test-Path -LiteralPath $InstalledExe) -and -not (Get-Process -Name ZAENIA -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $InstalledExe -WorkingDirectory $InstallDir
    }
}
