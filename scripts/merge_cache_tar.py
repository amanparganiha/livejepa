"""Dup-safe merge of a lane's cache tar into the local master cache.

Copies BOTH .npz and .txt companions (2026-07-19 lesson: an npz-only merge left
2,888 clips caption-less and broke eval). Never touches the master's
pipeline_state.json or VAL_UIDS.txt — the local lane's state is authoritative.

Usage:  python scripts/merge_cache_tar.py backups/coin_cache_p7.tar
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile

SUBDIRS = ("data_cache_coin_full", "data_cache_coin_full_val")
PROTECTED = {"pipeline_state.json", "VAL_UIDS.txt"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tar")
    ap.add_argument("--root", default=".", help="repo root holding the master dirs")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="cache_merge_")
    try:
        subprocess.run(["tar", "-xf", args.tar, "-C", tmp], check=True)
        for sub in SUBDIRS:
            src, dst = os.path.join(tmp, sub), os.path.join(args.root, sub)
            if not os.path.isdir(src):
                continue
            os.makedirs(dst, exist_ok=True)
            copied = skipped = 0
            for p in glob.glob(os.path.join(src, "*")):
                name = os.path.basename(p)
                if name in PROTECTED:
                    continue
                d = os.path.join(dst, name)
                if os.path.exists(d):
                    skipped += 1
                else:
                    shutil.copy2(p, d)
                    copied += 1
            n = len(glob.glob(os.path.join(dst, "*.npz")))
            print(f"{sub}: +{copied} files ({skipped} dups skipped) -> {n} clips")
        s = os.path.join(tmp, SUBDIRS[0], "pipeline_state.json")
        if os.path.exists(s):
            st = json.load(open(s))
            print(f"lane state in tar (info only): done={len(st.get('done', []))} "
                  f"dead={len(st.get('dead', []))}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
