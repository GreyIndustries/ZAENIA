# Install a staged update (Settings > Updates > Install). Started by the desktop app, hidden.
# Checks the staged exe against its manifest, backs up the installed app and phone site, closes ZAENIA,
# puts the new versions in place, optionally restarts the server, records the install and reopens ZAENIA.
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Za-z][0-9A-Za-z.\-]{0,63}$')][string]$Id,
    [string]$Root = "",
    [switch]$CheckOnly,
    [switch]$RestartServer
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "update_helpers.ps1")
$Root = Assert-ZaeDeploymentRoot $(if ($Root) { $Root } else { Split-Path -Parent $PSScriptRoot })
$Stage = Join-Path $Root ("updates\pending\" + $Id)
$DataDir = Join-Path $Root "data\updates"
$LogFile = Join-Path $DataDir "installed.json"
$ResultFile = Join-Path $DataDir "last-install.json"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ZAENIA"
$InstalledExe = Join-Path $InstallDir "ZAENIA.exe"
$SiteDir = Join-Path $Root "desktop\dist-web"
if (-not $CheckOnly) { New-Item -ItemType Directory -Force $DataDir | Out-Null }

function Write-Result($Status, $Message) {
    [ordered]@{ id = $Id; status = $Status; message = $Message; at = (Get-Date).ToString("o") } |
        ConvertTo-Json | Set-Content -Encoding UTF8 $ResultFile
}

$Closed = $false
$Replaced = $false
$Backup = $null
try {
    if (-not $CheckOnly) { Write-Result "running" "Installing..." }
    $Manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $Stage "manifest.json") | ConvertFrom-Json
    $NewExe = Join-Path $Stage "ZAENIA.exe"
    if (-not (Test-Path -LiteralPath (Join-Path $Stage "dist-web\index.html"))) { throw "The staged phone site is missing." }
    if ((Get-ZaeFileHash -LiteralPath $NewExe -Algorithm SHA256).Hash -ne $Manifest.sha256) { throw "The staged app does not match its manifest. Not installed." }

    if ($Manifest.deploymentRoot -and [IO.Path]::GetFullPath($Manifest.deploymentRoot) -ne $Root) { throw "This package targets a different deployment root." }
    Assert-ZaeChildPath $Root $Stage
    Assert-ZaeChildPath $Root $SiteDir
    if ($CheckOnly) { Write-Output "Package and deployment root validated; no processes stopped or files installed."; return }

    $Backup = Join-Path $Root ("backups\update-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Force $Backup | Out-Null
    if (Test-Path -LiteralPath $InstalledExe) { Copy-Item -LiteralPath $InstalledExe (Join-Path $Backup "ZAENIA.exe") }
    if (Test-Path -LiteralPath $SiteDir) { Copy-Item -Recurse -LiteralPath $SiteDir (Join-Path $Backup "dist-web") }

    $Targets = @(Get-ZaeInstallProcesses @(Get-Process -ErrorAction SilentlyContinue) $InstalledExe $Root)
    $Blockers = @()
    foreach ($App in $Targets) {
        $Closed = $true
        try {
            if ($App.MainWindowHandle -ne [IntPtr]::Zero) { [void]$App.CloseMainWindow() }
            if (-not $App.WaitForExit(5000)) { Stop-Process -Id $App.Id -Force -ErrorAction Stop; if (-not $App.WaitForExit(5000)) { throw 'Still running' } }
        } catch { $Blockers += ($App.Name + ' (PID ' + $App.Id + ')') }
    }
    if ($Blockers.Count) { throw ('Could not close ZAE processes: ' + ($Blockers -join ', ')) }
    $Replaced = $true
    Copy-ZaeFileWithRetry $NewExe $InstalledExe
    $Replaced = $true
    if ((Get-ZaeFileHash -LiteralPath $InstalledExe -Algorithm SHA256).Hash -ne $Manifest.sha256) { throw "The installed app does not match the update." }

    & robocopy (Join-Path $Stage "dist-web") $SiteDir /MIR /NJH /NJS /NP /NFL /NDL | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "The phone site could not be updated (robocopy $LASTEXITCODE)." }

    $Restarted = $false
    if ($RestartServer) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\restart_zaenia_server.ps1") | Out-Null
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
    Assert-ZaeChildPath $Root $Done
    Assert-ZaeChildPath $Root (Join-Path $Done $Id)
    Move-Item -LiteralPath $Stage (Join-Path $Done $Id) -Force
    $Note = if ($RestartServer -and -not $Restarted) { " The server did not come back on its own; restart it from Settings." } elseif ($Restarted) { " Server restarted (token mode)." } else { "" }
    Write-Result "ok" ("Installed " + $Manifest.title + " (" + $Manifest.version + ")." + $Note)
}
catch {
    if ($CheckOnly) { throw }
    Write-Result "failed" $_.Exception.Message
    if ($Backup -and (Test-Path -LiteralPath (Join-Path $Backup "ZAENIA.exe")) -and $Replaced) {
        Copy-Item -LiteralPath (Join-Path $Backup "ZAENIA.exe") $InstalledExe -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath (Join-Path $Backup "dist-web")) {
            Assert-ZaeChildPath $Root $Backup
            Assert-ZaeChildPath $Root $SiteDir
            & robocopy (Join-Path $Backup "dist-web") $SiteDir /MIR /NJH /NJS /NP /NFL /NDL | Out-Null
        }
    }
}
finally {
    if (-not $CheckOnly -and (Test-Path -LiteralPath $InstalledExe) -and -not (Get-Process -Name ZAENIA -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $InstalledExe -WorkingDirectory $InstallDir -WindowStyle Hidden
    }
}
