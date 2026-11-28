"""Measure SONAR decode throughput on this GPU with ONLY the decoder loaded.

Inputs mimic pooled segment means: averages of 2-4 real annotation embeddings
from eval_data/gt_emb_cache.npz. Nothing is written to any decode cache.
"""
import os
import sys
import time

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.encoders.sonar import SonarSpace  # noqa: E402

cfg = yaml.safe_load(open("configs/default.yaml"))
cfg["project"]["use_stubs"] = False
z = np.load("eval_data/gt_emb_cache.npz", allow_pickle=True)
embs = z["embs"].astype(np.float32)
rng = np.random.default_rng(0)
batch = np.stack([embs[rng.integers(0, len(embs), size=rng.integers(2, 5))].mean(0)
                  for _ in range(128)])
sonar = SonarSpace(cfg)
sonar._hf_decode(batch[:4])                      # load + warm up
for chunk in (16, 32):
    t = time.time()
    out = sonar._hf_decode(batch[:96], chunk=chunk)
    dt = time.time() - t
    print(f"chunk={chunk}: {len(out)} decodes in {dt:.1f}s -> {len(out) / dt:.2f} decodes/s",
          flush=True)
print("example:", out[0])
