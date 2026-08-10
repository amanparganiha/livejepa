# LiveJEPA - D.4 stages 4+5 (resume): predictor-mode Pareto on EgoExo with the
# IN-DOMAIN predictor, scored with BOTH metrics.
#
# Stages 1-3 are already complete (2026-07-29):
#   extraction 11,556 train / 446 val pairs; training 20k steps;
#   gate on held-out EgoExo takes = cos 0.599 (the COIN-trained predictor was
#   semantically unusable on this domain, so the in-domain model genuinely works).
# Stage 4 began but was interrupted after 12/40 takes. Encoded streams cache
# per-take, so this resumes from take 13.
#
# THE QUESTION: with a predictor that actually speaks EgoExo, does adaptive
# selective decoding beat uniform on atomic descriptions - reconciling our D.1
# negative with the paper's 2.85x - or is the redundancy limit confirmed
# end-to-end on the paper's own benchmark?
#
# Pure ASCII (PowerShell 5.1).

$repo = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo"
$logDir = Join-Path $repo "logs"
$log = Join-Path $logDir "d4_stage45.log"
$ckpt = "checkpoints_egoexo/predictor_20000.pt"

Set-Location $repo
New-Item -ItemType Directory -Force $logDir | Out-Null
function Log($m) { Add-Content -Path $log -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $m) }

Log "=== D4 stage 4 (resume): predictor-mode Pareto, CIDEr ==="
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\stop_server.ps1") *>> $log
Start-Sleep -Seconds 5

python -u -m livejepa.run_eval --dataset egoexo --mode predictor `
    --ckpt $ckpt --gt-source atomic `
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 `
    --decode-cache eval_data/decode_cache_egoexo_indomain.jsonl `
    --out results_egoexo_predictor_40_indomain *>> $log
Log ("stage 4 exited code " + $LASTEXITCODE)

Log "=== D4 stage 5: same takes, semantic metric + controls ==="
python -u scripts/eval_semantic_pareto.py --ckpt $ckpt `
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 `
    --out results_egoexo_predictor_40_indomain_semantic *>> $log
Log ("stage 5 exited code " + $LASTEXITCODE)

# pooling ablation, to separate temporal SELECTION from denoising (as in D.3)
Log "=== D4 stage 5b: semantic metric with pooling DISABLED ==="
python -u scripts/eval_semantic_pareto.py --ckpt $ckpt --pool none `
    --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 `
    --out results_egoexo_predictor_40_indomain_semantic_nopool *>> $log

# restore the demo on the COIN champion (the EgoExo ckpt is for evaluation only)
$env:LIVEJEPA_CKPT = Join-Path $repo "checkpoints_c1_final\predictor_30000.pt"
$env:LIVEJEPA_TOKEN = "livejepa-demo-2026"
powershell -ExecutionPolicy Bypass -File (Join-Path $repo "webapp\start_server.ps1") *>> $log

Log "=== D4 stages 4+5 DONE ==="
