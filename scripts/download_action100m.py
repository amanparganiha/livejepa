"""Download Action100M-preview annotations + videos for predictor training.

Two stages, both resumable:
  1. --shards N      fetch the first N annotation parquet shards (~tens of MB each)
  2. video download  rank videos by usable-segment count (densest supervision
                     first), fetch with yt-dlp @360p, skip dead links, write a
                     segments manifest for the cache builder.

Examples:
    # dry-run scale (5 videos from 1 shard):
    python scripts/download_action100m.py --shards 1 --max-videos 5

    # C2 scale on a pod:
    python scripts/download_action100m.py --shards 28 --max-videos 8000 --sleep 1
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.action100m import PARQUET_URL, N_SHARDS, load_segments


def fetch_shards(parquet_dir, n):
    os.makedirs(parquet_dir, exist_ok=True)
    for i in range(min(n, N_SHARDS)):
        dest = os.path.join(parquet_dir, f"part-{i:05d}.parquet")
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        url = PARQUET_URL.format(i)
        print(f"fetching shard {i}: {url}", flush=True)
        tmp = dest + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet-dir", default="eval_data/action100m")
    ap.add_argument("--out-dir", default="eval_data/a100m_videos")
    ap.add_argument("--shards", type=int, default=1,
                    help="number of annotation shards to fetch (28 = full preview)")
    ap.add_argument("--max-videos", type=int, default=50)
    ap.add_argument("--min-segments", type=int, default=3,
                    help="skip videos with fewer usable segments than this")
    ap.add_argument("--min-dur", type=float, default=3.0)
    ap.add_argument("--max-dur", type=float, default=60.0)
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between downloads (YouTube rate-limit relief)")
    ap.add_argument("--manifest", default=None,
                    help="segments manifest path (default <out-dir>/a100m_segments.json)")
    args = ap.parse_args()

    fetch_shards(args.parquet_dir, args.shards)
    print("parsing segments...", flush=True)
    segs = load_segments(args.parquet_dir, args.min_dur, args.max_dur)
    ranked = sorted(segs.items(), key=lambda kv: len(kv[1]), reverse=True)
    ranked = [(v, s) for v, s in ranked if len(s) >= args.min_segments]
    print(f"{len(segs)} videos with segments; {len(ranked)} pass "
          f"min-segments>={args.min_segments}; targeting {args.max_videos}", flush=True)

    os.makedirs(args.out_dir, exist_ok=True)
    manifest_path = args.manifest or os.path.join(args.out_dir, "a100m_segments.json")
    manifest = {}
    if os.path.exists(manifest_path):
        manifest = json.load(open(manifest_path))

    got = skipped = 0
    for vid, vsegs in ranked:
        if got >= args.max_videos:
            break
        out = os.path.join(args.out_dir, f"{vid}.mp4")
        if os.path.exists(out):
            manifest[vid] = vsegs
            got += 1
            continue
        r = subprocess.run(
            ["yt-dlp", "-f",
             # avoid AV1 (cloud OpenCV/ffmpeg often can't decode it -> clips skipped)
             "bv*[height<=360][vcodec!*=av01]+ba/b[height<=360][vcodec!*=av01]"
             "/bv*[height<=360]+ba/b[height<=360]/b",
             "--merge-output-format", "mp4", "-o", out, "--no-playlist",
             f"https://www.youtube.com/watch?v={vid}"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(out):
            manifest[vid] = vsegs
            got += 1
            print(f"ok   {vid}  ({len(vsegs)} segments)  [{got}/{args.max_videos}]",
                  flush=True)
        else:
            skipped += 1
            print(f"skip {vid}  (unavailable)", flush=True)
        if got % 10 == 0 or got >= args.max_videos:      # checkpoint the manifest
            json.dump(manifest, open(manifest_path, "w"))
        if args.sleep:
            time.sleep(args.sleep)

    json.dump(manifest, open(manifest_path, "w"))
    n_seg = sum(len(v) for v in manifest.values())
    print(f"\ndownloaded {got}, skipped {skipped} -> {args.out_dir}")
    print(f"manifest: {manifest_path} ({len(manifest)} videos, {n_seg} segments)")


if __name__ == "__main__":
    main()
