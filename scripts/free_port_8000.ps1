# Free TCP port 8000 (default FastAPI). Run as Administrator if access denied.
# Fallback: parses netstat when Get-NetTCPConnection misses PIDs.

$ErrorActionPreference = "Continue"
$port = 8000

function Get-PidsFromNetstat {
    $pids = New-Object 'System.Collections.Generic.HashSet[int]'
    $lines = netstat -ano 2>$null
    foreach ($line in $lines) {
        if ($line -notmatch "LISTENING") { continue }
        if ($line -notmatch ":$port\s") { continue }
        if ($line -match "LISTENING\s+(\d+)\s*$") {
            [void]$pids.Add([int]$Matches[1])
        }
    }
    return @($pids)
}

$pids = @()
$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
}
if (-not $pids -or $pids.Count -eq 0) {
    $pids = Get-PidsFromNetstat
}

if (-not $pids -or $pids.Count -eq 0) {
    Write-Host "Port $port is free (no LISTEN)."
    exit 0
}

foreach ($procId in $pids) {
    Write-Host "taskkill /F /PID $procId"
    & taskkill.exe /F /PID $procId 2>&1 | Out-Host
}

Start-Sleep -Milliseconds 800
$stillListen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
$stillPids = Get-PidsFromNetstat
if ($stillListen -or ($stillPids.Count -gt 0)) {
    Write-Warning "Port $port still in use. Close the terminal running uvicorn, or run this script as Administrator."
    exit 1
}
Write-Host "Port $port is now free."
exit 0
