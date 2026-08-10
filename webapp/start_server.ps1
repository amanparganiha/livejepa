# LiveJEPA web server - production-ish launcher (Windows).
# Binds 0.0.0.0 so the app is reachable from the LAN (and via a tunnel).
# Logs to webapp\server.log and restarts automatically if the process crashes.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File webapp\start_server.ps1
#   powershell -File webapp\start_server.ps1 -BindHost 127.0.0.1 -Port 8000
#
# Optional env vars (set before launching):
#   $env:LIVEJEPA_TOKEN = "some-secret"     # require token on upload + websockets
#   $env:LIVEJEPA_MAX_UPLOAD_MB = "500"     # upload size cap
#   $env:LIVEJEPA_CKPT = "path\to\ckpt.pt"  # override predictor checkpoint

param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [int]$MaxRestarts = 10
)

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$logFile = Join-Path $PSScriptRoot "server.log"

# Refuse to start if something already listens on the port (a second instance
# would fight over the log file and lose the bind anyway). Use stop_server.ps1 first.
$inUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($inUse) {
    Write-Host "Port $Port is already in use (PID $($inUse[0].OwningProcess))."
    Write-Host "Run  webapp\stop_server.ps1  first, or pick another -Port."
    exit 1
}

Write-Host "LiveJEPA server -> http://$($BindHost):$Port  (log: $logFile)"
if ($env:LIVEJEPA_TOKEN) { Write-Host "Access token: ENABLED" } else { Write-Host "Access token: disabled (set `$env:LIVEJEPA_TOKEN to enable)" }

$restarts = 0
while ($true) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$stamp] === starting uvicorn (restart #$restarts) ==="
    & python -m uvicorn webapp.backend:app --host $BindHost --port $Port --log-level info 2>&1 |
        Tee-Object -FilePath $logFile -Append
    $code = $LASTEXITCODE
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$stamp] === uvicorn exited with code $code ==="
    if ($code -eq 0) { break }             # clean shutdown (Ctrl+C) -> stop
    $restarts++
    if ($restarts -ge $MaxRestarts) {
        Write-Host "Too many crashes ($restarts) - giving up. Check $logFile"
        break
    }
    Write-Host "Server crashed (exit $code) - restarting in 5 s... ($restarts/$MaxRestarts)"
    Start-Sleep -Seconds 5
}
