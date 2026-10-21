$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Projects\ZAENIA"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Set-Location $ProjectRoot

# Prevent duplicate API processes.
$existingListener = Get-NetTCPConnection `
    -LocalPort 8766 `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($existingListener) {
    exit 0
}

# Token mode: starts without the passkey so the CarPlay brief, chat and the
# status feed work after a reboot while you are away. Every request still
# needs the API token. Owner features need the full server: run "server"
# without --unattended and enter the passkey.
& $Python -m core.api.server server --unattended

exit $LASTEXITCODE