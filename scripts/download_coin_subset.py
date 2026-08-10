"""Download a small COIN video subset for predictor training (Phase 2).

COIN videos are YouTube links inside COIN.json. This picks the N training
videos with the most annotated steps (densest supervision per MB) and
fetches them with yt-dlp at 360p (256px windows don't need more).

    pip install yt-dlp
    python scripts/download_coin_subset.py --n 30
    python scripts/extract_features.py --coin-json eval_data/COIN.json \
        --videos-dir eval_data/coin_videos --config configs/default.yaml

Some videos will be private/deleted — the script just skips them and moves
on; aim a bit higher than the clip count you need.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livejepa.data.coin import load_annotations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin-json", default="eval_data/COIN.json")
    ap.add_argument("--out-dir", default="eval_data/coin_videos")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--per-class", type=int, default=0,
                    help="if >0, sample up to this many videos from EACH COIN class "
                         "(class-diverse — the lever for predictor vocabulary breadth) "
                         "instead of the top --n videos by step count")
    ap.add_argument("--subset", default="training", choices=["training", "testing"])
    args = ap.parse_args()

    ann = load_annotations(args.coin_json)
    cand = [(v, m) for v, m in ann.items() if m["subset"] == args.subset and m["steps"]]
    if args.per_class > 0:
        from collections import defaultdict
        by_class = defaultdict(list)
        for v, m in cand:
            by_class[m["class"]].append(v)
        vids = []
        for cls, vs in sorted(by_class.items()):
            vs.sort(key=lambda v: len(ann[v]["steps"]), reverse=True)
            vids.extend(vs[: args.per_class])
        print(f"per-class sampling: {len(by_class)} classes -> {len(vids)} videos")
    else:
        vids = [v for v, _ in sorted(cand, key=lambda x: len(x[1]["steps"]),
                                     reverse=True)][: args.n]
    os.makedirs(args.out_dir, exist_ok=True)

    got, skipped = 0, 0
    for vid in vids:
        out = os.path.join(args.out_dir, f"{vid}.mp4")
        if os.path.exists(out):
            got += 1
            continue
        r = subprocess.run(
            ["yt-dlp", "-f", "bv*[height<=360]+ba/b[height<=360]/b",
             "--merge-output-format", "mp4", "-o", out, "--no-playlist",
             f"https://www.youtube.com/watch?v={vid}"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(out):
            got += 1
            print(f"ok   {vid}  ({len(ann[vid]['steps'])} steps)")
        else:
            skipped += 1
            print(f"skip {vid}  (unavailable)")
    print(f"\ndownloaded {got}, skipped {skipped} -> {args.out_dir}")


if __name__ == "__main__":
    main()
