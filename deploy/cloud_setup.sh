#!/usr/bin/env bash
# LiveJEPA — one-shot setup on a rented Linux GPU pod (RunPod / Vast.ai).
#
# Prereq: livejepa_cloud.zip uploaded to the pod (see deploy/README_CLOUD.md).
# Usage:
#   bash deploy/cloud_setup.sh            # after unzipping, from the repo dir
#   # or, starting from just the zip in the current directory:
#   unzip -o livejepa_cloud.zip -d livejepa && cd livejepa && bash deploy/cloud_setup.sh
#
# Safe to re-run (after a fix, or to change LIVEJEPA_TOKEN): it replaces a server
# left running by an earlier run. It waits until the models are loaded and prints
# the address to open: the pod's HTTPS proxy URL for port 8000 with ?token=... .
set -e
cd "$(dirname "$0")/.."      # the repo root, wherever this was started from

echo "== 1/4 system packages (opencv/ffmpeg deps) =="
if command -v apt-get >/dev/null; then
    apt-get update -qq && apt-get install -y -qq libgl1 libglib2.0-0 ffmpeg unzip > /dev/null
fi

echo "== 2/4 python packages (torch is preinstalled on GPU templates; pip skips it) =="
pip install -q -r requirements.txt

echo "== 3/4 sanity: GPU, checkpoint, caption tokenizer =="
python - <<'EOF'
import os, torch, yaml
assert torch.cuda.is_available(), "No CUDA GPU visible — pick a GPU pod/template!"
print("GPU:", torch.cuda.get_device_name(0))
ck = "checkpoints_c1_final/predictor_30000.pt"   # the model webapp/backend.py serves
assert os.path.exists(ck), f"missing {ck} — was the bundle built with the checkpoint?"
print("checkpoint OK:", os.path.getsize(ck)//1_000_000, "MB")
eg = "checkpoints_egoexo/predictor_20000.pt"           # the demo's second, switchable model
print("everyday-actions model:", "OK" if os.path.exists(eg)
      else "not bundled (the demo will offer how-to steps only)")
# The decoder's tokenizer is built from sentencepiece.bpe.model, which needs protobuf.
# Without it every caption fails, so stop here instead (a small download).
from transformers import AutoTokenizer
dec = yaml.safe_load(open("configs/default.yaml"))["encoders"]["sonar"]["hf_decoder"]
AutoTokenizer.from_pretrained(dec)
print("caption tokenizer OK:", dec)
EOF

echo "== 4/4 starting server on 0.0.0.0:8000 =="
# An earlier run's server would keep port 8000 (and its old token): replace it.
if pgrep -f 'uvicorn webapp.backend:app' >/dev/null 2>&1; then
    echo "stopping the server from an earlier run"
    pkill -f 'uvicorn webapp.backend:app' || true
    sleep 3
fi
export LIVEJEPA_TOKEN="${LIVEJEPA_TOKEN:-livejepa-demo-2026}"
export LIVEJEPA_EAGER_DECODER=1   # load the caption decoder at startup; the GPU has room
echo "access token: $LIVEJEPA_TOKEN   (override by exporting LIVEJEPA_TOKEN before running)"
# nohup so it survives the setup shell closing; append to server.log
nohup python -m uvicorn webapp.backend:app --host 0.0.0.0 --port 8000 --log-level info \
      >> server.log 2>&1 &
PID=$!
echo "server PID $PID  — logs: tail -f server.log"

echo "first start downloads V-JEPA 2 + the SONAR decoder (~7 GB) from HuggingFace; waiting..."
ready=0
for i in $(seq 1 180); do                     # up to 15 minutes
    sleep 5
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "SERVER EXITED — last lines of server.log:"
        tail -n 30 server.log
        exit 1
    fi
    h=$(python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read().decode())" 2>/dev/null || true)
    case "$h" in
        *'"model_loaded":true'*) ready=1; echo "READY: $h"; break ;;
        *'"error":"'*) echo "MODEL LOAD FAILED: $h"; tail -n 30 server.log; exit 1 ;;
    esac
    if [ $((i % 12)) -eq 0 ]; then echo "  still loading ($((i / 12)) min)..."; fi
done
if [ "$ready" != 1 ]; then
    echo "not ready after 15 min; the server is still running. Watch: tail -f server.log"
fi

echo
if [ -n "${RUNPOD_POD_ID:-}" ]; then
    echo "Open:  https://${RUNPOD_POD_ID}-8000.proxy.runpod.net/?token=${LIVEJEPA_TOKEN}"
else
    echo "Open the pod's HTTPS address for port 8000 with ?token=${LIVEJEPA_TOKEN} appended."
fi
echo "(RunPod: Connect -> HTTP Service [8000] shows the exact address.)"
