"""Statistical rigor pass for the D.4 headline: per-take scores, bootstrap CIs,
and an ORACLE upper bound.

The headline (RESULTS.md 5b) reports corpus-level point estimates over 40 takes.
Two questions a reader will ask, answered here:

  1. "Is adaptive > uniform significant, or noise across 40 videos?"
     -> per-take scores + PAIRED bootstrap of (adaptive - uniform). A paired
        design is the right test: both methods see the identical take, so the
        take-to-take variance cancels.

  2. "How much headroom is left?"
     -> ORACLE: segment the GROUND-TRUTH caption stream (perfect boundary
        knowledge) and decode the PREDICTED stream at those true midpoints. The
        predictor is unchanged, so this isolates the value of a perfect trigger
        and upper-bounds what any trigger could achieve.

Reuses cached streams and the persisted SONAR decode cache, so this is cheap.

    python scripts/eval_rigor.py --ckpt checkpoints_egoexo/predictor_20000.pt \
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
from livejepa.run_eval import select_points, corpus_cider, CachedDecoder, build_gt_stream
from livejepa.selective.offline import segment_stream
from livejepa.data.egoexo import load_atomic_descriptions


def boot_ci(vals, n=5000, seed=0):
    """95% bootstrap CI of the mean."""
    v = np.asarray(vals, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--uids-file", required=True)
    ap.add_argument("--max-seconds", type=float, default=360.0)
    ap.add_argument("--freqs", default=None)
    ap.add_argument("--decode-cache", default="eval_data/decode_cache_egoexo_indomain.jsonl")
    ap.add_argument("--gt-emb-cache", default="eval_data/gt_emb_cache.npz")
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--methods", default="uniform,adaptive,oracle",
                    help="comma-separated; also uniform_pool (the pooling-matched "
                         "baseline) and take_mean (one decode per take). NOTE: "
                         "'oracle' picks decode points no cache has seen, so it pays "
                         "full SONAR decode cost (~50 min/frequency); run it "
                         "separately on few freqs")
    ap.add_argument("--out", default="results_egoexo_rigor")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    cfg["project"]["use_stubs"] = False
    fps = cfg["eval"]["fps"]
    sel_cfg = cfg["selective"]
    freqs = ([float(x) for x in args.freqs.split(",")] if args.freqs
             else [f for f in cfg["eval"]["freq_sweep_hz"] if f < 2.0])

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
            built.append((uid, d["stream"], d["times"], gt))
    print(f"takes: {len(built)}", flush=True)

    from livejepa.encoders.sonar import SonarSpace
    sonar = SonarSpace(cfg)
    dec = CachedDecoder(sonar, cache_path=args.decode_cache)

    # GT caption embeddings (cached) — needed for the semantic metric and oracle
    emb = {}
    if os.path.exists(args.gt_emb_cache):
        z = np.load(args.gt_emb_cache, allow_pickle=True)
        emb = {k: v for k, v in zip(z["texts"], z["embs"])}
    texts = sorted({y for _, _, _, gt in built for _, y in gt})
    miss = [t for t in texts if t not in emb]
    if miss:
        print(f"encoding {len(miss)} GT captions...", flush=True)
        for i in range(0, len(miss), 64):
            ch = miss[i:i + 64]
            for t, e in zip(ch, sonar.encode(ch)):
                emb[t] = np.asarray(e, dtype=np.float32)
        ks = sorted(emb)
        np.savez_compressed(args.gt_emb_cache, texts=np.array(ks, dtype=object),
                            embs=np.stack([emb[k] for k in ks]))

    def cos(a, b):
        return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def points(method, stream, times, gt, hz):
        """Return (indices, embeddings) for a method.

        'oracle' = perfect boundary knowledge: segment the GROUND-TRUTH stream,
        then apply those boundaries to the PREDICTED stream. Two alignment
        details matter and were got wrong on the first attempt (making the
        oracle look no better than uniform):
          (a) build_gt_stream is timestamped from t=0 at 1/fps steps, while the
              predicted stream carries WINDOW-CENTRE times starting ~K/(2*fps)s
              in — so segments must be mapped by TIME, never by index; and
          (b) adaptive decodes segment MEANS, so the oracle must pool the
              predicted embeddings over each GT segment too, else it is
              handicapped against the method it is meant to upper-bound.
        """
        if method != "oracle":
            return select_points(method, stream, hz, fps, sel_cfg)
        stream = np.asarray(stream, dtype=np.float32)
        times = np.asarray(times, dtype=np.float32)
        n_seg = max(1, len(select_points("uniform", stream, hz, fps, sel_cfg)[0]))
        gstream, gtimes = build_gt_stream(gt, fps, sonar, max_seconds=args.max_seconds)
        labels, mids, _ = segment_stream(gstream, min(n_seg, len(gstream)),
                                         linkage=sel_cfg.get("linkage", "ward"))
        idxs, embs = [], []
        for seg in dict.fromkeys(labels):                  # time-ordered segments
            sel = np.where(labels == seg)[0]
            t0, t1 = float(gtimes[sel[0]]), float(gtimes[sel[-1]])
            tmid = 0.5 * (t0 + t1)
            in_seg = np.where((times >= t0) & (times <= t1))[0]   # map by TIME
            if len(in_seg) == 0:
                in_seg = np.array([int(np.argmin(np.abs(times - tmid)))])
            idxs.append(int(np.argmin(np.abs(times - tmid))))
            embs.append(stream[in_seg].mean(0))            # pool, as adaptive does
        return idxs, np.stack(embs).astype(np.float32)

    results = {}
    for method in [m for m in args.methods.split(",") if m]:
        curve = []
        for hz in freqs:
            per_take_sem, per_take_cid, n_dec, secs = [], [], 0, 0.0
            for uid, stream, times, gt in built:
                idxs, embs = points(method, stream, times, gt, hz)
                caps = dec.decode(embs)
                dt = np.asarray([float(times[i]) for i in idxs])
                sims = []
                dec_pv = list(zip([float(x) for x in dt], caps))
                for t, y in gt:
                    j = int(np.argmin(np.abs(dt - t)))
                    sims.append(cos(embs[j], emb[y]))
                per_take_sem.append(float(np.mean(sims)))
                per_take_cid.append(float(corpus_cider([dec_pv], [gt])))
                n_dec += len(idxs); secs += len(stream) / fps
            sem_lo, sem_hi = boot_ci(per_take_sem, args.boot)
            cid_lo, cid_hi = boot_ci(per_take_cid, args.boot)
            curve.append({
                "target_hz": hz, "avg_hz": n_dec / secs if secs else 0.0,
                "n_decodes": n_dec,
                "semantic_mean": float(np.mean(per_take_sem)),
                "semantic_ci95": [sem_lo, sem_hi],
                "cider_pertake_mean": float(np.mean(per_take_cid)),
                "cider_pertake_ci95": [cid_lo, cid_hi],
                "per_take_semantic": per_take_sem,
                "per_take_cider": per_take_cid,
            })
            print(f"  [{method:8}] {hz:5.2f}Hz  sem {np.mean(per_take_sem):.4f} "
                  f"[{sem_lo:.4f},{sem_hi:.4f}]   cider {np.mean(per_take_cid):.4f} "
                  f"[{cid_lo:.4f},{cid_hi:.4f}]", flush=True)
        results[method] = curve

    # PAIRED bootstrap: adaptive - each baseline that was run, per take (variance
    # from take difficulty cancels). 'uniform' keeps its original output key;
    # 'uniform_pool', the pooling-matched baseline, gets its own alongside it.
    baselines = [b for b in ("uniform", "uniform_pool") if b in results]
    if "adaptive" not in results or not baselines:
        json.dump({"ckpt": args.ckpt, "n_takes": len(built), "results": results},
                  open(args.out + ".json", "w"), indent=2)
        print("wrote", args.out + ".json")
        return
    out = {"ckpt": args.ckpt, "n_takes": len(built), "max_seconds": args.max_seconds,
           "bootstrap": args.boot, "results": results}
    for base in baselines:
        print(f"\n=== PAIRED adaptive - {base} (95% CI, per-take bootstrap) ===", flush=True)
        paired = []
        for i, hz in enumerate(freqs):
            row = {"target_hz": hz}
            for key, label in (("per_take_semantic", "semantic"), ("per_take_cider", "cider")):
                d = np.asarray(results["adaptive"][i][key]) - np.asarray(results[base][i][key])
                lo, hi = boot_ci(d, args.boot)
                row[label] = {"mean_diff": float(d.mean()), "ci95": [lo, hi],
                              "significant": bool(lo > 0 or hi < 0),
                              "takes_favoring_adaptive": int((d > 0).sum()), "n_takes": len(d)}
            s, c = row["semantic"], row["cider"]
            print(f"  {hz:5.2f}Hz  sem {s['mean_diff']:+.4f} [{s['ci95'][0]:+.4f},{s['ci95'][1]:+.4f}] "
                  f"{'SIG' if s['significant'] else 'ns '} ({s['takes_favoring_adaptive']}/{s['n_takes']})   "
                  f"cider {c['mean_diff']:+.4f} [{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                  f"{'SIG' if c['significant'] else 'ns '} ({c['takes_favoring_adaptive']}/{c['n_takes']})",
                  flush=True)
            paired.append(row)
        out[f"paired_adaptive_minus_{base}"] = paired

    json.dump(out, open(args.out + ".json", "w"), indent=2)
    print("\nwrote", args.out + ".json")


if __name__ == "__main__":
    main()
