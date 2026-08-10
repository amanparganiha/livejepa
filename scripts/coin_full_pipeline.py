"""Full-COIN feature-cache pipeline, chunked for small disks (rung C1).

Kaggle's working disk is ~20 GB but full-COIN video is ~100+ GB, so this driver
loops:  download a chunk of videos -> extract features -> DELETE the videos.
Models load once; everything is resumable (cached .npz + a state file of dead
links). The split is decided UP-FRONT from the annotation list, not from what
is on disk:

  - videos in --frozen-val-uids are NEVER cached here (they are the frozen
    1,118-sample benchmark, data_cache_coin2_val — evaluation-only),
  - everything else goes to TRAIN.

Video order is class round-robin, so any prefix of the run is class-diverse —
an interrupted run still yields balanced data.

    python scripts/coin_full_pipeline.py --config configs/colab.yaml \
        --eval-root eval_data --train-dir data_cache_coin_full \
        --frozen-val-uids eval_data/frozen_val_uids.txt --chunk 300
"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.coin import load_annotations, sample_step_frames
from livejepa.data.cache import cache_sample

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="configs/default.yaml")
ap.add_argument("--eval-root", default="eval_data",
                help="dir containing COIN.json; videos are staged in <eval-root>/coin_chunk")
ap.add_argument("--train-dir", default="data_cache_coin_full")
ap.add_argument("--val-dir", default="data_cache_coin_full_val")
ap.add_argument("--val-one-in", type=int, default=24,
                help="deterministic video-level val split: sha1(uid) %% N == 0 -> val "
                     "(0 disables; use when a saved benchmark val already exists)")
ap.add_argument("--frozen-val-uids", default="eval_data/frozen_val_uids.txt",
                help="one uid/line; these videos are skipped entirely (benchmark-only)")
ap.add_argument("--chunk", type=int, default=300, help="videos per download-extract-delete cycle")
ap.add_argument("--max-videos", type=int, default=0, help="0 = all training videos with steps")
ap.add_argument("--max-steps-per-video", type=int, default=20)
ap.add_argument("--max-tokens", type=int, default=256)
ap.add_argument("--state-file", default=None,
                help="json of dead/done uids (default <train-dir>/pipeline_state.json)")
ap.add_argument("--resume-dirs", default="",
                help="comma-separated read-only cache dirs from PRIOR sessions "
                     "(Kaggle datasets); their samples are treated as already cached")
ap.add_argument("--sleep", type=float, default=2.0,
                help="seconds between downloads (YouTube rate-limit relief)")
ap.add_argument("--retry-dead", action="store_true",
                help="clear the inherited dead list (use once after a session that "
                     "was throttled — real dead links get re-marked cheaply)")
ap.add_argument("--reverse", action="store_true",
                help="process the video list back-to-front (parallel second lane that "
                     "cannot collide with a front-to-back lane on another machine)")
ap.add_argument("--start-frac", type=float, default=0.0,
                help="rotate the video list to start at this fraction (e.g. 0.5 = "
                     "middle) — a third parallel lane between a front lane (0.0) and "
                     "a reverse lane; duplicate work only after lanes cross, and "
                     "duplicate sample-ids merge harmlessly")
ap.add_argument("--keep-videos", action="store_true", help="skip deletion (debugging)")
args = ap.parse_args()

cfg = yaml.safe_load(open(args.config))
cfg["project"]["use_stubs"] = False
K = cfg["encoders"]["vision"]["frames_per_window"]
res = cfg["encoders"]["vision"]["resolution"]

ann = load_annotations(os.path.join(args.eval_root, "COIN.json"))
frozen = set()
if os.path.exists(args.frozen_val_uids):
    frozen = {l.strip() for l in open(args.frozen_val_uids) if l.strip()}
    print(f"frozen benchmark uids (never cached here): {len(frozen)}", flush=True)

# class round-robin ordering over all training videos with steps
by_class = defaultdict(list)
for vid, m in ann.items():
    if m["subset"] == "training" and m["steps"] and vid not in frozen:
        by_class[m["class"]].append(vid)
for c in by_class:
    by_class[c].sort(key=lambda v: len(ann[v]["steps"]), reverse=True)
order = []
while any(by_class.values()):
    for c in sorted(by_class):
        if by_class[c]:
            order.append(by_class[c].pop(0))
if args.reverse:
    # second extraction lane: walk the SAME deterministic list from the back so a
    # front-walking lane (Kaggle) and this one never touch the same videos until
    # they meet in the middle (dup sample-ids merge harmlessly anyway)
    order.reverse()
if args.start_frac:
    k = int(len(order) * args.start_frac) % max(1, len(order))
    order = order[k:] + order[:k]
if args.max_videos:
    order = order[: args.max_videos]
lane = " (REVERSE lane)" if args.reverse else (
    f" (lane from {args.start_frac:.0%})" if args.start_frac else "")
print(f"pipeline target: {len(order)} videos, chunk={args.chunk}{lane}", flush=True)

state_path = args.state_file or os.path.join(args.train_dir, "pipeline_state.json")
os.makedirs(args.train_dir, exist_ok=True)
state = json.load(open(state_path)) if os.path.exists(state_path) else {"dead": [], "done": []}
dead, done = set(state["dead"]), set(state["done"])
resume_dirs = [d for d in args.resume_dirs.split(",") if d]
for d in resume_dirs:                      # merge state from prior sessions
    prior = os.path.join(d, "pipeline_state.json")
    if os.path.exists(prior):
        p = json.load(open(prior))
        dead |= set(p.get("dead", []))
        done |= set(p.get("done", []))
if resume_dirs:
    print(f"resume dirs: {resume_dirs} -> done={len(done)} dead={len(dead)}", flush=True)
if args.retry_dead and dead:
    print(f"--retry-dead: clearing {len(dead)} dead marks (throttled-session repair)",
          flush=True)
    dead = set()

stage_dir = os.path.join(args.eval_root, "coin_chunk")
os.makedirs(stage_dir, exist_ok=True)

def _is_val(vid):
    import hashlib
    if not args.val_one_in:
        return False
    return int(hashlib.sha1(vid.encode()).hexdigest(), 16) % args.val_one_in == 0


if args.val_one_in:
    os.makedirs(args.val_dir, exist_ok=True)
    val_now = sorted(v for v in order if _is_val(v))
    with open(os.path.join(args.val_dir, "VAL_UIDS.txt"), "w") as f:
        f.write("\n".join(val_now))
    print(f"fresh deterministic val: {len(val_now)} videos (1/{args.val_one_in})", flush=True)

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
# "Sign in to confirm you're not a bot", timeouts) is TRANSIENT throttling — the
# video must stay retryable, and a streak of transient failures means YouTube has
# blocked this IP for now, so stop cleanly instead of blacklisting the whole list.
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
        out = os.path.join(stage_dir, f"{vid}.mp4")
        if os.path.exists(out):
            continue
        r = subprocess.run(
            ["yt-dlp", "-f",
             # avoid AV1 (Kaggle's OpenCV/ffmpeg can't decode it -> clips skipped)
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
                dead.add(vid)                     # genuinely gone
                streak = 0
            else:
                streak += 1                       # transient: NOT dead, retry later
                if streak >= BREAKER_LIMIT:
                    print(f"!! {streak} consecutive transient download failures — "
                          "YouTube is throttling this IP. Extracting what we have, "
                          "saving state, and stopping. Resume in a later session.",
                          flush=True)
                    print("last yt-dlp error:", err.strip().splitlines()[-1][:200]
                          if err.strip() else "(empty)", flush=True)
                    throttled = True
                    break
        if args.sleep:
            time.sleep(args.sleep)
    # 2) extract
    for vid in chunk:
        path = os.path.join(stage_dir, f"{vid}.mp4")
        if not os.path.exists(path):
            continue
        out_dir = args.val_dir if _is_val(vid) else args.train_dir
        n_video = 0
        for j, (s, e, label) in enumerate(ann[vid]["steps"]):
            if j >= args.max_steps_per_video:
                break
            sid = f"coin_{vid}_{j:03d}"
            if any(os.path.exists(os.path.join(d, sid + ".npz"))
                   for d in [out_dir] + resume_dirs):
                n_video += 1
                continue
            frames = sample_step_frames(path, s, e, K, res)
            if frames is None:
                continue
            tokens = vision.encode_window(frames)
            target = sonar.encode([label])[0]
            cache_sample(out_dir, sid, tokens, target, label,
                         max_tokens=args.max_tokens)
            n_video += 1
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
