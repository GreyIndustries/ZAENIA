# ZAE maintenance: check, test, update, build, restart and undo, without Claude or Codex.
#
#   .\scripts\zae.ps1                 menu
#   .\scripts\zae.ps1 status          what's running, which version, anything wrong
#   .\scripts\zae.ps1 test            every test plus the security suites
#   .\scripts\zae.ps1 update          bring in new work from GitHub, test it, build, install, restart
#   .\scripts\zae.ps1 update -Branch feature/chatgpt-development
#   .\scripts\zae.ps1 build           rebuild the desktop and phone apps and install the desktop app
#   .\scripts\zae.ps1 restart         restart the server (token mode)
#   .\scripts\zae.ps1 rollback        go back to how ZAE was before the last update
#   .\scripts\zae.ps1 shortcut        add "ZAE Maintenance" to the Start menu
#
# Every update first saves a restore point (a git tag named zae-rollback-<date>-<time>),
# and undoes itself automatically if any test fails. Your data/ folder (memory,
# profile, settings, secrets) is never touched by update or rollback: git ignores it.
# Keep this file plain ASCII: Windows PowerShell 5 misreads other characters.

param(
    [Parameter(Position = 0)][string]$Command = "menu",
    [string]$Branch = "feature/claude-development",
    [string]$To = "",
    [switch]$Yes
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Desktop = Join-Path $Root "desktop"
$Port = 8766

function Say([string]$Text, [string]$Color = "Gray") { Write-Host $Text -ForegroundColor $Color }
function Good([string]$Text) { Say ("  OK    " + $Text) "Green" }
function Warn([string]$Text) { Say ("  NOTE  " + $Text) "Yellow" }
function Bad([string]$Text) { Say ("  FAIL  " + $Text) "Red" }
function Title([string]$Text) { Say ""; Say ("== " + $Text + " ==") "Cyan" }

function Confirm-Step([string]$Question) {
    if ($Yes) { return $true }
    $answer = Read-Host ($Question + " (y/n)")
    return $answer -match '^(y|yes)$'
}

function Invoke-Git { & git.exe -C $Root @args }

# ---------------------------------------------------------------- status
function Show-Status {
    Title "ZAE status"
    $branch = (Invoke-Git rev-parse --abbrev-ref HEAD).Trim()
    $commit = (Invoke-Git log -1 --format="%h  %s  (%cr)").Trim()
    Say ("  Code:    branch " + $branch + ", " + $commit)
    $changed = @(Invoke-Git status --porcelain)
    if ($changed.Count) { Warn ("" + $changed.Count + " file(s) changed locally and not committed. Updates wait until this is clean.") }
    else { Good "No uncommitted changes." }

    if (Test-Path $Python) { Good ("Python: " + ((& $Python -V) 2>&1)) } else { Bad "Python environment (.venv) is missing." }

    try {
        $health = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $Port + "/health") -TimeoutSec 4
        Good ("Server: running, mode " + $health.status + ", version " + $health.version)
    } catch { Bad "Server: not answering. Fix: .\scripts\zae.ps1 restart" }

    $voiceFile = Join-Path $Root "data\ui\voice_service.json"
    try {
        $voice = Get-Content $voiceFile -Raw | ConvertFrom-Json
        $age = ((Get-Date).ToUniversalTime() - ([DateTime]::Parse($voice.updatedAt)).ToUniversalTime()).TotalSeconds
        if ($age -lt 15 -and $voice.state -ne "off") { Good ("PC voice: " + $voice.state) }
        else { Warn "PC voice: off. Start it with scripts\start_zaenia_voice.ps1 (passkey)." }
    } catch { Warn "PC voice: off." }

    $checks = Join-Path $Root "data\security_checks"
    $latest = Get-ChildItem $checks -Filter *.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    if ($latest) { Say ("  Last security check: " + $latest.LastWriteTime.ToString("g") + " (details on the Security tab)") }

    $tags = @(Invoke-Git tag --list "zae-rollback-*" --sort=-creatordate | Select-Object -First 1)
    if ($tags.Count -and $tags[0]) { Say ("  Latest restore point: " + $tags[0]) }
}

