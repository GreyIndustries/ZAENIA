# Starts ZAE's local GraphHopper routing engine (127.0.0.1:8989) if it is not already running.
# Safe to run repeatedly. The first run after a graph-cache rebuild can take several minutes
# before the port opens. Output is appended to data\maps\routing\routing.log.

$ErrorActionPreference = 'Stop'

$jarName = 'graphhopper-web-11.1.jar'
$routingDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'data\maps\routing'

function Test-RoutingPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connect = $client.ConnectAsync('127.0.0.1', 8989)
        return ($connect.Wait(1000) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

if (Test-RoutingPort) {
    Write-Output 'Routing engine already listening on 127.0.0.1:8989.'
    exit 0
}

# Also catch a process that has launched but has not opened the port yet.
$existing = Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
    Where-Object { $_.CommandLine -like "*$jarName*" }
if ($existing) {
    Write-Output "Routing engine is already starting (PID $($existing.ProcessId -join ', '))."
    exit 0
}

foreach ($required in @($jarName, 'config.yml', 'washington-latest.osm.pbf')) {
    if (-not (Test-Path (Join-Path $routingDir $required))) {
        throw "Missing $required in $routingDir"
    }
}

$command = "java -Xmx3g -jar $jarName server config.yml >> routing.log 2>&1"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $command -WorkingDirectory $routingDir -WindowStyle Hidden
Write-Output 'Routing engine starting; see data\maps\routing\routing.log.'
