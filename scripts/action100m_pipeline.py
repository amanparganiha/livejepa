"""Chunked Action100M feature-cache pipeline (rung C2), for small pod disks.

Action100M-preview video is far larger than a rented pod's disk, so this driver
loops:  download a chunk of videos -> extract leaf-segment features -> DELETE the
videos. It fuses the SAME proven throttle handling as the COIN pipeline (fatal-vs-
transient classification + a consecutive-failure breaker that stops cleanly with
progress saved) so a YouTube-throttled pod ends tidily and resumes later.

Pairs with the "pod trains, home gates" design: run this on the rented 4090 to
build data_cache_a100m{,_val}, train, then bring the checkpoint home to gate on
the fixed vals.

  python scripts/action100m_pipeline.py --config configs/default.yaml \
      --shards 8 --max-videos 4000 --chunk 200 --sleep 1

Everything is resumable (cached .npz + a done/dead state file). Video order is
densest-supervision-first, so any prefix of an interrupted run is still the
highest-value slice. Val split is deterministic and video-level
(action100m.is_val_video: sha1(uid) % 32 == 0), stable across machines/runs.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.coin import sample_step_frames
from livejepa.data.cache import cache_sample
from livejepa.data.action100m import (PARQUET_URL, N_SHARDS, load_segments,
                                      is_val_video)

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="configs/default.yaml")
ap.add_argument("--parquet-dir", default="eval_data/action100m")
ap.add_argument("--shards", type=int, default=8,
                help="annotation parquet shards to fetch (28 = full preview)")
ap.add_argument("--train-dir", default="data_cache_a100m")
ap.add_argument("--val-dir", default="data_cache_a100m_val")
ap.add_argument("--stage-dir", default="eval_data/a100m_chunk",
                help="scratch dir where videos are staged then deleted")
ap.add_argument("--chunk", type=int, default=200,
                help="videos per download-extract-delete cycle")
ap.add_argument("--max-videos", type=int, default=0, help="0 = all ranked videos")
ap.add_argument("--min-segments", type=int, default=3,
                help="skip videos with fewer usable leaf segments than this")
ap.add_argument("--min-dur", type=float, default=3.0)
ap.add_argument("--max-dur", type=float, default=60.0)
ap.add_argument("--max-segments-per-video", type=int, default=40)
ap.add_argument("--max-tokens", type=int, default=256)
ap.add_argument("--state-file", default=None,
                help="json of dead/done uids (default <train-dir>/pipeline_state.json)")
ap.add_argument("--sleep", type=float, default=1.0,
                help="seconds between downloads (YouTube rate-limit relief)")
ap.add_argument("--retry-dead", action="store_true",
                help="clear the inherited dead list (use once after a throttled run)")
ap.add_argument("--keep-videos", action="store_true", help="skip deletion (debugging)")
args = ap.parse_args()

cfg = yaml.safe_load(open(args.config))
cfg["project"]["use_stubs"] = False
K = cfg["encoders"]["vision"]["frames_per_window"]
res = cfg["encoders"]["vision"]["resolution"]


def fetch_shards(parquet_dir, n):
    os.makedirs(parquet_dir, exist_ok=True)
    for i in range(min(n, N_SHARDS)):
        dest = os.path.join(parquet_dir, f"part-{i:05d}.parquet")
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        print(f"fetching shard {i}: {PARQUET_URL.format(i)}", flush=True)
        tmp = dest + ".part"
        urllib.request.urlretrieve(PARQUET_URL.format(i), tmp)
        os.replace(tmp, dest)


fetch_shards(args.parquet_dir, args.shards)
print("parsing segments...", flush=True)
segs = load_segments(args.parquet_dir, args.min_dur, args.max_dur)
# densest-supervision-first, uid tiebreak for determinism
ranked = sorted(((v, s) for v, s in segs.items() if len(s) >= args.min_segments),
                key=lambda kv: (-len(kv[1]), kv[0]))
order = [v for v, _ in ranked]
seg_of = dict(ranked)
if args.max_videos:
    order = order[: args.max_videos]
n_seg_target = sum(len(seg_of[v]) for v in order)
print(f"pipeline target: {len(order)} videos, {n_seg_target} segments, "
      f"chunk={args.chunk}", flush=True)

state_path = args.state_file or os.path.join(args.train_dir, "pipeline_state.json")
os.makedirs(args.train_dir, exist_ok=True)
os.makedirs(args.val_dir, exist_ok=True)
state = json.load(open(state_path)) if os.path.exists(state_path) else {"dead": [], "done": []}
dead, done = set(state["dead"]), set(state["done"])
if args.retry_dead and dead:
    print(f"--retry-dead: clearing {len(dead)} dead marks", flush=True)
    dead = set()

# record the frozen val uids for this run
val_now = sorted(v for v in order if is_val_video(v))
with open(os.path.join(args.val_dir, "VAL_UIDS.txt"), "w") as f:
    f.write("\n".join(val_now))
print(f"deterministic val: {len(val_now)} videos (sha1 %% 32 == 0)", flush=True)

os.makedirs(args.stage_dir, exist_ok=True)

print("loading encoders once...", flush=True)
from livejepa.encoders.vision import VisionEncoder
from livejepa.encoders.sonar import SonarSpace
vision = VisionEncoder(cfg)
sonar = SonarSpace(cfg)

todo = [v for v in order if v not in dead and v not in done]
print(f"remaining after resume: {len(todo)}", flush=True)
n_cached_total = 0
t_start = time.time()

# Only these yt-dlp errors mean the video is truly gone; anything else (429s,
# "Sign in to confirm you're not a bot", timeouts) is TRANSIENT throttling.
FATAL_MARKERS = ("Video unavailable", "Private video", "has been removed",
                 "no longer available", "account associated with this video",
                 "This video is not available")
BREAKER_LIMIT = 15
throttled = False

for c0 in range(0, len(todo), args.chunk):
    chunk = todo[c0 : c0 + args.chunk]
    print(f"\n=== chunk {c0 // args.chunk + 1}: {len(chunk)} videos ===", flush=True)
    # 1) download
    streak = 0
    for vid in chunk:
        out = os.path.join(args.stage_dir, f"{vid}.mp4")
        if os.path.exists(out):
            continue
        r = subprocess.run(
            ["yt-dlp", "-f",
             "bv*[height<=360][vcodec!*=av01]+ba/b[height<=360][vcodec!*=av01]"
             "/bv*[height<=360]+ba/b[height<=360]/b",
             "--merge-output-format", "mp4", "-o", out, "--no-playlist",
             f"https://www.youtube.com/watch?v={vid}"],
            capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out):
            streak = 0
        else:
            err = (r.stderr or "") + (r.stdout or "")
            if any(m in err for m in FATAL_MARKERS):
                dead.add(vid)
                streak = 0
            else:
                streak += 1
                if streak >= BREAKER_LIMIT:
                    print(f"!! {streak} consecutive transient download failures — "
                          "YouTube is throttling this IP. Extracting what we have, "
                          "saving state, and stopping. Resume later.", flush=True)
                    print("last yt-dlp error:", err.strip().splitlines()[-1][:200]
                          if err.strip() else "(empty)", flush=True)
                    throttled = True
                    break
        if args.sleep:
            time.sleep(args.sleep)
    # 2) extract
    for vid in chunk:
        path = os.path.join(args.stage_dir, f"{vid}.mp4")
        if not os.path.exists(path):
            continue
        out_dir = args.val_dir if is_val_video(vid) else args.train_dir
        for j, seg in enumerate(seg_of[vid]):
            if j >= args.max_segments_per_video:
                break
            s, e, caption = seg[0], seg[1], seg[2]
            sid = f"a100m_{vid}_{j:03d}"
            if os.path.exists(os.path.join(out_dir, sid + ".npz")):
                continue
            frames = sample_step_frames(path, s, e, K, res)
            if frames is None:
                continue
            tokens = vision.encode_window(frames)
            target = sonar.encode([caption])[0]
            cache_sample(out_dir, sid, tokens, target, caption,
                         max_tokens=args.max_tokens)
            n_cached_total += 1
            if n_cached_total % 25 == 0:
                rate = (time.time() - t_start) / max(1, n_cached_total)
                print(f"  cached {n_cached_total} this run ({rate:.1f}s/clip)", flush=True)
        done.add(vid)
        # 3) delete as we go (keeps the stage dir small even mid-chunk)
        if not args.keep_videos:
            try:
                os.remove(path)
            except OSError:
                pass
    json.dump({"dead": sorted(dead), "done": sorted(done)}, open(state_path, "w"))
    print(f"chunk done. total done={len(done)} dead={len(dead)}", flush=True)
    if throttled:
        break

status = "STOPPED (YouTube throttled — progress saved, resume later)" if throttled \
         else "ALL DONE"
print(f"\n{status}: {len(done)} videos processed, {len(dead)} dead links, "
      f"{n_cached_total} new clips this run -> {args.train_dir}", flush=True)