# ---------------------------------------------------------------- tests
function Invoke-Tests {
    Title "Python tests"
    $modules = Get-ChildItem (Join-Path $Root "core"), (Join-Path $Root "scripts") -Recurse -Filter "*_test.py" |
        Where-Object { $_.FullName -notmatch '\\_backup' -and $_.FullName -notmatch '\\__pycache__\\' } |
        ForEach-Object { $_.FullName.Substring($Root.Length + 1).Replace("\", ".").Replace(".py", "") }
    Push-Location $Root
    $out = & $Python -m unittest @modules 2>&1
    $ok = $LASTEXITCODE -eq 0
    Pop-Location
    $summary = $out | Where-Object { "$_" -match '^(Ran \d+|OK|FAILED)' }
    if ($ok) { Good ($summary -join "  ") } else {
        Bad ($summary -join "  ")
        $out | Where-Object { "$_" -match '^(ERROR|FAIL):' } | Select-Object -First 15 | ForEach-Object { Say ("        " + $_) "Red" }
        return $false
    }

    Title "Security suites"
    foreach ($suite in @("core.foundation.self_test", "core.foundation.closure_check", "core.foundation.integration_check")) {
        Push-Location $Root
        $null = & $Python -m $suite 2>&1
        $passed = $LASTEXITCODE -eq 0
        Pop-Location
        if ($passed) { Good $suite } else { Bad ($suite + "  (see the output: " + $Python + " -m " + $suite + ")"); return $false }
    }

    Title "App checks"
    Push-Location $Desktop
    foreach ($check in Get-ChildItem "scripts" -Filter "*.test.cjs") {
        $null = & node $check.FullName 2>&1
        if ($LASTEXITCODE -ne 0) { Pop-Location; Bad $check.Name; return $false }
    }
    Good "UI checks"
    $null = & npx tsc --noEmit -p . 2>&1
    $typesOk = $LASTEXITCODE -eq 0
    Pop-Location
    if ($typesOk) { Good "TypeScript" } else { Bad "TypeScript (run: cd desktop; npx tsc --noEmit -p .)"; return $false }
    return $true
}

# ---------------------------------------------------------------- build and install
function Invoke-Build {
    Title "Building the apps (about 2-3 minutes)"
    Push-Location $Desktop
    $null = & npm run build 2>&1;   if ($LASTEXITCODE -ne 0) { Pop-Location; Bad "Desktop web build"; return $false }; Good "Desktop interface"
    $null = & npm run build:web 2>&1; if ($LASTEXITCODE -ne 0) { Pop-Location; Bad "Phone app build"; return $false }; Good "Phone app"
    $null = & npm run tauri build -- --no-bundle 2>&1
    $built = $LASTEXITCODE -eq 0
    Pop-Location
    if (-not $built) { Bad "Desktop app build (run: cd desktop; npm run tauri build -- --no-bundle)"; return $false }
    Good "Desktop app"
    & (Join-Path $PSScriptRoot "update_desktop_app.ps1")
    if (-not $?) { Warn "The new desktop app is built but not installed: close ZAE and run .\scripts\zae.ps1 build again."; return $true }
    Good "Installed in the Start menu and reopened"
    return $true
}

function Invoke-Restart {
    Title "Restarting the server"
    & (Join-Path $PSScriptRoot "restart_zaenia_server.ps1")
}

# ---------------------------------------------------------------- update
function Invoke-Update {
    Title ("Update from GitHub: " + $Branch)
    if (@(Invoke-Git status --porcelain).Count) { Bad "There are uncommitted local changes. Commit or undo them first (see docs/SELF_SERVICE.md)."; return }
    if ((Invoke-Git rev-parse --abbrev-ref HEAD).Trim() -ne "main") { Bad "The live install should be on main. Run: git -C $Root switch main"; return }
    Invoke-Git fetch origin --prune 2>&1 | Out-Null
    $incoming = @(Invoke-Git log --oneline ("HEAD..origin/" + $Branch))
    if (-not $incoming.Count) { Good "Already up to date. Nothing new on that branch."; return }
    Say ("  New on " + $Branch + ":")
    $incoming | Select-Object -First 20 | ForEach-Object { Say ("    " + $_) }
    if (-not (Confirm-Step "Bring these in, test them and install?")) { Warn "Cancelled. Nothing changed."; return }

    $tag = "zae-rollback-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Invoke-Git tag $tag | Out-Null
    Good ("Restore point saved: " + $tag)

    Invoke-Git merge --no-edit ("origin/" + $Branch) 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Git merge --abort 2>&1 | Out-Null
        Bad "The new work conflicts with this install, so nothing was changed. Ask Claude or Codex to rebase their branch on main."
        return
    }
    Good "Merged"

    $changedFiles = @(Invoke-Git diff --name-only $tag HEAD)
    if ($changedFiles | Where-Object { $_ -like "requirements*.txt" }) {
        Say "  Python packages changed: installing..."
        & $Python -m pip install -q -r (Join-Path $Root "requirements.txt") 2>&1 | Out-Null
    }
    if ($changedFiles | Where-Object { $_ -eq "desktop/package-lock.json" }) {
        Say "  App packages changed: installing..."
        Push-Location $Desktop; & npm ci 2>&1 | Out-Null; Pop-Location
    }

    if (-not (Invoke-Tests)) {
        Bad "A test failed, so the update is being undone."
        Invoke-Git reset --hard $tag 2>&1 | Out-Null
        Good ("Back to " + $tag + ". ZAE is exactly as before. Send the FAIL lines above to Claude or Codex.")
        return
    }
    if (Invoke-Build) { Invoke-Restart }
    Title "Update finished"
    Say ("  If anything seems wrong, undo it with: .\scripts\zae.ps1 rollback")
}

# ---------------------------------------------------------------- rollback
function Invoke-Rollback {
    Title "Undo an update"
    $tags = @(Invoke-Git tag --list "zae-rollback-*" --sort=-creatordate | Select-Object -First 5)
    if (-not $tags.Count -or -not $tags[0]) { Warn "There's no restore point yet (one is made by every update)."; return }
    $target = if ($To) { $To } else { $tags[0] }
    if ($tags -notcontains $target -and -not (Invoke-Git tag --list $target)) { Bad ("No restore point named " + $target); return }
    Say "  Restore points (newest first):"
    $tags | ForEach-Object { Say ("    " + $_) }
    if (@(Invoke-Git status --porcelain).Count) { Bad "There are uncommitted local changes; commit or undo them first."; return }
    if (-not (Confirm-Step ("Go back to " + $target + "? Your data, memory and settings are not affected"))) { Warn "Cancelled."; return }
    Invoke-Git reset --hard $target 2>&1 | Out-Null
    Good ("Code is back at " + $target)
    if (Invoke-Build) { Invoke-Restart }
}

# ---------------------------------------------------------------- shortcut
function Install-Shortcut {
    $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path $startMenu "ZAE Maintenance.lnk"))
    $link.TargetPath = "powershell.exe"
    $link.Arguments = '-NoExit -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot "zae.ps1") + '"'
    $link.WorkingDirectory = $Root
    $link.Description = "Check, test, update, build, restart or undo ZAE"
    $icon = Join-Path $env:LOCALAPPDATA "Programs\ZAENIA\ZAENIA.ico"
    if (Test-Path $icon) { $link.IconLocation = $icon }
    $link.Save()
    Good "Added 'ZAE Maintenance' to the Start menu."
}

