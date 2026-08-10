# LiveJEPA - D.2 full-system COIN Pareto with the FINAL checkpoint.
#
# Tests plan Phase D.3: does the better-trained predictor (cos 0.846 vs the old
# 0.636) recover adaptive's mid-band advantage that the old run lost? Runs BOTH
# checkpoints on the SAME 7 leakage-clean held-out COIN videos (verified in
# neither the predictor train nor val cache) for an apples-to-apples comparison.
#
# Launched via Task Scheduler so it survives the session. Stops the demo first
# (the T1000 cannot hold two model copies), runs both evals, then restarts the
# demo on the final checkpoint. Crash-safe: decode cache + partial-json flush.
# Pure ASCII (PowerShell 5.1).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$logDir = Join-Path $repo "logs"
$log = Join-Path $logDir "d2_coin_pareto.log"
$final = "checkpoints_c1_final/predictor_30000.pt"
$old = "checkpoints_kaggle/predictor_20000.pt"

Set-Location $repo
New-Item -ItemType Directory -Force $logDir | Out-Null
function Log($m) { Add-Content -Path $log -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $m) }

Log "=== D2 COIN Pareto starting ==="

# free the GPU
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\stop_server.ps1") *>> $log
Start-Sleep -Seconds 5

# 1. FINAL checkpoint (fresh encode of the 7 videos, ~2.5 h)
Log "final ckpt eval starting"
python -u -m livejepa.run_eval --dataset coin --mode predictor --ckpt $final `
    --coin-split val --max-videos 7 --max-seconds 180 `
    --decode-cache eval_data/decode_cache_coin_pred.jsonl `
    --out results_coin_predictor_c1final *>> $log
Log ("final ckpt eval exited code " + $LASTEXITCODE)

# 2. OLD checkpoint on the SAME 7 videos (streams cached -> fast; guarantees
#    an identical-video baseline instead of trusting the 2026-07-09 json)
Log "old ckpt eval starting"
python -u -m livejepa.run_eval --dataset coin --mode predictor --ckpt $old `
    --coin-split val --max-videos 7 --max-seconds 180 `
    --decode-cache eval_data/decode_cache_coin_pred.jsonl `
    --out results_coin_predictor_c1old *>> $log
Log ("old ckpt eval exited code " + $LASTEXITCODE)

# 3. restore the demo on the final checkpoint
$env:LIVEJEPA_CKPT = Join-Path $repo "checkpoints_c1_final\predictor_30000.pt"
$env:LIVEJEPA_TOKEN = "livejepa-demo-2026"
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\start_server.ps1") *>> $log

Log "=== D2 COIN Pareto done ==="
