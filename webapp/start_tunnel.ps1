# LiveJEPA HTTPS tunnel - exposes the local server at a public https://*.trycloudflare.com URL.
#
# WHY: browsers only allow webcam (getUserMedia) on localhost or HTTPS. To use the
# laptop webcam against this GPU server, open the tunnel URL on the laptop.
#
# Uses cloudflared "quick tunnel": free, no account, no config. The URL changes on
# every launch - copy it from the output below.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File webapp\start_tunnel.ps1
#   powershell -File webapp\start_tunnel.ps1 -Port 8000
#
# SECURITY: the URL is public (unguessable, but public). Set $env:LIVEJEPA_TOKEN
# before starting the server, then share the URL as  https://<url>/?token=<secret>

param([int]$Port = 8000)

$exe = Join-Path $PSScriptRoot "cloudflared.exe"
if (-not (Test-Path $exe)) {
    Write-Host "Downloading cloudflared (one-time, ~60 MB)..."
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
}

Write-Host "Starting tunnel -> http://127.0.0.1:$Port"
Write-Host "Look for the  https://xxxx.trycloudflare.com  URL below and open it in your laptop browser."
& $exe tunnel --url "http://127.0.0.1:$Port"
