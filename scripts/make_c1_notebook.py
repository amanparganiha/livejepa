"""Generate notebooks/kaggle_c1_full_coin.ipynb — the rung-C1 (full-COIN) notebook.

Regenerable so the notebook never drifts from the scripts it calls:
    python scripts/make_c1_notebook.py

If eval_data/coin_union_state.json exists (union of done/dead across ALL lanes,
built on the institute machine), it is baked into cell 5 as a compressed blob so
a Kaggle session skips every video any lane already resolved and spends its
fresh IP only on the leftovers.
"""
import base64
import json
import os
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "notebooks", "kaggle_c1_full_coin.ipynb")
UNION_PATH = os.path.join(ROOT, "eval_data", "coin_union_state.json")

UNION_BLOB = ""
if os.path.exists(UNION_PATH):
    u = json.load(open(UNION_PATH))
    payload = json.dumps({"done": sorted(u["done"]), "dead": sorted(u["dead"])})
    UNION_BLOB = base64.b64encode(zlib.compress(payload.encode(), 9)).decode()
    print(f"embedding union state: done={len(u['done'])} dead={len(u['dead'])} "
          f"blob={len(UNION_BLOB)/1024:.0f} KB")


UNION_CELL = ""
if UNION_BLOB:
    UNION_CELL = '''

# --- 5c. Fleet-union coverage (baked at notebook generation time) ---
# Videos already resolved by ANY lane (kaggle/colab/institute) are merged into
# this session's state, so the fresh Kaggle IP is spent ONLY on the leftovers.
import base64 as _b64, zlib as _zlib
_u = json.loads(_zlib.decompress(_b64.b64decode(%r)))
s = '/kaggle/working/data_cache_coin_full/pipeline_state.json'
st = json.load(open(s)) if os.path.exists(s) else {'done': [], 'dead': []}
st['done'] = sorted(set(st['done']) | set(_u['done']))
st['dead'] = sorted((set(st['dead']) | set(_u['dead'])) - set(st['done']))
json.dump(st, open(s, 'w'))
print('fleet union merged: done=%%d dead=%%d -> remaining %%d of 9023'
      %% (len(st['done']), len(st['dead']), 9023 - len(st['done']) - len(st['dead'])))''' % UNION_BLOB


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": src.splitlines(keepends=True)}


