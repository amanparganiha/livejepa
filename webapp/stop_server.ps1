# Stops the LiveJEPA server cleanly: kills the launcher loop(s) first (so the
# crash-restart logic cannot resurrect the server), then whatever owns the port.
#
# Usage: powershell -ExecutionPolicy Bypass -File webapp\stop_server.ps1

param([int]$Port = 8000)

# 1. launcher loops (powershell running start_server.ps1)
$launchers = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
    Where-Object { $_.CommandLine -match 'start_server\.ps1' -and $_.ProcessId -ne $PID }
foreach ($p in $launchers) {
    Write-Host "Stopping launcher PID $($p.ProcessId)"
    try { Stop-Process -Id $p.ProcessId -Force -Confirm:$false -ErrorAction Stop } catch {}
}

# 2. the server process on the port
$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    Write-Host "Stopping server PID $($c.OwningProcess) on port $Port"
    try { Stop-Process -Id $c.OwningProcess -Force -Confirm:$false -ErrorAction Stop } catch {}
}

Start-Sleep -Seconds 2
$left = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($left) { Write-Host "WARNING: port $Port still in use." } else { Write-Host "Server stopped - port $Port free." }
