# LiveJEPA - D.4: build an IN-DOMAIN EgoExo predictor, then redo the D.3 eval.
#
# WHY: D.3 (predictor-mode on EgoExo) was uninterpretable because our predictor is
# COIN-trained - it emits imperative step labels ("remove the chain") while EgoExo
# annotates descriptively ("the camera wearer takes a tire lever ... with his right
# hand"). CIDEr floored at 0.012 despite semantically CORRECT predictions, and the
# style-robust semantic metric had near-zero temporal sensitivity (nearest-vs-random
# alignment lift +0.0012). 58% of the apparent adaptive win was mean-pooling
# denoising, not selection. Root cause: no in-domain predictor.
#
# This script: (1) extracts EgoExo training pairs with windowing IDENTICAL to
# inference, (2) trains a predictor on them, (3) gates it, (4) re-runs the
# predictor-mode Pareto on the 40 held-out takes with BOTH metrics.
#
# Leakage control: the 40 D.3 eval takes are excluded from training entirely;
# 25 further takes are held out for gating.
#
# Stage 1 is the long pole (~10 h) and is RESUMABLE - rerun to continue.
# Pure ASCII (PowerShell 5.1).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$logDir = Join-Path $repo "logs"
$log = Join-Path $logDir "d4_egoexo_predictor.log"

Set-Location $repo
New-Item -ItemType Directory -Force $logDir | Out-Null
function Log($m) { Add-Content -Path $log -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $m) }

Log "=== D4 stage 1: extracting EgoExo training pairs ==="
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\stop_server.ps1") *>> $log
Start-Sleep -Seconds 5

python -u scripts/build_egoexo_cache.py --max-per-take 20 --max-samples 12000 *>> $log
Log ("extraction exited code " + $LASTEXITCODE)

$n = (Get-ChildItem "data_cache_egoexo" -Filter "*.npz" -ErrorAction SilentlyContinue | Measure-Object).Count
$nv = (Get-ChildItem "data_cache_egoexo_val" -Filter "*.npz" -ErrorAction SilentlyContinue | Measure-Object).Count
Log ("cache: train=" + $n + " val=" + $nv)
if ($n -lt 2000) {
    Log "too few samples to train - rerun this script to continue extraction"
    exit 1
}

Log "=== D4 stage 2: training the in-domain predictor (20k steps) ==="
python -u -m livejepa.train --config configs/default.yaml `
    --data-root data_cache_egoexo --ckpt-dir checkpoints_egoexo `
    --max-steps 20000 --batch-size 32 *>> $log
Log ("training exited code " + $LASTEXITCODE)

$ckpt = "checkpoints_egoexo/predictor_20000.pt"
if (-not (Test-Path $ckpt)) {
    $latest = Get-ChildItem "checkpoints_egoexo" -Filter "predictor_*.pt" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime | Select-Object -Last 1
    if ($latest) { $ckpt = "checkpoints_egoexo/" + $latest.Name }
}

Log ("=== D4 stage 3: gating " + $ckpt + " on held-out EgoExo takes ===")
python scripts/eval_predictor.py --ckpt $ckpt --val data_cache_egoexo_val --decode *>> $log

Log "=== D4 stage 4: predictor-mode Pareto on the 40 eval takes (CIDEr) ==="
python -u -m livejepa.run_eval --dataset egoexo --mode predictor `
    --ckpt $ckpt --gt-source atomic `
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 `
    --decode-cache eval_data/decode_cache_egoexo_indomain.jsonl `
    --out results_egoexo_predictor_40_indomain *>> $log

Log "=== D4 stage 5: same takes, semantic metric + controls ==="
python -u scripts/eval_semantic_pareto.py --ckpt $ckpt `
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 `
    --out results_egoexo_predictor_40_indomain_semantic *>> $log

# restore the demo on the COIN champion (EgoExo ckpt is for evaluation, not the demo)
$env:LIVEJEPA_CKPT = Join-Path $repo "checkpoints_c1_final\predictor_30000.pt"
$env:LIVEJEPA_TOKEN = "livejepa-demo-2026"
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\start_server.ps1") *>> $log

Log "=== D4 DONE ==="