CELLS = [
    md("""# LiveJEPA — Rung C1: full-COIN feature cache (Kaggle AUTOPILOT)

Extracts features for **every COIN training video with steps** (~9k videos) via a
chunked download → extract → delete loop. **Autopilot design:** every cell is safe to
run top-to-bottom unattended — extraction stops itself when YouTube throttles, the
PACK cell bundles progress into one tar, and the train/gate cells are guarded off
(`RUN_TRAIN=False`) until the one final run.

**One-time autopilot setup:**
1. Inputs: repo zip dataset + the newest `livejepa-coin-cache-pN` + **this notebook's
   own output** (Add Input → Notebooks tab → select this notebook) — that self-input
   is how each scheduled run resumes from the previous one.
2. Run it manually once top-to-bottom to verify the loop (cell 5 must report the
   resumed `done/dead` state; the PACK cell must print the new tar).
3. Sidebar → **Schedule a notebook to run** → daily. Done — each scheduled run gets a
   fresh machine/IP, extracts ~400 videos, and saves its own output automatically.

Extraction is complete when `done + dead` reaches the printed target (9,023) — then
set `RUN_TRAIN=True` in cell 7 and run once more for the final training + gate.

> Accelerator: GPU T4. Scheduled runs consume ~2–3 GPU-h each (quota: 30 h/week)."""),

    code("""# --- 1. Get the repo (Kaggle auto-extract, raw zip, or CWD) ---
import glob, os, shutil, zipfile
DEST = '/kaggle/working/repo'
if os.path.exists('configs/default.yaml'):
    print('repo already in CWD')
else:
    zips = glob.glob('/kaggle/input/**/livejepa_kaggle.zip', recursive=True)
    root = None
    for marker in glob.glob('/kaggle/input/**/configs/default.yaml', recursive=True):
        r = os.path.dirname(os.path.dirname(marker))
        if os.path.isdir(os.path.join(r, 'livejepa')):
            root = r; break
    if zips:
        with zipfile.ZipFile(zips[0]) as z: z.extractall(DEST)
        os.chdir(DEST)
    elif root:
        if not os.path.exists(DEST): shutil.copytree(root, DEST)
        os.chdir(DEST)
    else:
        raise SystemExit('Upload livejepa_kaggle.zip via + Add Input, then re-run.')
print('CWD:', os.getcwd())"""),

    code("""# --- 2. Dependencies (torch preinstalled) ---
!pip install -q transformers accelerate sentencepiece einops pyyaml scikit-learn scipy opencv-python yt-dlp
import torch; print(torch.__version__, torch.cuda.get_device_name(0))"""),

    code("""# --- 3. GPU config ---
import yaml
cfg = yaml.safe_load(open('configs/default.yaml'))
cfg['project']['use_stubs'] = False
cfg['project']['device'] = 'cuda'
cfg['encoders']['sonar']['backend'] = 'transformers'
yaml.safe_dump(cfg, open('configs/colab.yaml', 'w'))
print('wrote configs/colab.yaml')"""),

    code("""# --- 4. COIN.json + frozen benchmark uids ---
# frozen_val_uids.txt ships in the repo (local 137-sample benchmark videos). If you
# also attached the ORIGINAL 1,118-sample val cache (data_cache_coin2_val) as a
# dataset, its uids are added too — those videos are never used for training.
import glob, os, urllib.request
os.makedirs('eval_data', exist_ok=True)
if not os.path.exists('eval_data/COIN.json'):
    from livejepa.data.coin import COIN_ANNOTATIONS_URL
    urllib.request.urlretrieve(COIN_ANNOTATIONS_URL, 'eval_data/COIN.json')
frozen = set()
if os.path.exists('eval_data/frozen_val_uids.txt'):
    frozen |= {l.strip() for l in open('eval_data/frozen_val_uids.txt') if l.strip()}
for p in glob.glob('/kaggle/input/**/data_cache_coin2_val*/coin_*.npz', recursive=True):
    frozen.add(os.path.basename(p)[len('coin_'):-len('.npz')].rsplit('_', 1)[0])
open('eval_data/frozen_val_uids.txt', 'w').write('\\n'.join(sorted(frozen)))
print(f'frozen benchmark videos (excluded from training): {len(frozen)}')"""),

    code("""# --- 5. Resume prior sessions (tar bundles and/or loose cache dirs) ---
import glob, json, os, re, shutil, subprocess
# 5a. unpack the NEWEST cumulative tar (numeric sort — p10 > p9 > p2; tars are
#     cumulative so only the newest matters; autopilot runs find their own
#     previous version's tar here via the notebook-output-as-input mount)
tars = glob.glob('/kaggle/input/**/coin_cache_p*.tar', recursive=True)
tars.sort(key=lambda p: int((re.search(r'p(\\d+)\\.tar$', p) or [0, 0])[1] or 0))
if tars:
    print('unpacking newest bundle:', tars[-1])
    subprocess.run(['tar', '-xf', tars[-1], '-C', '/kaggle/working'], check=True)
# 5b. loose npz dirs from any non-tar datasets (older sessions)
resume = sorted({os.path.dirname(p) for p in
                 glob.glob('/kaggle/input/**/data_cache_coin_full/*.npz', recursive=True)} |
                {os.path.dirname(p) for p in
                 glob.glob('/kaggle/input/**/data_cache_coin_full_val/*.npz', recursive=True)})
RESUME = ','.join(d for d in resume if not d.endswith('_val'))
RESUME_VAL = ','.join(d for d in resume if d.endswith('_val'))
os.makedirs('/kaggle/working/data_cache_coin_full', exist_ok=True)
os.makedirs('/kaggle/working/data_cache_coin_full_val', exist_ok=True)
RETRY = ''
states = ['/kaggle/working/data_cache_coin_full/pipeline_state.json'] + \\
         [os.path.join(d, 'pipeline_state.json') for d in resume]
for s in states:
    if os.path.exists(s):
        if s != states[0]:
            shutil.copy(s, states[0])
        st = json.load(open(s))
        # a throttled legacy session mass-marked good videos dead; auto-repair.
        # (threshold sits ABOVE the legitimate fleet-union dead count of ~1.6k)
        if len(st.get('dead', [])) > 3000:
            RETRY = '--retry-dead'
        print(f\"resume state: done={len(st.get('done', []))} dead={len(st.get('dead', []))}\")
        break
n_working = len(glob.glob('/kaggle/working/data_cache_coin_full/*.npz'))
print('clips already in working dir:', n_working)
print('loose resume train dirs:', RESUME or '(none)')
print('loose resume val dirs:', RESUME_VAL or '(none)')
print('dead-list repair:', RETRY or '(not needed)')""" + UNION_CELL),

    code("""# --- 6. EXTRACT (chunked; safe to stop anytime, fully resumable) ---
# ~1.5-2 s/clip on a T4. Interrupt whenever the session nears its limit, then save
# /kaggle/working/data_cache_coin_full{,_val} as a Dataset and resume next session.
# If YouTube throttles the session (streaks of failed downloads), the pipeline now
# stops itself cleanly with progress saved — just resume in a later session.
!python scripts/coin_full_pipeline.py --config configs/colab.yaml \\
    --eval-root eval_data \\
    --train-dir /kaggle/working/data_cache_coin_full \\
    --val-dir /kaggle/working/data_cache_coin_full_val \\
    --frozen-val-uids eval_data/frozen_val_uids.txt \\
    --chunk 250 --max-tokens 256 --sleep 2 --resume-dirs \"$RESUME\" $RETRY"""),

    code("""# --- 6b. PACK for saving (run when extraction stops for the day) ---
# One tar instead of thousands of tiny files — Kaggle's save 429s otherwise.
# Bump pN each session (p1, p2, ...) and create the dataset from this file.
import glob, os, re, subprocess
# prior sessions appear as tars OR as auto-unpacked dataset dirs (Kaggle extracts
# uploaded tars) — count both to pick the next part number
prior = [int(m.group(1)) for p in
         glob.glob('/kaggle/input/**/coin_cache_p*', recursive=True) +
         glob.glob('/kaggle/input/livejepa-coin-cache-p*')
         if (m := re.search(r'p(\\d+)(?:\\.tar)?$', p))]
N = max(prior, default=0) + 1
tar = f'/kaggle/working/coin_cache_p{N}.tar'
subprocess.run(['tar', '-cf', tar, '-C', '/kaggle/working',
                'data_cache_coin_full', 'data_cache_coin_full_val'], check=True)
subprocess.run(['rm', '-rf', '/kaggle/working/data_cache_coin_full',
                '/kaggle/working/data_cache_coin_full_val'], check=True)
print(f'{tar}: {os.path.getsize(tar)/1e9:.2f} GB — Quick Save, then create dataset '
      f'livejepa-coin-cache-p{N} from the Output tab')"""),

    md("""## Saving
**Autopilot (scheduled runs):** nothing to do — the PACK tar above is saved as the
version's output automatically, and the next run resumes from it via the self-input.
**Manual sessions only:** after the PACK cell, `Save Version` (**Quick Save**, with
output) → Output tab → New Dataset `livejepa-coin-cache-pN` if you also want a
standalone dataset checkpoint (good practice once every few sessions as backup)."""),

    code("""# --- 7. TRAIN — GUARDED for autopilot (scheduled runs skip this) ---
# Flip to True ONLY for the one final run after extraction covers all 9,023 videos.
RUN_TRAIN = False

import os
if RUN_TRAIN:
    data_roots = '/kaggle/working/data_cache_coin_full' + (',' + RESUME if RESUME else '')
    !python -m livejepa.train --config configs/colab.yaml \\
        --data-root \"{data_roots}\" --ckpt-dir checkpoints_c1 \\
        --max-steps 30000 --batch-size 32
else:
    print('RUN_TRAIN=False — skipping (autopilot mode). '
          'Set True for the single final training run.')"""),

    code("""# --- 8. GATE CHECK + package — GUARDED like cell 7 ---
if RUN_TRAIN:
    val_roots = '/kaggle/working/data_cache_coin_full_val' + (',' + RESUME_VAL if RESUME_VAL else '')
    !python scripts/eval_predictor.py --ckpt checkpoints_c1/predictor_30000.pt \\
        --val \"{val_roots}\" --decode
    # also score the OLD checkpoint on the SAME val for the scaling-table baseline:
    import glob as g
    olds = g.glob('/kaggle/input/**/predictor_20000.pt', recursive=True)
    if olds:
        !python scripts/eval_predictor.py --ckpt \"{olds[0]}\" --val \"{val_roots}\" --decode
    !zip -j predictor_c1.zip checkpoints_c1/predictor_30000.pt
    print('predictor_c1.zip ready — download from the output panel')
else:
    print('RUN_TRAIN=False — skipping (autopilot mode).')"""),

    md("""## Back home
Download `predictor_c1.zip` → unzip into `checkpoints_kaggle/` on the institute machine →
gate against the LOCAL 137-sample benchmark too:
```bash
python scripts/eval_predictor.py --ckpt checkpoints_kaggle/predictor_30000.pt --val data_cache_coin2_val --decode
```
Compare: old ckpt = cos 0.636 (Kaggle 1118-val) / 0.772 (local 137-val)."""),
]

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3",
                                  "language": "python"}},
      "cells": CELLS}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(nb, open(OUT, "w", encoding="utf-8"), indent=1)
print("wrote", OUT)