# ---------------------------------------------------------------- menu
function Show-Menu {
    while ($true) {
        Title "ZAE maintenance"
        Say "  1  Status       what's running and which version"
        Say "  2  Test         run every test and the security suites"
        Say "  3  Update       bring in new work from GitHub (tested, undone automatically if it fails)"
        Say "  4  Build        rebuild and install the apps"
        Say "  5  Restart      restart her server"
        Say "  6  Rollback     undo the last update"
        Say "  Q  Quit"
        switch ((Read-Host "Choose").Trim().ToUpper()) {
            "1" { Show-Status }
            "2" { if (Invoke-Tests) { Title "All tests passed" } }
            "3" {
                $choice = Read-Host "Branch to update from [Enter = feature/claude-development, C = feature/chatgpt-development]"
                if ($choice -match '^[cC]$') { $script:Branch = "feature/chatgpt-development" }
                elseif ($choice) { $script:Branch = $choice }
                Invoke-Update
            }
            "4" { $null = Invoke-Build }
            "5" { Invoke-Restart }
            "6" { Invoke-Rollback }
            "Q" { return }
            default { Warn "Type a number from the list." }
        }
    }
}

switch ($Command.ToLower()) {
    "menu" { Show-Menu }
    "status" { Show-Status }
    "test" { if (Invoke-Tests) { Title "All tests passed" } else { exit 1 } }
    "update" { Invoke-Update }
    "build" { if (-not (Invoke-Build)) { exit 1 } }
    "restart" { Invoke-Restart }
    "rollback" { Invoke-Rollback }
    "shortcut" { Install-Shortcut }
    default { Get-Content $PSCommandPath -TotalCount 14 | ForEach-Object { $_.TrimStart("#") } }
}
