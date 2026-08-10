# LiveJEPA - D.1 paper-protocol EgoExo eval (218 density-matched val takes).
#
# Launched via Windows Task Scheduler so the run survives the terminal / agent
# session that started it (background child processes do NOT survive - that is
# how the 2026-07-19 attempt was lost). Pure ASCII (PowerShell 5.1).
#
# Protocol: atomic descriptions, gt-mode, max-seconds 360 (paper takes run ~6
# min; 360 keeps 98 percent of annotations vs 84 percent at the 180 default).
# Restart-safe: SONAR decodes persist to eval_data/decode_cache.jsonl and
# partial curves flush to the results json after every (method, frequency).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$logDir = Join-Path $repo "logs"
$log = Join-Path $logDir "d1_218.log"

Set-Location $repo
New-Item -ItemType Directory -Force $logDir | Out-Null
Add-Content -Path $log -Value ("=== D1 eval starting " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")

python -u -m livejepa.run_eval --dataset egoexo --mode gt --gt-source atomic `
    --uids-file eval_data/egoexo_takes_218.txt `
    --max-seconds 360 `
    --out results_egoexo_atomic_218 *>> $log

Add-Content -Path $log -Value ("=== D1 eval exited (code " + $LASTEXITCODE + ") " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")
