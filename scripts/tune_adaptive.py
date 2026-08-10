"""Ablation: can smoothing the (noisy) predictor-mode stream before adaptive
segmentation recover the mid-band CIDEr that uniform won in WS2?

Context (results_coin_predictor.json, 7 held-out COIN val videos): on the GT
stream adaptive Pareto-dominates uniform, but on the *predicted* stream uniform
peaks at 0.20 Hz (2.96) and beats adaptive in the 0.20-0.35 Hz band. Hypothesis:
the predicted stream is noisier, so Ward boundaries land on per-step noise rather
than real semantic transitions; a moving-average pre-smooth should fix the
boundaries and recover the advantage.

This reuses run_eval's EXACT SONAR decoder + time-aligned CIDEr, so every number
here is directly comparable to results_coin_predictor.json. Streams are loaded
from the cache written during WS2 (no re-encoding), and a single shared decode
cache is used across all configs, so the whole sweep is cheap.

Reproduce:
    python scripts/tune_adaptive.py --ckpt checkpoints_kaggle/predictor_20000.pt

Outputs results_adaptive_tuning.json + a console table (uniform baseline, then
each adaptive config with per-frequency Delta vs uniform and a WIN marker).
"""
import argparse, glob, itertools, json, os, sys
import numpy as np, yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.run_eval import (select_points, corpus_cider, CachedDecoder,
                               iter_eval_videos)


def load_cached_streams(cfg, ckpt):
    """vid -> (stream, times) from the WS2 stream cache for this exact ckpt."""
    ck = f"{os.path.basename(ckpt)}.{int(os.path.getmtime(ckpt))}"
    sdir = os.path.join(cfg["eval"]["data_root"], "streams")
    out = {}
    for f in glob.glob(os.path.join(sdir, f"coin_*_{ck}.npz")):
        vid = os.path.basename(f).split("_K")[0][len("coin_"):]
        d = np.load(f)
        out[vid] = (d["stream"], d["times"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--max-seconds", type=float, default=180.0)
    ap.add_argument("--freqs", default="0.5,0.35,0.2,0.1",
                    help="mid-band Hz where WS2 adaptive lost")
    ap.add_argument("--smoothings", default="1,3,5,7",
                    help="moving-average windows to test (1 = WS2 baseline)")
    ap.add_argument("--linkages", default="ward,average")
    ap.add_argument("--out", default="results_adaptive_tuning.json")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    cfg["project"]["use_stubs"] = False
    cfg["eval"]["coin_split"] = "val"
    fps = cfg["eval"]["fps"]
    freqs = [float(x) for x in args.freqs.split(",")]

    streams = load_cached_streams(cfg, args.ckpt)
    if not streams:
        raise SystemExit("No cached streams for this ckpt. Run WS2 (run_eval "
                         "--mode predictor) first so eval_data/streams is populated.")

    # GT via the same iterator run() uses, capped to match the stream span
    gts = {}
    for vid, _path, gt in iter_eval_videos(cfg, "coin", require_video=True,
                                           gt_source="atomic"):
        gts[vid] = [p for p in gt if p[0] <= args.max_seconds] or gt[:1]

    vids = sorted(v for v in streams if v in gts)
    print(f"{len(vids)} videos with cached stream + GT: {vids}\n")

    from livejepa.encoders.sonar import SonarSpace
    dec = CachedDecoder(SonarSpace(cfg))   # one shared cache across all configs

    def score(method, sel_cfg):
        curve = {}
        for hz in freqs:
            dpv, gpv, ndec, secs = [], [], 0, 0.0
            for v in vids:
                stream, times = streams[v]
                idxs, embs = select_points(method, stream, hz, fps, sel_cfg)
                caps = dec.decode(embs)
                dpv.append(list(zip([float(times[i]) for i in idxs], caps)))
                gpv.append(gts[v]); ndec += len(idxs); secs += len(stream) / fps
            curve[hz] = {"cider": corpus_cider(dpv, gpv),
                         "avg_hz": ndec / secs if secs else 0.0, "n": ndec}
        return curve

    uni = score("uniform", cfg["selective"])
    print("UNIFORM baseline:")
    for hz in freqs:
        print(f"  {hz:5.2f}Hz  CIDEr={uni[hz]['cider']:.3f}")

    adaptive = {}
    best = None
    for w, lk in itertools.product(
            [int(x) for x in args.smoothings.split(",")],
            [s.strip() for s in args.linkages.split(",")]):
        sc = dict(cfg["selective"]); sc["smoothing_window"] = w; sc["linkage"] = lk
        cur = score("adaptive", sc)
        name = f"smooth{w}_{lk}"
        adaptive[name] = cur
        wins = sum(cur[hz]["cider"] > uni[hz]["cider"] for hz in freqs)
        mean_delta = np.mean([cur[hz]["cider"] - uni[hz]["cider"] for hz in freqs])
        tag = " <-- WS2 baseline" if (w == 1 and lk == "ward") else ""
        print(f"\nADAPTIVE smoothing={w} linkage={lk}"
              f"  [wins {wins}/{len(freqs)}, mean d={mean_delta:+.3f}]{tag}")
        for hz in freqs:
            u, a = uni[hz]["cider"], cur[hz]["cider"]
            print(f"  {hz:5.2f}Hz  CIDEr={a:.3f}  (uniform {u:.3f})  "
                  f"{'WIN ' if a > u else '    '}d={a - u:+.3f}")
        if best is None or mean_delta > best[1]:
            best = (name, mean_delta, wins)

    print(f"\nBEST adaptive config: {best[0]}  "
          f"(mean d={best[1]:+.3f} vs uniform, wins {best[2]}/{len(freqs)})")

    json.dump({"ckpt": args.ckpt, "n_videos": len(vids), "vids": vids,
               "freqs": freqs,
               "uniform": {str(k): v for k, v in uni.items()},
               "adaptive": {n: {str(k): v for k, v in c.items()}
                            for n, c in adaptive.items()},
               "best": {"config": best[0], "mean_delta": best[1]}},
              open(args.out, "w"), indent=2)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
