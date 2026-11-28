"""Benchmark-fidelity rerun of the atomic-description comparison, ground-truth stream.

Added 2026-11-25 after a review found that the D.1 take set
(eval_data/egoexo_takes_218.txt) is not VL-JEPA's benchmark: it was picked by
annotation count across all 8 EgoExo4D scenarios (99/218 procedural) and the loader
merged every annotator pass. VL-JEPA (sec. 4.6) uses the procedural-domain val
takes; eval_data/egoexo_takes_proc219.txt (scripts/select_egoexo_procedural.py)
reproduces its published statistics. Decision rules: WORKLOG 2026-11-25.

For any take list x annotation-pass policy x length cap, this scores uniform,
uniform_pool, adaptive and take_mean on the ground-truth stream exactly as
livejepa.run_eval builds and selects it, PER TAKE, with paired bootstrap CIs
(over takes, and over participants as a clustering check) and a per-scenario
breakdown.

Metrics
  semantic  time-aligned cosine between the embedding selected for decoding and
            SONAR(annotation). Needs only the SONAR encoder, so it is cheap. It
            rewards averaging in itself, so it compares schedules ONLY at matched
            pooling (adaptive vs uniform_pool), never adaptive vs plain uniform.
  cider     time-aligned CIDEr-D (per take and corpus-level, as run_eval). Needs
            SONAR text: --cider cache-only scores from the persisted decode cache
            and never decodes (a miss is reported, not paid for); --cider full
            decodes the misses (slow on the T1000; see WORKLOG for cost).

Usage
  # validation gate: must reproduce Table 7 (D.1) exactly, from cache, no decoding
  python scripts/eval_gt_fidelity.py --uids-file eval_data/egoexo_takes_218.txt \
      --passes all --max-seconds 360 --methods uniform,adaptive --cider cache-only \
      --encode-chunk 0 --out results_fidelity_218_all_cap360
  # semantic screen on the faithful benchmark
  python scripts/eval_gt_fidelity.py --uids-file eval_data/egoexo_takes_proc219.txt \
      --passes first --max-seconds 0 --out results_fidelity_proc219_first
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.run_eval import (select_points, corpus_cider, build_gt_stream,  # noqa: E402
                               CachedDecoder, METHODS)
from livejepa.data.egoexo import load_atomic_descriptions, ANNOTATION_PASSES  # noqa: E402


def boot_ci(vals, n=5000, seed=0):
    """95% percentile-bootstrap CI of the mean (resampling takes)."""
    v = np.asarray(vals, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def cluster_boot_ci(vals, groups, n=5000, seed=0):
    """95% CI of the mean when whole clusters (participants) are resampled, so
    takes recorded by the same person are not treated as independent."""
    v = np.asarray(vals, dtype=np.float64)
    groups = np.asarray(groups)
    members = [np.where(groups == g)[0] for g in np.unique(groups)]
    rng = np.random.default_rng(seed)
    means = np.empty(n)
    for b in range(n):
        pick = rng.integers(0, len(members), size=len(members))
        means[b] = v[np.concatenate([members[i] for i in pick])].mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


class MemoEncoder:
    """Pass-through to SonarSpace.encode that remembers text -> embedding, so the
    semantic metric reuses exactly the vectors build_gt_stream laid out.

    chunk=0 encodes a take's unique captions in ONE padded batch, exactly as
    run_eval does, so decode-cache keys match the D.1 run (the validation gate
    needs this). Full-length procedural takes carry several hundred captions,
    and one batch of that size fills an 8 GB GPU and spills into system memory,
    so new benchmarks encode in fixed chunks (deterministic, but not bit-equal
    to single-batch encoding; irrelevant for streams no earlier run decoded)."""

    def __init__(self, sonar, chunk=0):
        self.sonar, self.dim, self.table, self.chunk = sonar, sonar.dim, {}, chunk

    def encode(self, texts):
        texts = list(texts)
        step = self.chunk or max(1, len(texts))
        embs = np.concatenate([np.asarray(self.sonar.encode(texts[i:i + step]), dtype=np.float32)
                               for i in range(0, len(texts), step)], axis=0)
        for t, e in zip(texts, embs):
            self.table[t] = e
        return embs


class CacheOnlyDecoder:
    """Look decodes up in a CachedDecoder JSONL file; never runs the decoder."""

    def __init__(self, cache_path, round_dp=4):
        self.round_dp, self.cache, self.calls, self.misses = round_dp, {}, 0, 0
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                self.cache[e["k"]] = e["t"]
        print(f"decode cache (read-only): {len(self.cache)} entries from {cache_path}",
              flush=True)

    def _key(self, emb):  # identical to CachedDecoder._key
        return hashlib.sha1(np.round(emb, self.round_dp).tobytes()).hexdigest()

    def decode(self, embs):
        embs = np.atleast_2d(np.asarray(embs, dtype=np.float32))
        out = [self.cache.get(self._key(e)) for e in embs]
        self.calls += len(out)
        self.misses += sum(o is None for o in out)
        return out


def cos(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--uids-file", required=True)
    ap.add_argument("--passes", default="first", choices=ANNOTATION_PASSES)
    ap.add_argument("--max-seconds", type=float, default=0.0,
                    help="cap each take at this many seconds; 0 = full takes")
    ap.add_argument("--freqs", default=None)
    ap.add_argument("--methods", default="uniform,uniform_pool,adaptive,take_mean")
    ap.add_argument("--cider", default="off", choices=["off", "cache-only", "full"])
    ap.add_argument("--decode-cache", default="eval_data/decode_cache.jsonl")
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--max-takes", type=int, default=0, help="debug: first N takes only")
    ap.add_argument("--encode-chunk", type=int, default=64,
                    help="captions per SONAR encode batch; 0 = one batch per take, "
                         "bit-identical to run_eval (use 0 for the validation gate)")
    ap.add_argument("--out", required=True, help="output basename (.json)")
    args = ap.parse_args()

    methods = [m for m in args.methods.split(",") if m]
    bad = [m for m in methods if m not in METHODS]
    if bad:
        ap.error(f"unknown method(s) {bad}; choose from {list(METHODS)}")

    cfg = yaml.safe_load(open(args.config))
    cfg["project"]["use_stubs"] = False
    fps, sel_cfg = cfg["eval"]["fps"], cfg["selective"]
    freqs = ([float(x) for x in args.freqs.split(",")] if args.freqs
             else [f for f in cfg["eval"]["freq_sweep_hz"] if f < 2.0])
    ms = args.max_seconds or None

    root = os.path.join(cfg["eval"]["data_root"], "egoexo")
    gt_all = load_atomic_descriptions(root, split="val", passes=args.passes)
    takes = json.load(open(os.path.join(root, "takes.json"), encoding="utf-8"))
    meta = {t["take_uid"]: t for t in takes if t.get("take_uid")}
    uids = sorted({l.strip() for l in open(args.uids_file) if l.strip()})
    if args.max_takes:
        uids = uids[:args.max_takes]

    from livejepa.encoders.sonar import SonarSpace
    sonar = SonarSpace(cfg)
    enc = MemoEncoder(sonar, chunk=args.encode_chunk)

    # 1. ground-truth streams, built exactly as livejepa.run_eval does in gt mode
    t0, built, missing = time.time(), [], []
    for n_u, uid in enumerate(uids, 1):
        if n_u % 25 == 0:
            print(f"  building streams: {n_u}/{len(uids)} ({time.time() - t0:.0f}s)", flush=True)
        if uid not in gt_all:
            missing.append(uid)
            continue
        gt = gt_all[uid]
        stream, times = build_gt_stream(gt, fps, enc, noise=0.0, max_seconds=ms)
        gt_s = ([p for p in gt if p[0] <= ms] or gt[:1]) if ms else gt
        m = meta.get(uid, {})
        built.append((uid, stream, times, gt_s, m.get("parent_task_name", "unknown"),
                      m.get("participant_uid", uid)))
    if not built:
        raise SystemExit("no takes built")
    n_ann = np.array([len(b[3]) for b in built], dtype=float)
    secs_take = np.array([len(b[1]) / fps for b in built], dtype=float)
    scen_counts = {}
    for b in built:
        scen_counts[b[4]] = scen_counts.get(b[4], 0) + 1
    stats = {"n_takes": len(built), "missing_uids": missing,
             "participants": len({b[5] for b in built}), "scenarios": scen_counts,
             "mean_annotations": float(n_ann.mean()),
             "mean_stream_seconds": float(secs_take.mean()),
             "annotations_per_second": float(n_ann.sum() / secs_take.sum())}
    print(f"built {len(built)} streams in {time.time() - t0:.0f}s "
          f"(missing {len(missing)}) | {stats}", flush=True)

    decoder = None
    if args.cider == "cache-only":
        decoder = CacheOnlyDecoder(args.decode_cache)
    elif args.cider == "full":
        try:  # free the encoder: encoder + decoder overflow an 8 GB GPU in fp32
            import torch
            sonar._encoder = None
            torch.cuda.empty_cache()
        except Exception:
            pass
        decoder = CachedDecoder(sonar, cache_path=args.decode_cache)

    # 2. score every schedule at every budget, per take
    results, t_sweep = {}, time.time()
    with open(args.out + ".pid", "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{os.getpid()}\n")        # lets a long run be stopped reliably
    for method in methods:
        curve = []
        results[method] = curve            # bound early so partial flushes see progress
        for hz in freqs:
            t_hz = time.time()
            sem, cid, dec_pv, gts_pv, n_dec, secs, miss = [], [], [], [], 0, 0.0, 0
            for uid, stream, times, gt, _, _ in built:
                idxs, embs = select_points(method, stream, hz, fps, sel_cfg)
                dt = np.asarray([float(times[i]) for i in idxs])
                match = [int(np.argmin(np.abs(dt - t))) for t, _ in gt]
                sem.append(float(np.mean([cos(embs[j], enc.table[y])
                                          for j, (_, y) in zip(match, gt)])))
                if decoder is not None:
                    caps = decoder.decode(embs)
                    if any(c is None for c in caps):
                        miss += sum(c is None for c in caps)
                        cid.append(float("nan"))
                    else:
                        pairs = list(zip([float(x) for x in dt], caps))
                        cid.append(float(corpus_cider([pairs], [gt])))
                        dec_pv.append(pairs)
                        gts_pv.append(gt)
                n_dec += len(idxs)
                secs += len(stream) / fps
            row = {"target_hz": hz, "avg_hz": n_dec / secs, "n_decodes": n_dec,
                   "semantic_mean": float(np.mean(sem)), "per_take_semantic": sem}
            if decoder is not None:
                row["decode_misses"] = miss
                if miss == 0:
                    row["cider"] = float(corpus_cider(dec_pv, gts_pv))
                    row["cider_pertake_mean"] = float(np.mean(cid))
                    row["per_take_cider"] = cid
            curve.append(row)
            msg = (f"  [{method:12}] {hz:5.2f}Hz n={n_dec:6d} sem={row['semantic_mean']:.4f}")
            if "cider" in row:
                msg += f" CIDEr={row['cider']:.3f}"
            elif decoder is not None:
                msg += f" CIDEr=n/a ({miss} uncached decodes)"
            print(msg + f"  ({time.time() - t_hz:.0f}s, total "
                  f"{(time.time() - t_sweep) / 60:.1f}m)", flush=True)
            # partial flush: a long --cider full run shows finished cells as it goes,
            # and a killed run restarts cheaply because every decode is cached
            with open(args.out + ".partial.json", "w", encoding="utf-8", newline="\n") as f:
                json.dump({"partial": True, "stats": stats, "cider_mode": args.cider,
                           "results": results}, f)

    # 3. paired differences, adaptive minus each baseline, per budget and summarised
    groups = [b[5] for b in built]
    paired = {}
    for base in [b for b in ("uniform", "uniform_pool") if b in results]:
        if "adaptive" not in results:
            break
        block = {"per_budget": [], "summary": {}}
        for metric in ("semantic", "cider"):
            key = f"per_take_{metric}"
            rows_a, rows_b = results["adaptive"], results[base]
            if not all(key in r for r in rows_a + rows_b):
                continue
            diffs = []
            for ra, rb in zip(rows_a, rows_b):
                d = np.asarray(ra[key]) - np.asarray(rb[key])
                diffs.append(d)
                lo, hi = boot_ci(d, args.boot)
                block["per_budget"].append({
                    "metric": metric, "target_hz": ra["target_hz"],
                    "mean_diff": float(d.mean()), "ci95": [lo, hi],
                    "significant": bool(lo > 0 or hi < 0),
                    "takes_favoring_adaptive": int((d > 0).sum()), "n_takes": len(d)})
            across = np.mean(np.stack(diffs), axis=0)       # per take, mean over budgets
            lo, hi = boot_ci(across, args.boot)
            clo, chi = cluster_boot_ci(across, groups, args.boot)
            base_mean = float(np.mean([np.mean(rb[key]) for rb in rows_b]))
            block["summary"][metric] = {
                "mean_diff_over_budgets": float(across.mean()), "ci95_takes": [lo, hi],
                "ci95_participants": [clo, chi], "baseline_mean": base_mean,
                "budgets_won_by_adaptive": int(sum(np.mean(d) > 0 for d in diffs)),
                "n_budgets": len(diffs)}
        paired[f"adaptive_minus_{base}"] = block

    # 4. per-scenario semantic breakdown (adaptive vs each baseline, mean over budgets)
    per_scen = {}
    for s in sorted(scen_counts):
        ix = [i for i, b in enumerate(built) if b[4] == s]
        entry = {"n_takes": len(ix)}
        for base in ("uniform", "uniform_pool"):
            if "adaptive" in results and base in results:
                d = np.mean([np.asarray(ra["per_take_semantic"])[ix]
                             - np.asarray(rb["per_take_semantic"])[ix]
                             for ra, rb in zip(results["adaptive"], results[base])], axis=0)
                lo, hi = boot_ci(d, args.boot) if len(ix) > 1 else (float("nan"),) * 2
                entry[f"semantic_adaptive_minus_{base}"] = {
                    "mean": float(d.mean()), "ci95_takes": [lo, hi]}
        per_scen[s] = entry

    out = {"uids_file": args.uids_file, "passes": args.passes, "max_seconds": ms,
           "fps": fps, "selective": sel_cfg, "freqs": freqs, "cider_mode": args.cider,
           "encode_chunk": args.encode_chunk,
           "bootstrap": args.boot, "stats": stats, "results": results,
           "paired": paired, "per_scenario": per_scen,
           "decode_misses": getattr(decoder, "misses", None)}
    with open(args.out + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)

    print("\n=== summary (adaptive - baseline, mean over budgets; 95% CI takes | participants) ===")
    for name, block in paired.items():
        for metric, s in block["summary"].items():
            print(f"  {name:28} {metric:8} {s['mean_diff_over_budgets']:+.4f} "
                  f"[{s['ci95_takes'][0]:+.4f},{s['ci95_takes'][1]:+.4f}] | "
                  f"[{s['ci95_participants'][0]:+.4f},{s['ci95_participants'][1]:+.4f}]  "
                  f"adaptive ahead at {s['budgets_won_by_adaptive']}/{s['n_budgets']} budgets")
    print("wrote", args.out + ".json")


if __name__ == "__main__":
    main()
