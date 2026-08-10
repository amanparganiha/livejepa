"""Build an EgoExo4D training cache: (V-JEPA 2 window tokens -> SONAR caption).

WHY (rung D.4, 2026-07-28). The D.3 predictor-mode eval on EgoExo was
uninterpretable: our COIN-trained predictor speaks imperative step labels
("remove the chain") while EgoExo annotates in a descriptive egocentric template
("the camera wearer takes a tire lever from the table with his right hand").
CIDEr floored at ~0.012 despite semantically correct predictions, and the
style-robust semantic metric had almost no temporal sensitivity. Root cause: no
in-domain predictor. This script builds the data to train one.

Windowing MATCHES INFERENCE EXACTLY (livejepa.run_eval.build_predictor_stream):
frames are read at eval fps, and each sample is the K-frame window CENTERED on
the annotation timestamp — so a predictor trained here sees at training time
exactly what it will see at eval time.

Leakage control: takes listed in --exclude-uids (the D.3 predictor-mode eval set)
are never cached. A disjoint slice of the remaining takes is held out as val.

Resumable: existing .npz are skipped, so it can run across several nights.

    python scripts/build_egoexo_cache.py --max-per-take 20 --max-samples 12000
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.cache import cache_sample
from livejepa.data.egoexo import load_atomic_descriptions, load_takes, _find_take_video
from livejepa.run_eval import read_frames_at_fps

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="configs/default.yaml")
ap.add_argument("--root", default="eval_data/egoexo")
ap.add_argument("--train-dir", default="data_cache_egoexo")
ap.add_argument("--val-dir", default="data_cache_egoexo_val")
ap.add_argument("--exclude-uids", default="eval_data/egoexo_takes_pred40.txt",
                help="never cache these takes (they are the predictor-mode eval set)")
ap.add_argument("--val-takes", type=int, default=25,
                help="takes held out for gating (disjoint from train and excluded)")
ap.add_argument("--max-per-take", type=int, default=20,
                help="annotations sampled per take (evenly spread over the take)")
ap.add_argument("--max-samples", type=int, default=12000)
ap.add_argument("--max-seconds", type=float, default=360.0)
ap.add_argument("--max-tokens", type=int, default=256)
ap.add_argument("--state-file", default=None)
args = ap.parse_args()

cfg = yaml.safe_load(open(args.config))
cfg["project"]["use_stubs"] = False
K = cfg["encoders"]["vision"]["frames_per_window"]
res = cfg["encoders"]["vision"]["resolution"]
fps = cfg["eval"]["fps"]

gt = load_atomic_descriptions(args.root, split="val")
takes = load_takes(args.root)
excluded = set()
if args.exclude_uids and os.path.exists(args.exclude_uids):
    excluded = {l.strip() for l in open(args.exclude_uids) if l.strip()}
print(f"annotated takes: {len(gt)} | excluded (eval set): {len(excluded)}", flush=True)

usable = sorted(u for u in gt
                if u not in excluded and takes.get(u)
                and _find_take_video(args.root, takes[u]))
val_uids = set(usable[::max(1, len(usable) // args.val_takes)][:args.val_takes])
train_uids = [u for u in usable if u not in val_uids]
print(f"usable takes: {len(usable)} -> train {len(train_uids)} | val {len(val_uids)}",
      flush=True)

os.makedirs(args.train_dir, exist_ok=True)
os.makedirs(args.val_dir, exist_ok=True)
with open(os.path.join(args.val_dir, "VAL_UIDS.txt"), "w", newline="\n") as f:
    f.write("\n".join(sorted(val_uids)))

state_path = args.state_file or os.path.join(args.train_dir, "pipeline_state.json")
state = json.load(open(state_path)) if os.path.exists(state_path) else {"done": []}
done = set(state["done"])

print("loading encoders once...", flush=True)
from livejepa.encoders.vision import VisionEncoder
from livejepa.encoders.sonar import SonarSpace
vision = VisionEncoder(cfg)
sonar = SonarSpace(cfg)

order = [u for u in (sorted(val_uids) + train_uids) if u not in done]
n_total, t0 = 0, time.time()

for ti, uid in enumerate(order, 1):
    if n_total >= args.max_samples:
        print("reached --max-samples", flush=True)
        break
    out_dir = args.val_dir if uid in val_uids else args.train_dir
    path = _find_take_video(args.root, takes[uid])
    events = [(t, y) for t, y in gt[uid] if t <= args.max_seconds]
    if not events or not path:
        done.add(uid)
        continue
    # evenly spread the sampled annotations across the take
    if len(events) > args.max_per_take:
        pick = np.linspace(0, len(events) - 1, args.max_per_take).astype(int)
        events = [events[i] for i in sorted(set(pick))]
    # skip the (expensive) video read if every sample for this take exists
    if all(os.path.exists(os.path.join(out_dir, f"ego_{uid}_{j:03d}.npz"))
           for j in range(len(events))):
        done.add(uid)
        continue
    frames, ftimes = read_frames_at_fps(path, fps, args.max_seconds, res)
    if frames is None or len(frames) < K:
        done.add(uid)
        continue
    ftimes = np.asarray(ftimes, dtype=np.float32)
    n_take = 0
    for j, (t, caption) in enumerate(events):
        sid = f"ego_{uid}_{j:03d}"
        if os.path.exists(os.path.join(out_dir, sid + ".npz")):
            continue
        c = int(np.argmin(np.abs(ftimes - t)))          # window CENTERED on t
        s = max(0, min(c - K // 2, len(frames) - K))
        window = frames[s:s + K]
        if len(window) < K:
            continue
        tokens = vision.encode_window(window)
        target = sonar.encode([caption])[0]
        cache_sample(out_dir, sid, tokens, target, caption, max_tokens=args.max_tokens)
        n_take += 1
        n_total += 1
    done.add(uid)
    json.dump({"done": sorted(done)}, open(state_path, "w"))
    rate = (time.time() - t0) / max(1, n_total)
    print(f"[{ti}/{len(order)}] {uid[:8]} +{n_take} samples "
          f"(total {n_total}, {rate:.1f}s/sample)", flush=True)

print(f"\nDONE: {n_total} new samples this run -> {args.train_dir} / {args.val_dir}",
      flush=True)
