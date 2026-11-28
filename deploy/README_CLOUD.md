# LiveJEPA on a rented GPU (RunPod / Vast.ai)

Rent an RTX 4090 (or 3090) for an hour or two and run the **real-time** demo, or
fast training. The first deployment (2026-11-22: RTX 4090 at $0.89/hr, about
70 minutes including setup) cost $1.06.

## Step 0 — build the bundle (on your machine, once)

```powershell
python scripts/make_cloud_bundle.py        # -> livejepa_cloud.zip (~300 MB)
```

## Step 1 — rent the pod (RunPod, recommended for simplicity)

1. runpod.io → Deploy → pick **RTX 4090** (or 3090 to save money), Community Cloud.
2. Template: **RunPod PyTorch** (torch + CUDA preinstalled).
3. Before deploying, click *Edit Template*: HTTP ports **8888, 8000** (8888 is
   Jupyter, 8000 the demo) and container disk **50 GB** (the models need ~7 GB).
4. Deploy. Wait until Running.

## Step 2 — upload the bundle

Easiest: the pod's **Jupyter Lab** (Connect → Jupyter Lab) → drag-and-drop
`livejepa_cloud.zip` into `/workspace`.
(Alternative: `runpodctl send livejepa_cloud.zip` locally, `runpodctl receive <code>` on the pod.)

## Step 3 — setup + run (pod terminal)

```bash
cd /workspace
unzip -o livejepa_cloud.zip -d livejepa && cd livejepa
export LIVEJEPA_TOKEN="pick-a-secret"      # optional; defaults to livejepa-demo-2026
bash deploy/cloud_setup.sh
```

The script installs packages, checks the GPU, checkpoint and caption tokenizer,
starts the server, then **waits while the models download (~7 GB on a fresh
pod)** and ends with `READY` and the address to open. If something fails it
prints the last lines of `server.log`. Re-running it is safe: it replaces the
server from the earlier run (do this after changing `LIVEJEPA_TOKEN`).

## Step 4 — open the demo

RunPod: **Connect → HTTP Service [8000]** gives an HTTPS URL like
`https://<pod-id>-8000.proxy.runpod.net`. Open:

```
https://<pod-id>-8000.proxy.runpod.net/?token=pick-a-secret
```

That opens the white brand page; its **Open the live demo** button goes to `/demo`
and carries the `?token=` along (so do the links to and from `/about`).

HTTPS means the **webcam works directly** — no tunnel needed. A 4090 takes 0.10 s
per window (measured 2026-11-22; the T1000 takes 4.65 s), so captions keep up live.

Point the camera **down at your hands**: both models learned from hands-and-objects
footage, so a laptop webcam facing you gives off-topic captions. On a phone, open
the same link: the page uses the back camera, so the screen still faces you.

Vast.ai instead: choose a "pytorch" image, add port mapping 8000, then use the
instance's "Open" button URL — or run cloudflared inside the pod if no HTTPS port
is offered:
`wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cf && chmod +x cf && ./cf tunnel --url http://localhost:8000`

## Training on the pod instead (optional)

Same bundle contains the full training pipeline:

```bash
python scripts/download_coin_subset.py --per-class 8 --out-dir eval_data/coin_videos_train
python scripts/build_coin_cache.py --config configs/default.yaml --eval-root eval_data \
       --train-dir data_cache_coin3 --val-dir data_cache_coin3_val
python -m livejepa.train --config configs/default.yaml --data-root data_cache_coin3 \
       --ckpt-dir checkpoints_cloud --max-steps 20000 --batch-size 64
```

Download the resulting `checkpoints_cloud/predictor_*.pt` before stopping the pod
(Jupyter file browser → right-click → Download).

## Cost control — read this

- **STOP (terminate) the pod when done** — billing runs while it exists, even idle.
  "Stop" on RunPod still bills storage; *Terminate* ends all charges.
- Models re-download on a fresh pod (~7 GB, a few minutes on datacenter internet) — fine.
- A demo session (setup 10 min + 1 h of playing) on a 4090 at $0.89/hr ≈ $1.05.
- RunPod shows *Terminate* only after *Stop Pod*: stop first, then terminate.
- Nothing sensitive is in the bundle; the token gates uploads/jobs on the public URL.
