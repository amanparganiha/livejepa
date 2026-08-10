"""Build a diverse, leakage-free COIN feature cache from downloaded videos.

Caches (V-JEPA 2 tokens, SONAR target) per annotated step. Splits videos by
class: for each class with >=2 downloaded videos, the last is held out for val,
so every val class is also seen in training (no unseen-class leakage), and no
video appears in both splits.

Resume-friendly: skips steps already cached. Run from repo root:
    python scripts/build_coin_cache.py
"""
import os, sys, glob, time, argparse
from collections import defaultdict
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.coin import load_annotations, sample_step_frames
from livejepa.data.cache import cache_sample
from livejepa.encoders.vision import VisionEncoder
from livejepa.encoders.sonar import SonarSpace

_ap = argparse.ArgumentParser(description="Build a leakage-free COIN feature cache.")
_ap.add_argument("--config", default="configs/default.yaml")
_ap.add_argument("--train-dir", default="data_cache_coin2")
_ap.add_argument("--val-dir", default="data_cache_coin2_val")
_ap.add_argument("--max-steps-per-video", type=int, default=20,
                 help="cap steps/video to bound caching time (0 = no cap)")
_ap.add_argument("--eval-root", default=None,
                 help="dir with COIN.json + coin_videos/ (overrides eval.data_root, e.g. /kaggle/working)")
_ap.add_argument("--exclude-uids-dir", default=None,
                 help="dir of an EXISTING val cache (e.g. data_cache_coin2_val): its video "
                      "uids are forced into val, never train — keeps the frozen benchmark "
                      "leak-free when scaling the download pool")
_ap.add_argument("--max-tokens", type=int, default=256,
                 help="subsample tokens at cache time (matches train.collate; 0=keep all)")
_args = _ap.parse_args()
TRAIN_DIR, VAL_DIR = _args.train_dir, _args.val_dir
MAX_STEPS_PER_VIDEO = _args.max_steps_per_video or 10**9

cfg = yaml.safe_load(open(_args.config))
cfg["project"]["use_stubs"] = False
if _args.eval_root:
    cfg["eval"]["data_root"] = _args.eval_root
root = cfg["eval"]["data_root"]
vdir = os.path.join(root, "coin_videos")
ann = load_annotations(os.path.join(root, "COIN.json"))

exts = (".mp4", ".mkv", ".webm")
by_id = {}
# Prefer .mp4: OpenCV's per-frame seek (cap.set(POS_FRAMES)) hangs on many .webm
# (VP9) files, which pegs the CPU with zero progress during caching.
for p in sorted(glob.glob(os.path.join(vdir, "*")),
                key=lambda x: (os.path.splitext(x)[1].lower() != ".mp4", x)):
    vid = os.path.splitext(os.path.basename(p))[0].split(".")[0]
    if os.path.splitext(p)[1] in exts and vid in ann and ann[vid]["steps"]:
        by_id.setdefault(vid, p)
dropped = [v for v, p in by_id.items() if p.lower().endswith(".webm")]
by_id = {v: p for v, p in by_id.items() if not p.lower().endswith(".webm")}
if dropped:
    print(f"skipping {len(dropped)} webm-only videos (seek hangs): {dropped}", flush=True)

by_class = defaultdict(list)
for vid in sorted(by_id):
    by_class[ann[vid]["class"]].append(vid)
val_uids = {vids[-1] for vids in by_class.values() if len(vids) >= 2}

if _args.exclude_uids_dir:
    # uids of the frozen benchmark: cache files are named coin_<vid>_<j>.npz
    frozen = set()
    for p in glob.glob(os.path.join(_args.exclude_uids_dir, "coin_*.npz")):
        stem = os.path.basename(p)[len("coin_"):-len(".npz")]
        frozen.add(stem.rsplit("_", 1)[0])
    overlap = frozen & set(by_id)
    val_uids |= overlap
    print(f"exclude-uids-dir: {len(frozen)} frozen-benchmark videos, "
          f"{len(overlap)} present in this pool -> forced into val", flush=True)

train_uids = [v for v in sorted(by_id) if v not in val_uids]
assert not (set(train_uids) & val_uids), "split leak: train/val overlap"
if not val_uids:
    print("WARNING: no downloaded class has >=2 videos -> val split is EMPTY "
          "(eval will have nothing held out). Download more videos per class.", flush=True)

print("classes:", {c: len(v) for c, v in sorted(by_class.items())}, flush=True)
print(f"train videos: {len(train_uids)} | val videos: {len(val_uids)} -> {sorted(val_uids)}",
      flush=True)
print(f"train steps: {sum(len(ann[v]['steps']) for v in train_uids)} | "
      f"val steps: {sum(len(ann[v]['steps']) for v in val_uids)}", flush=True)

K = cfg["encoders"]["vision"]["frames_per_window"]
res = cfg["encoders"]["vision"]["resolution"]
vision = VisionEncoder(cfg)
sonar = SonarSpace(cfg)


def build(uids, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    n, t0 = 0, time.time()
    for vid in uids:
        path = by_id[vid]
        for j, (s, e, label) in enumerate(ann[vid]["steps"]):
            if j >= MAX_STEPS_PER_VIDEO:
                break
            sid = f"coin_{vid}_{j:03d}"
            if os.path.exists(os.path.join(out_dir, sid + ".npz")):
                n += 1
                continue
            frames = sample_step_frames(path, s, e, K, res)
            if frames is None:
                continue
            tokens = vision.encode_window(frames)
            target = sonar.encode([label])[0]
            cache_sample(out_dir, sid, tokens, target, label,
                         max_tokens=_args.max_tokens)
            n += 1
            if n % 20 == 0:
                print(f"  {out_dir}: {n} cached ({(time.time()-t0)/n:.1f}s/clip)", flush=True)
    print(f"DONE {out_dir}: {n} samples in {time.time()-t0:.0f}s", flush=True)


build(train_uids, TRAIN_DIR)
build(val_uids, VAL_DIR)
print("ALL DONE", flush=True)
