# Pure helpers shared with the isolated installer checks.
function Get-ZaeInstallProcesses($Processes, [string]$InstalledExe, [string]$ProjectRoot) {
    $Prefix = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
    @($Processes | Where-Object {
        try {
            $Path = [IO.Path]::GetFullPath($_.Path)
            $Path.Equals([IO.Path]::GetFullPath($InstalledExe), [StringComparison]::OrdinalIgnoreCase) -or
                ($_.Name -in @('ZAENIA','desktop') -and $Path.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase))
        } catch { $false }
    })
}
function Assert-ZaeDeploymentRoot([string]$Root) {
    if (-not [IO.Path]::IsPathRooted($Root)) { throw 'Deployment root must be absolute.' }
    $Full = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    if (($Full -split '[\\/]') -contains '.tmp') { throw 'Temporary build folders are not deployment roots.' }
    foreach ($Name in @('core\api\update_routes.py','scripts\install_update.ps1','desktop')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Full $Name))) { throw "Deployment root is missing $Name" }
    }
    return $Full
}
function Assert-ZaeChildPath([string]$Root, [string]$Path) {
    $Prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not [IO.Path]::GetFullPath($Path).StartsWith($Prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes the intended project.' }
}
function Copy-ZaeFileWithRetry([string]$Source,[string]$Destination) {
    for ($Try=0; $Try -lt 6; $Try++) {
        try { Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop; return }
        catch { if ($Try -eq 5) { throw }; Start-Sleep -Milliseconds (250 * ($Try + 1)) }
    }
}

function Get-ZaeFileHash([string]$LiteralPath, [ValidateSet('SHA256')][string]$Algorithm='SHA256') {
    $Hasher=[Security.Cryptography.SHA256]::Create()
    $Stream=[IO.File]::OpenRead($LiteralPath)
    try { [pscustomobject]@{Hash=([BitConverter]::ToString($Hasher.ComputeHash($Stream))).Replace('-','')} }
    finally { $Stream.Dispose(); $Hasher.Dispose() }
}
