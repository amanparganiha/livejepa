"""Select EgoExo4D val takes for the paper-protocol atomic-descriptions eval (D.1).

Selections (deterministic, written to eval_data/):
  egoexo_takes_218.txt    density-MATCHED 218 takes: annotation counts closest to the
                          paper's ~143/video mean (VL-JEPA sec. 4.3), uid tiebreak.
  egoexo_takes_pred40.txt 40-take subset of the 218 for predictor-mode (video needed):
                          round-robin across scenarios, then even density spread —
                          keeps the subset representative, not densest-first (the
                          2026-07-17 pilot showed densest-first is a different regime).

Usage:  python scripts/select_egoexo_takes.py [--root eval_data/egoexo]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.egoexo import load_atomic_descriptions  # noqa: E402

PAPER_MEAN = 143
N_MATCHED = 218
N_PRED = 40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="eval_data/egoexo")
    ap.add_argument("--out-dir", default="eval_data")
    args = ap.parse_args()

    gt = load_atomic_descriptions(args.root, split="val")
    print(f"annotated val takes on disk: {len(gt)}")

    # scenario/task lookup for stratification
    scenario = {}
    takes_path = os.path.join(args.root, "takes.json")
    if os.path.exists(takes_path):
        for t in json.load(open(takes_path, encoding="utf-8")):
            uid = t.get("take_uid") or t.get("uid")
            if uid:
                scenario[uid] = (t.get("parent_task_name") or t.get("task_name")
                                 or t.get("scenario_name") or "unknown")

    # --- density-matched 218 ---
    ranked = sorted(gt, key=lambda u: (abs(len(gt[u]) - PAPER_MEAN), u))
    matched = sorted(ranked[:N_MATCHED])
    counts = sorted(len(gt[u]) for u in matched)
    print(f"matched-{N_MATCHED}: ann/take min={counts[0]} median={counts[len(counts)//2]} "
          f"max={counts[-1]} (paper mean ~{PAPER_MEAN})")

    # --- predictor-mode 40: round-robin over scenarios, densest-agnostic order ---
    by_scen = {}
    for u in matched:
        by_scen.setdefault(scenario.get(u, "unknown"), []).append(u)
    for lst in by_scen.values():  # inside a scenario: closest-to-paper-mean first
        lst.sort(key=lambda u: (abs(len(gt[u]) - PAPER_MEAN), u))
    pred = []
    while len(pred) < N_PRED and any(by_scen.values()):
        for s in sorted(by_scen):
            if by_scen[s] and len(pred) < N_PRED:
                pred.append(by_scen[s].pop(0))
    pred = sorted(pred)
    scen_counts = {}
    for u in pred:
        scen_counts[scenario.get(u, "unknown")] = scen_counts.get(scenario.get(u, "unknown"), 0) + 1
    print(f"pred-{N_PRED} scenario spread: {scen_counts}")

    os.makedirs(args.out_dir, exist_ok=True)
    for name, uids in ((f"egoexo_takes_{N_MATCHED}.txt", matched),
                       (f"egoexo_takes_pred{N_PRED}.txt", pred)):
        path = os.path.join(args.out_dir, name)
        with open(path, "w", newline="\n") as f:  # LF: uids feed POSIX-shell tooling
            f.write("\n".join(uids) + "\n")
        print(f"wrote {path} ({len(uids)} uids)")


if __name__ == "__main__":
    main()
