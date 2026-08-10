"""Time-aligned SEMANTIC Pareto evaluation (style-robust alternative to CIDEr).

Motivation (2026-07-28, rung D.3). Running the full system on EgoExo4D produced
time-aligned CIDEr ~0.012 at every decode budget — apparently total failure. It
is not. The predictor transfers correctly; it recognises the activity and emits
accurate actions ("remove the chain", "load the inner tube" on a bike-repair
take). But EgoExo annotations use a descriptive egocentric template ("the camera
wearer takes a tire lever from the table with his right hand") while a
COIN-trained predictor speaks in imperatives. The two share almost no n-grams,
so CIDEr — an n-gram metric — reports ~0 for semantically correct output, and
both adaptive and uniform sit on the floor, making the comparison meaningless.

This script keeps VL-JEPA's time-alignment protocol exactly (each GT annotation
is matched to the nearest decoded timepoint) but replaces the n-gram score with
cosine similarity in SONAR space between the decoded-point embedding and the GT
caption's embedding. It therefore measures *meaning* rather than *phrasing*, and
can compare adaptive vs uniform where CIDEr cannot.

Reuses the cached predictor streams written by run_eval (eval_data/streams/), so
it is cheap: no video is re-encoded.

    python scripts/eval_semantic_pareto.py --ckpt checkpoints_c1_final/predictor_30000.pt \
        --uids-file eval_data/egoexo_takes_pred40.txt --max-seconds 360 \
        --out results_egoexo_predictor_40_semantic
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.run_eval import select_points
from livejepa.data.egoexo import load_atomic_descriptions, load_keystep_annotations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--ckpt", required=True,
                    help="checkpoint whose cached streams to score (name is part "
                         "of the stream-cache key)")
    ap.add_argument("--uids-file", default=None)
    ap.add_argument("--gt-source", default="atomic", choices=["atomic", "keystep"])
    ap.add_argument("--max-seconds", type=float, default=360.0)
    ap.add_argument("--freqs", default=None, help="comma-separated Hz")
    ap.add_argument("--pool", default=None, choices=["mean", "none"],
                    help="override selective.pool — 'none' decodes the exact "
                         "midpoint embedding instead of the segment mean; use it "
                         "to separate temporal SELECTION from pooling/denoising")
    ap.add_argument("--gt-emb-cache", default="eval_data/gt_emb_cache.npz",
                    help="cache of SONAR embeddings for GT captions (speeds reruns)")
    ap.add_argument("--out", default="results_semantic_pareto")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    cfg["project"]["use_stubs"] = False
    fps = cfg["eval"]["fps"]
    sel_cfg = dict(cfg["selective"])
    if args.pool:
        sel_cfg["pool"] = args.pool
        print(f"pool override: {args.pool}")
    freqs = ([float(x) for x in args.freqs.split(",")] if args.freqs
             else [f for f in cfg["eval"]["freq_sweep_hz"] if f < 2.0])

    root = os.path.join(cfg["eval"]["data_root"], "egoexo")
    gt_all = (load_atomic_descriptions(root, split="val") if args.gt_source == "atomic"
              else load_keystep_annotations(root, split="val"))
    keep = None
    if args.uids_file:
        keep = {l.strip() for l in open(args.uids_file) if l.strip()}

    # locate cached streams for this checkpoint
    tag = os.path.basename(args.ckpt)
    paths = [p for p in glob.glob(os.path.join(cfg["eval"]["data_root"], "streams",
                                               f"egoexo_*{tag}*.npz"))]
    built = []
    for p in sorted(paths):
        uid = os.path.basename(p).split("_")[1]
        if (keep and uid not in keep) or uid not in gt_all:
            continue
        d = np.load(p)
        stream, times = d["stream"], d["times"]
        gt = [(t, y) for t, y in gt_all[uid] if t <= args.max_seconds] or gt_all[uid][:1]
        if len(stream) >= 2 and gt:
            built.append((uid, stream, times, gt))
    if not built:
        raise SystemExit(f"no cached streams matching '{tag}' — run run_eval first")
    print(f"scoring {len(built)} takes, {sum(len(g) for _,_,_,g in built)} GT events",
          flush=True)

    # encode every GT caption once (SONAR), cached to disk across reruns
    texts = sorted({y for _, _, _, gt in built for _, y in gt})
    emb = {}
    if args.gt_emb_cache and os.path.exists(args.gt_emb_cache):
        z = np.load(args.gt_emb_cache, allow_pickle=True)
        emb = {k: v for k, v in zip(z["texts"], z["embs"])}
        print(f"GT embedding cache: loaded {len(emb)}", flush=True)
    missing = [t for t in texts if t not in emb]
    if missing:
        from livejepa.encoders.sonar import SonarSpace
        sonar = SonarSpace(cfg)
        print(f"encoding {len(missing)} new GT captions...", flush=True)
        B = 64
        for i in range(0, len(missing), B):
            chunk = missing[i:i + B]
            for t, e in zip(chunk, sonar.encode(chunk)):
                emb[t] = np.asarray(e, dtype=np.float32)
            if (i // B) % 10 == 0:
                print(f"  {min(i+B, len(missing))}/{len(missing)}", flush=True)
        if args.gt_emb_cache:
            os.makedirs(os.path.dirname(args.gt_emb_cache) or ".", exist_ok=True)
            ks = sorted(emb)
            np.savez_compressed(args.gt_emb_cache, texts=np.array(ks, dtype=object),
                                embs=np.stack([emb[k] for k in ks]))
            print("cached GT embeddings ->", args.gt_emb_cache, flush=True)

    def cos(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        return float(a @ b / (na * nb + 1e-8))

    # CONTROL: alongside each cell we score a SHUFFLED alignment — each GT event
    # matched to a RANDOM decoded point instead of the nearest one. If nearest
    # does not beat shuffled, the metric is not measuring temporal precision and
    # any adaptive-vs-uniform gap would be meaningless.
    rng = np.random.default_rng(0)
    results = {}
    for method in ("uniform", "adaptive", "random"):
        curve = []
        for hz in freqs:
            sims, shuf, n_dec, secs = [], [], 0, 0.0
            for uid, stream, times, gt in built:
                if method == "random":               # placement baseline: same
                    n = max(1, len(select_points("uniform", stream, hz,   # budget,
                                                 fps, sel_cfg)[0]))       # random spots
                    idxs = np.sort(rng.choice(len(stream), size=min(n, len(stream)),
                                              replace=False))
                    embs = np.asarray(stream)[idxs]
                else:
                    idxs, embs = select_points(method, stream, hz, fps, sel_cfg)
                dt = np.asarray([float(times[i]) for i in idxs])
                for t, y in gt:                      # nearest decoded timepoint
                    j = int(np.argmin(np.abs(dt - t)))
                    sims.append(cos(embs[j], emb[y]))
                    shuf.append(cos(embs[rng.integers(len(embs))], emb[y]))
                n_dec += len(idxs)
                secs += len(stream) / fps
            score, floor = float(np.mean(sims)), float(np.mean(shuf))
            curve.append({"target_hz": hz, "avg_hz": n_dec / secs if secs else 0.0,
                          "n_decodes": n_dec, "semantic_cos": score,
                          "semantic_cos_shuffled_align": floor})
            print(f"  [{method:8}] target={hz:5.2f}Hz avg={curve[-1]['avg_hz']:5.3f}Hz "
                  f"n={n_dec:5d} semantic-cos={score:.4f} (shuffled-align floor "
                  f"{floor:.4f}, lift {score-floor:+.4f})", flush=True)
        results[method] = curve

    summary = {"metric": "time-aligned SONAR cosine", "ckpt": args.ckpt,
               "gt_source": args.gt_source, "n_videos": len(built),
               "max_seconds": args.max_seconds, "results": results}
    json.dump(summary, open(args.out + ".json", "w"), indent=2)
    print("wrote", args.out + ".json")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 5))
        for m, st in (("uniform", dict(marker="s", color="#888", ls="--")),
                      ("adaptive", dict(marker="o", color="#2c7fb8", ls="-"))):
            xs = [c["avg_hz"] for c in results[m]]
            ys = [c["semantic_cos"] for c in results[m]]
            o = np.argsort(xs)
            ax.plot(np.array(xs)[o], np.array(ys)[o], label=m, **st)
        ax.set_xscale("log")
        ax.set_xlabel("avg decoding frequency (Hz, log)")
        ax.set_ylabel("time-aligned semantic similarity (SONAR cosine)")
        ax.set_title("LiveJEPA — EgoExo4D predictor stream (semantic metric)")
        ax.legend(); ax.grid(alpha=.3)
        fig.tight_layout(); fig.savefig(args.out + ".png", dpi=150)
        print("wrote", args.out + ".png")
    except Exception as e:
        print("plot skipped:", e)


if __name__ == "__main__":
    main()
