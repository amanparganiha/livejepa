"""Decode throughput on REAL pooled embeddings (adaptive + uniform_pool at 0.2 Hz on
three faithful-benchmark takes), with the encoder freed first, as --cider full does."""
import sys, os, time
import numpy as np, yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.run_eval import build_gt_stream, select_points
from livejepa.data.egoexo import load_atomic_descriptions
from livejepa.encoders.sonar import SonarSpace
cfg = yaml.safe_load(open("configs/default.yaml")); cfg["project"]["use_stubs"] = False
fps, sel = cfg["eval"]["fps"], cfg["selective"]
gt = load_atomic_descriptions("eval_data/egoexo", "val", passes="first")
uids = [l.strip() for l in open("eval_data/egoexo_takes_proc219.txt") if l.strip()]
sonar = SonarSpace(cfg)
embs = []
for u in uids[:3]:
    stream, _ = build_gt_stream(gt[u], fps, sonar, max_seconds=None)
    for m in ("adaptive", "uniform_pool"):
        embs.append(select_points(m, stream, 0.2, fps, sel)[1])
embs = np.concatenate(embs)
import torch
sonar._encoder = None; torch.cuda.empty_cache()
sonar._hf_decode(embs[:4])                      # load decoder + warm up
n = min(64, len(embs) - 4)
t = time.time(); out = sonar._hf_decode(embs[4:4 + n], chunk=16); dt = time.time() - t
print(f"{len(out)} real pooled decodes in {dt:.1f}s -> {len(out) / dt:.2f} decodes/s", flush=True)
for s in out[:3]:
    print("  e.g.", s)
