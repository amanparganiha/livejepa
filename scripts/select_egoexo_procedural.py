"""Write the benchmark-faithful EgoExo4D take list (added 2026-11-25).

VL-JEPA (arXiv:2512.10942, sec. 4.6) evaluates selective decoding on the EgoExo4D
validation takes of the *procedural* activity domains: 218 videos averaging 6 min
with ~143 atomic-action annotations each. On disk, the val takes whose
parent_task_name is Cooking, Health or Bike Repair and that carry atomic
descriptions number 219, average 5.95 min, and have 143.8 annotations per take
when a single annotator pass is used, which matches that description.

This script only WRITES eval_data/egoexo_takes_proc219.txt (sorted uids, LF). It
never touches the frozen egoexo_takes_218.txt / egoexo_takes_pred40.txt lists,
which select_egoexo_takes.py owns.

Usage:  python scripts/select_egoexo_procedural.py [--root eval_data/egoexo]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.egoexo import load_atomic_descriptions  # noqa: E402

PROCEDURAL = ("Cooking", "Health", "Bike Repair")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="eval_data/egoexo")
    ap.add_argument("--out", default="eval_data/egoexo_takes_proc219.txt")
    args = ap.parse_args()

    gt_first = load_atomic_descriptions(args.root, split="val", passes="first")
    takes = json.load(open(os.path.join(args.root, "takes.json"), encoding="utf-8"))
    meta = {t["take_uid"]: t for t in takes if t.get("take_uid")}

    sel = sorted(u for u in gt_first
                 if u in meta and meta[u].get("parent_task_name") in PROCEDURAL)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sel) + "\n")

    dur = np.array([meta[u].get("duration_sec") or np.nan for u in sel], dtype=float)
    n = np.array([len(gt_first[u]) for u in sel], dtype=float)
    by = {s: sum(meta[u]["parent_task_name"] == s for u in sel) for s in PROCEDURAL}
    print(f"wrote {args.out}: {len(sel)} takes {by}")
    print(f"  mean duration {np.nanmean(dur) / 60:.2f} min | "
          f"mean annotations (one pass) {n.mean():.1f} | "
          f"participants {len({meta[u].get('participant_uid') for u in sel})}")


if __name__ == "__main__":
    main()
