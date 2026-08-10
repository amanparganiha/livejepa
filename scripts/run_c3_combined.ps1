# LiveJEPA - combined COIN + Action100M training (free, local T1000).
#
# Tests whether open-vocabulary A100M data helps as AUGMENTATION rather than as a
# replacement (rung C2 showed replacement loses: 0.348 vs 0.401 scale-matched).
# Hypothesis: COIN's 747-label closed set supplies anchor structure while A100M's
# 6,096 unique captions supply vocabulary breadth.
#
# Recipe deliberately IDENTICAL to the C1-final row (30k steps, batch 32) so the
# result slots straight into the scaling table; only the data mix changes:
#   COIN 26,863 + A100M 6,710 = 33,573 clips.
#
# Gates on ALL THREE benchmarks so it is comparable everywhere:
#   frozen COIN-137 (C1-final 0.897) | COIN-956 (0.846) | A100M-160 (best 0.401)
#
# Launched via Task Scheduler so it survives the terminal/agent session.
# Pure ASCII (PowerShell 5.1).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$logDir = Join-Path $repo "logs"
$log = Join-Path $logDir "c3_combined.log"

Set-Location $repo
New-Item -ItemType Directory -Force $logDir | Out-Null
function Log($m) { Add-Content -Path $log -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $m) }

Log "=== C3 combined COIN+A100M training starting ==="

python -u -m livejepa.train --config configs/default.yaml `
    --data-root "data_cache_coin_full,data_cache_a100m" `
    --ckpt-dir checkpoints_c3_combined `
    --max-steps 30000 --batch-size 32 *>> $log

Log ("training exited code " + $LASTEXITCODE)

$ckpt = "checkpoints_c3_combined/predictor_30000.pt"
if (-not (Test-Path $ckpt)) {
    $latest = Get-ChildItem "checkpoints_c3_combined" -Filter "predictor_*.pt" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime | Select-Object -Last 1
    if ($latest) { $ckpt = "checkpoints_c3_combined/" + $latest.Name }
}
Log ("gating " + $ckpt)

Log "--- frozen COIN-137 (baseline 0.897) ---"
python scripts/eval_predictor.py --ckpt $ckpt --val data_cache_coin2_val --decode *>> $log
Log "--- COIN-956 (baseline 0.846) ---"
python scripts/eval_predictor.py --ckpt $ckpt --val data_cache_coin_full_val *>> $log
Log "--- A100M-160 (best so far 0.401) ---"
python scripts/eval_predictor.py --ckpt $ckpt --val data_cache_a100m_val --decode *>> $log

# restore the demo on the C1 checkpoint (swap later only if C3 gates better)
$env:LIVEJEPA_CKPT = Join-Path $repo "checkpoints_c1_final\predictor_30000.pt"
$env:LIVEJEPA_TOKEN = "livejepa-demo-2026"
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\start_server.ps1") *>> $log

Log "=== C3 combined DONE ==="
