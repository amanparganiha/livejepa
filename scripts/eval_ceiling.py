"""Headroom analysis: how much of the remaining gap belongs to the TRIGGER and
how much to the PREDICTOR?

Motivated by a surprise in scripts/eval_rigor.py: the "oracle" (segment the
GROUND-TRUTH caption stream, decode the predicted stream at those true
boundaries) scored at or slightly BELOW adaptive. That is not a bug the second
time round -- perfect *annotation* boundaries are not the optimal decode points
for this metric, because adaptive pools over segments that are homogeneous in
PREDICTOR space, so its mean is a sharper representative of what the model
actually saw. Annotation boundaries pool across predictor-heterogeneous spans.

So the GT-boundary condition is a REFERENCE, not an upper bound. This script
computes bounds that really are bounds, and needs no SONAR decoding at all
(the semantic metric is a cosine in embedding space), so it runs in minutes:

  dense    decode EVERY timestep, no pooling. The "spend infinite compute,
           no selection" reference -- what selection has to beat.
  frame    max over all timesteps of cos(stream[j], gt). Best single frame
           any selector could ever pick, at any budget.
  window   max over all CONTIGUOUS index ranges of cos(mean(stream[a:b]), gt).
           Best pooled embedding any segmenting method could ever produce.
           This upper-bounds every row of the Pareto table, adaptive included.

Reported as: adaptive's score as a % of the window ceiling. Close to 100% means
the trigger is nearly exhausted and further gains must come from a better
predictor.

    python scripts/eval_ceiling.py --ckpt checkpoints_egoexo/predictor_20000.pt \
        --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.data.egoexo import load_atomic_descriptions


def boot_ci(vals, n=5000, seed=0):
    """95% bootstrap CI of the mean (same estimator as eval_rigor.py)."""
    v = np.asarray(vals, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def take_ceilings(stream, times, gt, emb):
    """Per-annotation (dense, best-frame, best-window) cosines for one take.

    best-window uses prefix sums: the mean over [a,b) is (P[b]-P[a])/(b-a), and
    the 1/(b-a) cancels inside a cosine, so every range's score comes from
      num[a,b] = (P[b]-P[a]) . g      and     |P[b]-P[a]|^2 = N[a]+N[b]-2 P[a].P[b]
    giving all O(T^2) ranges from two matrix products instead of a loop.
    """
    S = np.asarray(stream, dtype=np.float64)
    P = np.concatenate([np.zeros((1, S.shape[1])), np.cumsum(S, axis=0)])  # (T+1,d)
    N = (P * P).sum(1)                                                     # (T+1,)
    d2 = N[:, None] + N[None, :] - 2.0 * (P @ P.T)
    denom = np.sqrt(np.clip(d2, 0.0, None)) + 1e-12                        # |P[b]-P[a]|
    hi = np.triu(np.ones_like(denom, dtype=bool), k=1)                     # a < b only

    Sn = S / (np.linalg.norm(S, axis=1, keepdims=True) + 1e-12)
    dense, frame, window = [], [], []
    for t, y in gt:
        g = np.asarray(emb[y], dtype=np.float64)
        g = g / (np.linalg.norm(g) + 1e-12)
        dense.append(float(Sn[int(np.argmin(np.abs(times - t)))] @ g))
        per_frame = Sn @ g
        frame.append(float(per_frame.max()))
        Dg = P @ g                                                         # (T+1,)
        c = (Dg[None, :] - Dg[:, None]) / denom                            # cos[a,b]
        window.append(float(c[hi].max()))
    return dense, frame, window


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--uids-file", required=True)
    ap.add_argument("--max-seconds", type=float, default=360.0)
    ap.add_argument("--gt-emb-cache", default="eval_data/gt_emb_cache.npz")
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--compare", default="results_egoexo_rigor_oracle_fixed.json",
                    help="rigor json to express as a %% of the ceiling")
    ap.add_argument("--out", default="results_egoexo_ceiling")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    fps = cfg["eval"]["fps"]
    root = os.path.join(cfg["eval"]["data_root"], "egoexo")
    gt_all = load_atomic_descriptions(root, split="val")
    keep = {l.strip() for l in open(args.uids_file) if l.strip()}
    tag = os.path.basename(args.ckpt)

    built = []
    for p in sorted(glob.glob(os.path.join(cfg["eval"]["data_root"], "streams",
                                           f"egoexo_*{tag}*.npz"))):
        uid = os.path.basename(p).split("_")[1]
        if uid not in keep or uid not in gt_all:
            continue
        d = np.load(p)
        gt = [(t, y) for t, y in gt_all[uid] if t <= args.max_seconds] or gt_all[uid][:1]
        if len(d["stream"]) >= 2 and gt:
            built.append((uid, d["stream"], np.asarray(d["times"], dtype=np.float64), gt))
    print(f"takes: {len(built)}", flush=True)

    # GT caption embeddings come straight from the cache the rigor run filled;
    # if anything is missing we say so rather than silently loading SONAR.
    z = np.load(args.gt_emb_cache, allow_pickle=True)
    emb = {k: v for k, v in zip(z["texts"], z["embs"])}
    need = {y for _, _, _, gt in built for _, y in gt}
    miss = sorted(need - set(emb))
    if miss:
        print(f"ERROR: {len(miss)} GT captions absent from {args.gt_emb_cache}; "
              f"run scripts/eval_rigor.py first (it populates the cache).")
        sys.exit(1)

    per_take = {"dense": [], "frame": [], "window": []}
    rows = []
    for uid, stream, times, gt in built:
        dn, fr, wn = take_ceilings(stream, times, gt, emb)
        for k, v in (("dense", dn), ("frame", fr), ("window", wn)):
            per_take[k].append(float(np.mean(v)))
        rows.append({"uid": uid, "n_gt": len(gt), "dense": float(np.mean(dn)),
                     "frame": float(np.mean(fr)), "window": float(np.mean(wn))})
        print(f"  {uid[:8]}  n={len(gt):3d}  dense {np.mean(dn):.4f}  "
              f"frame {np.mean(fr):.4f}  window {np.mean(wn):.4f}", flush=True)

    summary = {}
    print("\n=== headroom (40 takes, semantic metric) ===", flush=True)
    for k in ("dense", "frame", "window"):
        lo, hi = boot_ci(per_take[k], args.boot)
        summary[k] = {"mean": float(np.mean(per_take[k])), "ci95": [lo, hi],
                      "per_take": per_take[k]}
        print(f"  {k:7} {np.mean(per_take[k]):.4f} [{lo:.4f},{hi:.4f}]", flush=True)

    ceiling = summary["window"]["mean"]
    pct = {}
    if os.path.exists(args.compare):
        cmp = json.load(open(args.compare))
        print(f"\n=== share of the achievable ceiling ({ceiling:.4f}) ===", flush=True)
        for method, curve in cmp.get("results", {}).items():
            pct[method] = []
            for row in curve:
                f = 100.0 * row["semantic_mean"] / ceiling
                pct[method].append({"target_hz": row["target_hz"],
                                    "semantic_mean": row["semantic_mean"],
                                    "pct_of_ceiling": f})
                print(f"  [{method:8}] {row['target_hz']:5.2f}Hz  "
                      f"{row['semantic_mean']:.4f}  =  {f:5.1f}% of ceiling", flush=True)

    json.dump({"ckpt": args.ckpt, "n_takes": len(built),
               "max_seconds": args.max_seconds, "bootstrap": args.boot,
               "summary": summary, "per_take": rows, "pct_of_ceiling": pct},
              open(args.out + ".json", "w"), indent=2)
    print("\nwrote", args.out + ".json")


if __name__ == "__main__":
    main()
