"""Build livejepa_cloud.zip — everything a rented Linux GPU pod (RunPod/Vast) needs.

Default (demo/serve): code, configs, tests, the two predictors the demo switches
between (COIN c1_final and the in-domain EgoExo one), the web app, deploy scripts,
a few COIN sample videos. (The superseded checkpoints_kaggle predictor is left out:
the server only falls back to it when c1_final is missing, and c1_final ships.)
--c2 (rung-C2 training weekend): additionally bundles the small training assets —
COIN.json, the frozen-val + EgoExo uid lists, the Action100M segment manifest, and
the C2 runbook. Deliberately EXCLUDES the ~1 GB frozen val caches and any videos:
the pod TRAINS, and the resulting checkpoint is GATED at home on the T1000 against
the fixed vals (cheaper, smaller upload, no AWS creds on a rented pod).
Excludes always: caches, results, cloudflared.exe, uploads/thumbs, notebooks.

Usage:  python scripts/make_cloud_bundle.py [--c2] [--out livejepa_cloud.zip] [--samples 6]
"""
import argparse
import glob
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INCLUDE_DIRS = ["livejepa", "configs", "scripts", "tests", "deploy"]
INCLUDE_FILES = ["requirements.txt", "README.md", "RESULTS.md", "HANDOFF.md",
                 os.path.join("checkpoints_c1_final", "predictor_30000.pt"),
                 os.path.join("checkpoints_egoexo", "predictor_20000.pt"),
                 os.path.join("webapp", "backend.py"),
                 os.path.join("webapp", "README.md"),
                 os.path.join("webapp", "static", "index.html"),
                 os.path.join("webapp", "static", "about.html"),
                 os.path.join("webapp", "static", "brand.html")]
# small training assets for --c2 (no big caches, no videos)
C2_FILES = [os.path.join("eval_data", "COIN.json"),
            os.path.join("eval_data", "frozen_val_uids.txt"),
            os.path.join("eval_data", "coin_union_state.json"),
            os.path.join("eval_data", "egoexo_takes_218.txt"),
            os.path.join("eval_data", "egoexo_takes_pred40.txt"),
            os.path.join("eval_data", "a100m_videos", "a100m_segments.json")]
SKIP_PATTERNS = ("__pycache__", ".pyc", "cloudflared", "server.log", "autopilot.log")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "livejepa_cloud.zip"))
    ap.add_argument("--c2", action="store_true",
                    help="bundle rung-C2 training assets (COIN.json, uid lists, "
                         "A100M manifest); pod trains, home gates")
    ap.add_argument("--samples", type=int, default=6,
                    help="number of COIN sample videos to bundle for the UI gallery")
    args = ap.parse_args()

    files = []
    for d in INCLUDE_DIRS:
        for p in glob.glob(os.path.join(ROOT, d, "**", "*"), recursive=True):
            if os.path.isfile(p) and not any(s in p for s in SKIP_PATTERNS):
                files.append(p)
    include = list(INCLUDE_FILES) + (C2_FILES if args.c2 else [])
    for f in include:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            files.append(p)
        else:
            print(f"WARNING: missing {f}")
    samples = sorted(glob.glob(os.path.join(ROOT, "eval_data", "coin_videos", "*.mp4")))
    files += samples[: args.samples]

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(files)):
            z.write(p, os.path.relpath(p, ROOT))
    print(f"wrote {args.out}  ({os.path.getsize(args.out) / 1e6:.1f} MB, "
          f"{len(set(files))} files, {min(args.samples, len(samples))} sample videos, "
          f"c2={'yes' if args.c2 else 'no'})")


if __name__ == "__main__":
    main()
