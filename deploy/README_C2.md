# Rung C2 — train on Action100M on a rented RTX 4090 (beginner runbook)

Goal: train the predictor on **Action100M** (the paper's own data) on a fast GPU,
bring the checkpoint home, and add a new row to the scaling table. Budget ~$8-10;
you loaded $15. **The pod trains; we grade the result at home on the T1000.**

> ⚠️ **Two money rules, read first:**
> 1. **Pick an RTX 4090** (~$0.35-0.70/hr). Do NOT pick B200 / H200 / RTX PRO 6000
>    (they are $2-6/hr and would burn $15 in ~3 hours).
> 2. **TERMINATE the pod when done.** RunPod bills for as long as the pod *exists*,
>    even idle. "Stop" is not enough — use **Terminate**.

---

## Before you start
- RunPod account with ~$15 credit ✅ (done)
- `livejepa_cloud.zip` on your PC (Claude rebuilds this with `--c2`; ~300 MB)

## Step 1 — deploy the pod
1. runpod.io → **Pods → Deploy**.
2. **Template:** leave **RunPod PyTorch 2.8** (torch + CUDA preinstalled).
3. **GPU:** type **`4090`** in the GPU search box → pick **RTX 4090**, **Community
   Cloud** (cheapest). If none free, an **RTX 3090** (~$0.22/hr) also works.
4. Click **Set overrides / Edit** → set **Container Disk = 80 GB** (the feature
   cache + models need room). Leave "Start Jupyter notebook" checked.
5. **Deploy** → wait until the pod shows **Running** (~1 min).

## Step 2 — upload the bundle
1. On the pod card, **Connect → Jupyter Lab**.
2. In Jupyter, make sure you are in `/workspace` (left file panel).
3. **Drag `livejepa_cloud.zip` from your PC into the Jupyter file panel.** Wait for
   the upload to finish (a few minutes).

## Step 3 — launch (one command)
Open a terminal in Jupyter (**File → New → Terminal**) and paste:

```bash
cd /workspace && unzip -o livejepa_cloud.zip -d livejepa && cd livejepa
bash deploy/run_c2.sh 2>&1 | tee c2_run.log
```

That's it. The script installs deps, downloads ~5 GB of models, then downloads +
extracts Action100M, trains, gates, and packages the result. **Leave it running.**

## Step 4 — monitor (check in occasionally)
- Progress prints live. Extraction is the long part (`cached N this run (…s/clip)`),
  then training (`step … loss …`).
- **Watch your credit** (top-right `$` on RunPod). If it approaches ~$12, or you
  want to stop early, that's fine — checkpoints save every 1000 steps, so whatever
  finished is usable (see Step 5).
- If you see `YouTube is throttling this IP … stopping`, that's expected and
  handled — training will proceed on what was extracted.

## Step 5 — bring the result home
When you see `C2 DONE. DOWNLOAD c2_out.tar.gz`:
1. Jupyter file panel → right-click **`c2_out.tar.gz`** → **Download**.
   (If the run stopped early, download the newest `checkpoints_c2/predictor_*.pt`.)
2. Put it in the repo under `checkpoints_c2/` on your PC (Claude will unpack it).

## Step 6 — TERMINATE the pod
RunPod → your pod → **Terminate** (the trash/stop icon → Terminate, not just Stop).
Confirm the pod is gone. Billing stops here.

## Step 7 — at home (Claude does this)
- Unpack `c2_out.tar.gz`, gate the C2 checkpoint on the **frozen COIN vals**
  (data_cache_coin2_val + data_cache_coin_full_val) → the new scaling-table row.
- Run the predictor-mode **EgoExo atomic eval** on the T1000 (videos already local,
  no AWS creds on a rented pod) — the open question from the D.1 result.
- Update RESULTS.md / THESIS.md with the C2 row.

---

## Troubleshooting
- **Card declined at billing:** enable international/online payments in your bank
  app, or use a card that supports USD transactions.
- **"CUDA not available" / no GPU in `nvidia-smi`:** you picked a CPU pod — Terminate
  and redeploy choosing a 4090.
- **Upload is slow:** the bundle is ~300 MB; on a slow link use RunPod's
  `runpodctl send livejepa_cloud.zip` on your PC → `runpodctl receive <code>` on the pod.
- **Ran out of credit mid-training:** no problem — download the newest
  `checkpoints_c2/predictor_*.pt`; even a partial run is a valid data point.

*Cost math: 4090 @ ~$0.40/hr. Extraction ~10-14 h + train ~2-3 h + setup ~0.5 h
≈ 13-18 h ≈ $5-8. The $15 covers it with margin.*
