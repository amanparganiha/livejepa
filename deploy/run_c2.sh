#!/usr/bin/env bash
# LiveJEPA rung C2 - train the predictor on Action100M (the paper's own data)
# on a rented RTX 4090. Run from the unzipped repo root ON THE POD:
#
#     cd /workspace/livejepa && bash deploy/run_c2.sh
#
# Design: "pod trains, home gates". This script downloads a slice of Action100M,
# extracts features (chunked download->extract->DELETE so a small disk is fine),
# trains, and gates IN-DOMAIN on the A100M val. You then download the checkpoint
# and gate it on the frozen COIN vals at home on the T1000.
#
# Everything is resumable: if YouTube throttles the pod, extraction stops cleanly
# with the cache saved and training proceeds on whatever landed (a valid, smaller
# scaling point). Checkpoints save every 1000 steps, so a partial run is usable.
#
# Tunables via env (sensible defaults chosen to fit a ~$8-10 weekend):
#     SHARDS=3 MAXVID=2000 STEPS=30000 BS=64 bash deploy/run_c2.sh
set -e
cd "$(dirname "$0")/.."

SHARDS="${SHARDS:-3}"       # Action100M annotation shards (1 shard ~ 930 vids / 19k segs)
MAXVID="${MAXVID:-2000}"    # cap videos (extraction stops earlier if throttled)
STEPS="${STEPS:-30000}"
BS="${BS:-64}"

echo "=== C2 config: SHARDS=$SHARDS MAXVID=$MAXVID STEPS=$STEPS BS=$BS ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

# 0. deps (torch is preinstalled on the RunPod PyTorch template)
echo "=== installing deps ==="
pip install -q transformers accelerate sentencepiece einops pyyaml \
    scikit-learn scipy opencv-python-headless yt-dlp pandas pyarrow

# 1. GPU config
python - <<'PY'
import yaml
c = yaml.safe_load(open('configs/default.yaml'))
c['project']['use_stubs'] = False
c['project']['device'] = 'cuda'
c['encoders']['sonar']['backend'] = 'transformers'
yaml.safe_dump(c, open('configs/c2.yaml', 'w'))
print('wrote configs/c2.yaml')
PY

# 2. Action100M download + extract (chunked, resumable, throttle-safe).
#    First model use pulls ~5 GB of V-JEPA 2 + SONAR weights (a couple of minutes).
echo "=== extracting Action100M features (this is the long pole) ==="
python scripts/action100m_pipeline.py --config configs/c2.yaml \
    --shards "$SHARDS" --max-videos "$MAXVID" --chunk 200 --sleep 1 \
    --train-dir data_cache_a100m --val-dir data_cache_a100m_val

TRAIN_N=$(ls data_cache_a100m/*.npz 2>/dev/null | wc -l)
VAL_N=$(ls data_cache_a100m_val/*.npz 2>/dev/null | wc -l)
echo "=== extracted: train=$TRAIN_N val=$VAL_N clips ==="
if [ "$TRAIN_N" -lt 500 ]; then
    echo "!! too few clips ($TRAIN_N) - YouTube likely throttled early. You can"
    echo "   re-run this script later (it resumes) before training, or proceed."
fi

# 3. train on Action100M
echo "=== training predictor on Action100M ==="
python -m livejepa.train --config configs/c2.yaml \
    --data-root data_cache_a100m --ckpt-dir checkpoints_c2 \
    --max-steps "$STEPS" --batch-size "$BS"

CKPT="checkpoints_c2/predictor_${STEPS}.pt"
[ -f "$CKPT" ] || CKPT=$(ls -t checkpoints_c2/predictor_*.pt | head -1)   # latest if partial
echo "=== gating $CKPT on the in-domain A100M val ==="
python scripts/eval_predictor.py --ckpt "$CKPT" --val data_cache_a100m_val --decode \
    2>&1 | tee results_c2_a100m_gate.txt

# 4. package for download (checkpoints + gate report + val uid list)
tar -czf c2_out.tar.gz checkpoints_c2 results_c2_a100m_gate.txt \
    data_cache_a100m_val/VAL_UIDS.txt
echo ""
echo "=========================================================================="
echo " C2 DONE.  DOWNLOAD  c2_out.tar.gz  (Jupyter: right-click -> Download)"
echo " THEN *TERMINATE* THE POD (billing continues while it exists)."
echo "=========================================================================="
