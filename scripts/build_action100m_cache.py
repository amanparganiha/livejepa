"""Build the Action100M feature cache from downloaded videos + segments manifest.

Caches (V-JEPA 2 tokens, SONAR target) per usable leaf segment, exactly like
`build_coin_cache.py` does for COIN steps. Split is VIDEO-LEVEL and deterministic
(`action100m.is_val_video`: sha1(uid) % 32 == 0 -> val), so it is stable across
machines and runs; the chosen val uids are also written to <val-dir>/VAL_UIDS.txt
for the record.

Resume-friendly (skips cached .npz). Run from repo root:
    python scripts/build_action100m_cache.py \
        --manifest eval_data/a100m_videos/a100m_segments.json \
        --videos-dir eval_data/a100m_videos
"""
import argparse
import json
import os
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.coin import sample_step_frames
from livejepa.data.cache import cache_sample
from livejepa.data.action100m import is_val_video
from livejepa.encoders.vision import VisionEncoder
from livejepa.encoders.sonar import SonarSpace

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="configs/default.yaml")
ap.add_argument("--manifest", default="eval_data/a100m_videos/a100m_segments.json")
ap.add_argument("--videos-dir", default="eval_data/a100m_videos")
ap.add_argument("--train-dir", default="data_cache_a100m")
ap.add_argument("--val-dir", default="data_cache_a100m_val")
ap.add_argument("--max-segments-per-video", type=int, default=40)
ap.add_argument("--max-tokens", type=int, default=256,
                help="subsample tokens at cache time (matches train.collate; 0=keep all)")
args = ap.parse_args()

cfg = yaml.safe_load(open(args.config))
cfg["project"]["use_stubs"] = False
K = cfg["encoders"]["vision"]["frames_per_window"]
res = cfg["encoders"]["vision"]["resolution"]

manifest = json.load(open(args.manifest))
have = {v: os.path.join(args.videos_dir, f"{v}.mp4") for v in manifest
        if os.path.exists(os.path.join(args.videos_dir, f"{v}.mp4"))}
val_uids = sorted(v for v in have if is_val_video(v))
train_uids = sorted(v for v in have if v not in set(val_uids))
print(f"videos on disk: {len(have)} -> train {len(train_uids)} | val {len(val_uids)}",
      flush=True)
os.makedirs(args.val_dir, exist_ok=True)
with open(os.path.join(args.val_dir, "VAL_UIDS.txt"), "w") as f:
    f.write("\n".join(val_uids))

vision = VisionEncoder(cfg)
sonar = SonarSpace(cfg)


def build(uids, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    n, t0 = 0, time.time()
    for vid in uids:
        for j, seg in enumerate(manifest[vid]):
            if j >= args.max_segments_per_video:
                break
            s, e, caption = seg[0], seg[1], seg[2]
            sid = f"a100m_{vid}_{j:03d}"
            if os.path.exists(os.path.join(out_dir, sid + ".npz")):
                n += 1
                continue
            frames = sample_step_frames(have[vid], s, e, K, res)
            if frames is None:
                continue
            tokens = vision.encode_window(frames)
            target = sonar.encode([caption])[0]
            cache_sample(out_dir, sid, tokens, target, caption,
                         max_tokens=args.max_tokens)
            n += 1
            if n % 20 == 0:
                print(f"  {out_dir}: {n} cached ({(time.time()-t0)/n:.1f}s/clip)",
                      flush=True)
    print(f"DONE {out_dir}: {n} samples in {time.time()-t0:.0f}s", flush=True)


build(train_uids, args.train_dir)
build(val_uids, args.val_dir)
print("ALL DONE", flush=True)
