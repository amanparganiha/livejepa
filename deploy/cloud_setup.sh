#!/usr/bin/env bash
# LiveJEPA — one-shot setup on a rented Linux GPU pod (RunPod / Vast.ai).
#
# Prereq: livejepa_cloud.zip uploaded to the pod (see deploy/README_CLOUD.md).
# Usage:
#   bash deploy/cloud_setup.sh            # after unzipping, from the repo dir
#   # or, starting from just the zip in the current directory:
#   unzip -o livejepa_cloud.zip -d livejepa && cd livejepa && bash deploy/cloud_setup.sh
#
# Then open the pod's HTTPS proxy URL for port 8000 (RunPod: Connect -> HTTP 8000)
# with ?token=$LIVEJEPA_TOKEN appended.
set -e

echo "== 1/4 system packages (opencv/ffmpeg deps) =="
if command -v apt-get >/dev/null; then
    apt-get update -qq && apt-get install -y -qq libgl1 libglib2.0-0 ffmpeg unzip > /dev/null
fi

echo "== 2/4 python packages (torch is preinstalled on GPU templates; pip skips it) =="
pip install -q -r requirements.txt

echo "== 3/4 sanity: GPU + checkpoint =="
python - <<'EOF'
import torch, os
assert torch.cuda.is_available(), "No CUDA GPU visible — pick a GPU pod/template!"
print("GPU:", torch.cuda.get_device_name(0))
ck = "checkpoints_kaggle/predictor_20000.pt"
assert os.path.exists(ck), f"missing {ck} — was the bundle built with the checkpoint?"
print("checkpoint OK:", os.path.getsize(ck)//1_000_000, "MB")
EOF

echo "== 4/4 starting server on 0.0.0.0:8000 =="
export LIVEJEPA_TOKEN="${LIVEJEPA_TOKEN:-livejepa-demo-2026}"
echo "access token: $LIVEJEPA_TOKEN   (override by exporting LIVEJEPA_TOKEN before running)"
echo "first start downloads V-JEPA 2 + SONAR (~5 GB) from HuggingFace — watch /health"
# nohup so it survives the setup shell closing; log to server.log
nohup python -m uvicorn webapp.backend:app --host 0.0.0.0 --port 8000 --log-level info \
      > server.log 2>&1 &
echo "server PID $!  — logs: tail -f server.log"
echo "poll readiness:  curl -s localhost:8000/health"
