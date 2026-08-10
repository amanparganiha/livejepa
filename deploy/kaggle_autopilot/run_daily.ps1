# LiveJEPA Kaggle autopilot - daily DOWNLOAD driver (institute machine).
# The Kaggle WEB SCHEDULER starts the GPU run each morning (API pushes cannot get
# GPU - verified 2026-07-17: pushed runs land on CPU-only torch). This script runs
# at noon: waits out any still-running kernel, then banks the newest tar into
# backups\. Pure ASCII file (PS 5.1).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$dir = Join-Path $repo "deploy\kaggle_autopilot"
$log = Join-Path $dir "autopilot.log"
$kernel = "amanparganiha/notebook3308534b33"

function Log($msg) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$stamp] $msg"
}

Set-Location $repo
Log "=== download driver starting ==="

# if the scheduled run is still going, wait (up to 4 h)
$deadline = (Get-Date).AddHours(4)
while ((Get-Date) -lt $deadline) {
    $s = kaggle kernels status $kernel 2>&1 | Out-String
    Log ("status: " + $s.Trim())
    if ($s -notmatch "RUNNING|QUEUED") { break }
    Start-Sleep -Seconds 300
}

$outDir = Join-Path $repo "backups\kaggle_daily"
New-Item -ItemType Directory -Force $outDir | Out-Null
Get-ChildItem $outDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -Confirm:$false
kaggle kernels output $kernel -p $outDir 2>&1 | Out-String | ForEach-Object { Log ("output: " + $_.Trim()) }

$tars = Get-ChildItem $outDir -Filter "coin_cache_p*.tar" -ErrorAction SilentlyContinue |
        Sort-Object { [int]($_.Name -replace '\D', '') }
if ($tars) {
    $newest = $tars[-1]
    $destName = Join-Path (Join-Path $repo "backups") $newest.Name
    Move-Item $newest.FullName $destName -Force
    Log ("banked: " + $newest.Name + " -> backups\")
} else {
    Log "no coin_cache_p*.tar in latest output (run failed or not yet done) - will retry tomorrow"
}
Get-ChildItem $outDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -Confirm:$false
Log "=== download driver done ==="
