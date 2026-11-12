# Build a ZAENIA update and stage it for Grey to install from Settings > Updates.
# Nothing installed or served changes here: the desktop exe and the phone site go to updates\pending\<id>\
# and only Install (scripts\install_update.ps1, run by the desktop app) puts them in place.
#
#   .\scripts\stage_update.ps1 -Title "Settings hub, Updates and About" -Notes "First change|Second change" [-Part ui|system|tab:<id>] [-RestartServer]
#
# Bump the numbers in desktop\src\config\versions.json (and add a history entry) before staging.
param(
    [Parameter(Mandatory = $true)][string]$Title,
    [string]$Notes = "",   # one string, changes separated by |
    [string]$Part = "ui",
    [string]$ReleaseNotesFile = "", # JSON array: kind, title, description
    [switch]$RestartServer,
    [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = Join-Path $Root "desktop"
$Versions = Get-Content -Raw -Encoding UTF8 (Join-Path $Desktop "src\config\versions.json") | ConvertFrom-Json
if ($Part -notmatch '^(ui|system|tab:[a-z]+)$') { throw "Part must be ui, system or tab:<id>." }
$Version = if ($Part -eq "system") { $Versions.system.version } elseif ($Part -like "tab:*") { $Versions.tabs.($Part.Substring(4)).version } else { $Versions.ui.version }
if (-not $Version) { throw "No version found for $Part in versions.json." }
# Every future release carries detailed notes, regardless of which part changed.
$DetailedNotes = if ($ReleaseNotesFile) { @(Get-Content -LiteralPath $ReleaseNotesFile -Raw -Encoding UTF8 | ConvertFrom-Json) } else { @($Versions.history | Where-Object { $_.part -eq $Part -and $_.version -eq $Version } | Select-Object -First 1 | ForEach-Object { $_.releaseNotes }) }
if (-not $DetailedNotes.Count -or $DetailedNotes.Count -gt 100) { throw "Provide 1-100 detailed release notes in history or -ReleaseNotesFile before staging." }
foreach ($Entry in $DetailedNotes) {
    if ($Entry.kind -notin @('added','changed','fixed','removed','performance','security','limitations') -or $Entry.title -isnot [string] -or $Entry.description -isnot [string] -or $Entry.title.Trim().Length -lt 3 -or $Entry.description.Trim().Length -lt 20 -or $Entry.title.Length -gt 200 -or $Entry.description.Length -gt 4000) { throw "Each release note needs a valid kind, title (3-200 characters), and explanation (20-4000 characters)." }
}
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Id = ($Part -replace ':', '-') + "-" + $Version + "-" + $Stamp
$PendingRoot = Join-Path $Root "updates\pending"
$Work = Join-Path $PendingRoot ("_staging-" + $Stamp)
New-Item -ItemType Directory -Force $Work | Out-Null

Push-Location $Desktop
try {
    if (-not $SkipBuild) {
        & npx tsc --noEmit -p . ; if ($LASTEXITCODE) { throw "TypeScript check failed." }
        & npx vite build --mode web --base /app/ --outDir (Join-Path $Work "dist-web") --emptyOutDir ; if ($LASTEXITCODE) { throw "Phone site build failed." }
        & npm run tauri build -- --no-bundle ; if ($LASTEXITCODE) { throw "Desktop build failed." }
    } else {
        Copy-Item -Recurse (Join-Path $Desktop "dist-web") (Join-Path $Work "dist-web")
    }
} finally { Pop-Location }

$Exe = Join-Path $Desktop "src-tauri\target\release\desktop.exe"
if (-not (Test-Path -LiteralPath $Exe)) { throw "Desktop build output not found: $Exe" }
Copy-Item -LiteralPath $Exe (Join-Path $Work "ZAENIA.exe")
$Commit = (& git -C $Root rev-parse --short HEAD 2>$null)
$Dirty = [bool](& git -C $Root status --porcelain 2>$null)
$Manifest = [ordered]@{
    id = $Id; title = $Title; notes = @($DetailedNotes | ForEach-Object { "[$($_.kind)] $($_.title) — $($_.description)" }); summary = @($Notes -split '\|' | ForEach-Object { $_.Trim() } | Where-Object { $_ }); part = $Part; version = $Version
    releaseNotes = @($DetailedNotes)
    versions = [ordered]@{ system = $Versions.system.version; ui = $Versions.ui.version }
    restartServer = [bool]$RestartServer
    createdAt = (Get-Date).ToString("o")
    sha256 = (Get-FileHash -LiteralPath (Join-Path $Work "ZAENIA.exe") -Algorithm SHA256).Hash
    builtFrom = [ordered]@{ commit = "$Commit"; uncommittedChanges = $Dirty }
}
$Manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $Work "manifest.json")
# Appears in Settings only once it is complete.
Rename-Item -LiteralPath $Work -NewName $Id
Write-Output "Staged $Id. Open Settings > Updates in ZAENIA to install it."
