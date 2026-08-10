# LiveJEPA - D.3: EgoExo4D predictor-mode eval (the last open experiment).
#
# THE QUESTION: D.1 showed that on a CLEAN ground-truth stream of atomic
# descriptions, uniform decoding beats adaptive at every budget - the annotation
# density (~1 event / 2 s) leaves no redundancy to exploit. But VL-JEPA's own
# 2.85x headline was measured on their PREDICTED stream, which is smoother and
# denoised by the predictor. So: does running the FULL SYSTEM (V-JEPA 2 ->
# predictor -> SONAR) recover an adaptive advantage on atomic content where the
# clean stream could not?
#
# Setup: 40 density-matched val takes spread over 8 scenarios
# (eval_data/egoexo_takes_pred40.txt), champion checkpoint, --max-seconds 360
# (same cap as D.1; keeps 99% of annotations, 37/40 takes fully covered).
#
# Cost: ~14.5k windows to encode on the T1000 (~13 h) + ~3 h sweep. Resumable -
# encoded streams cache per-checkpoint under eval_data/streams/ and SONAR decodes
# persist to a JSONL cache, so a crash/restart resumes rather than restarts.
#
# Launched via Task Scheduler so it survives the terminal/agent session.
# Pure ASCII (PowerShell 5.1).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$logDir = Join-Path $repo "logs"
$log = Join-Path $logDir "d3_egoexo_predictor.log"
$ckpt = "checkpoints_c1_final/predictor_30000.pt"

Set-Location $repo
New-Item -ItemType Directory -Force $logDir | Out-Null
function Log($m) { Add-Content -Path $log -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $m) }

Log "=== D3 EgoExo predictor-mode eval starting ==="

# free the GPU (SONAR + V-JEPA 2 will not fit alongside the demo on 8 GB)
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\stop_server.ps1") *>> $log
Start-Sleep -Seconds 5

python -u -m livejepa.run_eval --dataset egoexo --mode predictor `
    --ckpt $ckpt --gt-source atomic `
    --uids-file eval_data/egoexo_takes_pred40.txt `
    --max-seconds 360 `
    --decode-cache eval_data/decode_cache_egoexo_pred.jsonl `
    --out results_egoexo_predictor_40 *>> $log

Log ("eval exited code " + $LASTEXITCODE)

# restore the demo on the champion checkpoint
$env:LIVEJEPA_CKPT = Join-Path $repo "checkpoints_c1_final\predictor_30000.pt"
$env:LIVEJEPA_TOKEN = "livejepa-demo-2026"
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\start_server.ps1") *>> $log

Log "=== D3 DONE - results_egoexo_predictor_40.json ==="
