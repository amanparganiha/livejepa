"""Generate notebooks/colab_c1_full_coin.ipynb — the Colab middle-lane C1 notebook.

Colab's edge over Kaggle: native Google Drive mounting, so session progress saves
to Drive AUTOMATICALLY (no Quick Save / dataset clicking). This lane starts at the
50% mark of the video list (Kaggle = front, institute T1000 = back).

Drive layout (created on first run):
    MyDrive/LiveJEPA/livejepa_kaggle.zip          <- user uploads once
    MyDrive/LiveJEPA/caches/coin_cache_colab_pN.tar  <- written automatically

Regenerate:  python scripts/make_colab_notebook.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "notebooks", "colab_c1_full_coin.ipynb")


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": src.splitlines(keepends=True)}


CELLS = [
    md("""# LiveJEPA — C1 middle lane (Colab + Google Drive, auto-saving)

Extracts COIN features starting from the **middle** of the video list (Kaggle works
the front, the institute machine works the back). Progress is tarred and copied to
**your Google Drive automatically** at the end of the run — no manual saving.

**Per session:** Runtime → Change runtime type → **T4 GPU** → Run all → approve the
Drive permission popup → walk away. When YouTube throttles the session, it saves
itself to Drive and finishes. That's it.

**One-time setup:** upload `livejepa_kaggle.zip` to `MyDrive/LiveJEPA/` on Drive."""),

    code("""# --- 1. Mount Drive + get the repo ---
import glob, os, zipfile
from google.colab import drive
drive.mount('/content/drive')
DRV = '/content/drive/MyDrive/LiveJEPA'
os.makedirs(DRV + '/caches', exist_ok=True)
zips = sorted(glob.glob(DRV + '/livejepa_kaggle*.zip'))
assert zips, 'Upload livejepa_kaggle.zip to MyDrive/LiveJEPA/ first!'
DEST = '/content/repo'
if not os.path.exists(DEST + '/configs/default.yaml'):
    with zipfile.ZipFile(zips[-1]) as z:
        z.extractall(DEST)
os.chdir(DEST)
print('repo ready:', os.getcwd(), '| zip:', os.path.basename(zips[-1]))"""),

    code("""# --- 2. Dependencies (torch preinstalled on Colab GPU runtimes) ---
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

    code("""# --- 4. COIN.json ---
import os, urllib.request
os.makedirs('eval_data', exist_ok=True)
if not os.path.exists('eval_data/COIN.json'):
    from livejepa.data.coin import COIN_ANNOTATIONS_URL
    urllib.request.urlretrieve(COIN_ANNOTATIONS_URL, 'eval_data/COIN.json')
print('COIN.json ready; frozen uids:',
      sum(1 for _ in open('eval_data/frozen_val_uids.txt')))"""),

    code("""# --- 5. Resume from Drive (newest colab tar, if any) ---
import glob, json, os, subprocess
DRV = '/content/drive/MyDrive/LiveJEPA'
tars = sorted(glob.glob(DRV + '/caches/coin_cache_colab_p*.tar'),
              key=lambda p: int(''.join(filter(str.isdigit, os.path.basename(p))) or 0))
if tars:
    print('resuming from', tars[-1])
    subprocess.run(['tar', '-xf', tars[-1], '-C', '/content'], check=True)
os.makedirs('/content/data_cache_coin_full', exist_ok=True)
s = '/content/data_cache_coin_full/pipeline_state.json'
if os.path.exists(s):
    st = json.load(open(s))
    print(f\"resume state: done={len(st['done'])} dead={len(st['dead'])}\")
print('clips in place:', len(glob.glob('/content/data_cache_coin_full/*.npz')))"""),

    code("""# --- 6. EXTRACT (middle lane) + AUTO-SAVE to Drive — fully unattended ---
import glob, os, re, shutil, subprocess
r = subprocess.run(['python', 'scripts/coin_full_pipeline.py',
    '--config', 'configs/colab.yaml', '--eval-root', 'eval_data',
    '--train-dir', '/content/data_cache_coin_full',
    '--val-dir', '/content/data_cache_coin_full_val',
    '--frozen-val-uids', 'eval_data/frozen_val_uids.txt',
    '--chunk', '250', '--max-tokens', '256', '--sleep', '2',
    '--start-frac', '0.5'])
print('pipeline exit code:', r.returncode)

# auto-save: cumulative tar -> Drive, numbered from what's already there
DRV = '/content/drive/MyDrive/LiveJEPA'
prior = [int(m.group(1)) for p in glob.glob(DRV + '/caches/coin_cache_colab_p*.tar')
         if (m := re.search(r'p(\\d+)\\.tar$', p))]
N = max(prior, default=0) + 1
tar = f'/content/coin_cache_colab_p{N}.tar'
subprocess.run(['tar', '-cf', tar, '-C', '/content',
                'data_cache_coin_full', 'data_cache_coin_full_val'], check=True)
shutil.copy(tar, DRV + '/caches/')
gb = os.path.getsize(tar) / 1e9
print(f'SAVED TO DRIVE: caches/coin_cache_colab_p{N}.tar ({gb:.2f} GB) — session done, '
      'you can close this tab.')"""),

    md("""## Notes
- Each run resumes automatically from the newest Drive tar (cell 5) and re-saves a
  bigger cumulative tar (cell 6) — attach nothing, click nothing.
- If Colab disconnects mid-run, the un-tarred progress of that session is lost, but
  everything up to the previous Drive tar is safe; just Run all again.
- This lane never trains — training happens once, at the end, when all lanes have
  covered the full list. The lane tars merge on the institute machine."""),
]

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3",
                                  "language": "python"},
                   "accelerator": "GPU"},
      "cells": CELLS}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(nb, open(OUT, "w", encoding="utf-8"), indent=1)
print("wrote", OUT)
