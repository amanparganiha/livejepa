"""Phase 3 ablations on real GT streams (EgoExo4D keysteps by default).

Reuses the run_eval machinery and a shared decode cache. Streams are given a
moderate Gaussian noise so the *denoising* components (pooling, smoothing) are
actually exercised — that's the realistic 'predicted stream' regime.

Produces (results_ablations.json + results_ablation_methods.png):
  1. method:    uniform vs adaptive (offline Ward) vs online (variance trigger)
  2. pooling:   mean-pooled vs exact-midpoint decoding
  3. online:    threshold tau x window W sensitivity
  4. smoothing: causal moving-average window 1/3/5
"""
import argparse, json, os, sys
import numpy as np, yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from livejepa.run_eval import (build_gt_stream, CachedDecoder, corpus_cider,
                               iter_eval_videos, select_points)
from livejepa.eval_pareto import hz_to_stride, uniform_points
from livejepa.selective.offline import decode_points
from livejepa.selective.online import run_online, run_online_segments
from livejepa.selective.pooling import moving_average


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="egoexo")
    ap.add_argument("--gt-source", default="keystep")
    ap.add_argument("--max-videos", type=int, default=6)
    ap.add_argument("--max-seconds", type=float, default=240)
    ap.add_argument("--noise", type=float, default=0.001,
                    help="Gaussian noise on the stream (~16 pct of native scale; lets "
                         "tau modulate the online trigger and exercises denoising)")
    args = ap.parse_args()

    cfg = yaml.safe_load(open("configs/default.yaml"))
    cfg["project"]["use_stubs"] = False
    fps = cfg["eval"]["fps"]
    sel = cfg["selective"]
    from livejepa.encoders.sonar import SonarSpace
    sonar = SonarSpace(cfg)
    dec = CachedDecoder(sonar)

    built = []
    for vid, path, gt in iter_eval_videos(cfg, args.dataset, require_video=False,
                                          gt_source=args.gt_source):
        if len(built) >= args.max_videos:
            break
        stream, times = build_gt_stream(gt, fps, sonar, noise=args.noise,
                                        max_seconds=args.max_seconds)
        if stream is not None and len(stream) >= 2:
            built.append((vid, stream, times, gt))
    print(f"built {len(built)} noisy GT streams (noise={args.noise})\n")

    def score(points_per_video):
        decoded_pv, gts_pv, ndec, secs = [], [], 0, 0.0
        for (idxs, embs), (vid, stream, times, gt) in zip(points_per_video, built):
            caps = dec.decode(embs)
            decoded_pv.append(list(zip([float(times[i]) for i in idxs], caps)))
            gts_pv.append(gt); ndec += len(idxs); secs += len(stream) / fps
        return corpus_cider(decoded_pv, gts_pv), (ndec / secs if secs else 0.0), ndec

    R = {}

    # ---- 1. method comparison ----
    freqs = [0.35, 0.2, 0.1, 0.05]
    methods = {}
    for name in ("uniform", "adaptive"):
        curve = []
        for hz in freqs:
            pts = [select_points(name, s, hz, fps, sel) for _, s, _, _ in built]
            c, a, n = score(pts)
            curve.append({"avg_hz": a, "cider": c, "n": n})
        methods[name] = curve
    online = []
    for tau in [0.08, 0.12, 0.16, 0.22, 0.30]:
        pts = [run_online(s, sel["window"], tau, sel["min_gap"], "mean") for _, s, _, _ in built]
        c, a, n = score(pts)
        online.append({"tau": tau, "avg_hz": a, "cider": c, "n": n})
    methods["online"] = online
    online_seg = []                          # corrected: retrospective segment emission
    for tau in [0.08, 0.12, 0.16, 0.22, 0.30]:
        pts = [run_online_segments(s, sel["window"], tau, sel["min_gap"]) for _, s, _, _ in built]
        c, a, n = score(pts)
        online_seg.append({"tau": tau, "avg_hz": a, "cider": c, "n": n})
    methods["online_seg"] = online_seg
    R["methods"] = methods
    print("== 1. method comparison (CIDEr @ avg Hz) ==")
    for name in ("uniform", "adaptive"):
        print(" ", name, " ".join(f"{r['cider']:.2f}@{r['avg_hz']:.2f}" for r in methods[name]))
    print("  online     ", " ".join(f"{r['cider']:.2f}@{r['avg_hz']:.2f}" for r in online))
    print("  online_seg ", " ".join(f"{r['cider']:.2f}@{r['avg_hz']:.2f}" for r in online_seg))

    # ---- 2. pooling mean vs none ----
    pool_tab = []
    for hz in [0.35, 0.2, 0.1]:
        row = {"hz": hz}
        for pool in ("mean", "none"):
            pts = [decode_points(s, max(1, len(uniform_points(len(s), hz_to_stride(hz, fps)))), pool=pool)
                   for _, s, _, _ in built]
            c, a, n = score(pts)
            row[pool] = round(c, 3)
        pool_tab.append(row)
    R["pooling"] = pool_tab
    print("\n== 2. pooling (mean vs exact-midpoint) ==")
    for r in pool_tab:
        print(f"  {r['hz']:.2f}Hz  mean={r['mean']:.3f}  none={r['none']:.3f}  "
              f"(pool helps: {r['mean'] - r['none']:+.3f})")

    # ---- 3. online tau x window ----
    grid = []
    for W in [4, 8, 16]:
        for tau in [0.1, 0.15, 0.2]:
            pts = [run_online(s, W, tau, sel["min_gap"], "mean") for _, s, _, _ in built]
            c, a, n = score(pts)
            grid.append({"W": W, "tau": tau, "avg_hz": round(a, 3), "cider": round(c, 3)})
    R["online_grid"] = grid
    print("\n== 3. online trigger sensitivity (W x tau) ==")
    for r in grid:
        print(f"  W={r['W']:2d} tau={r['tau']:.2f} -> {r['avg_hz']:.3f}Hz  CIDEr={r['cider']:.3f}")

    # ---- 4. smoothing ----
    smooth = []
    for win in [1, 3, 5]:
        pts = []
        for _, s, _, _ in built:
            ss = moving_average(s, win) if win > 1 else s
            pts.append(decode_points(ss, max(1, len(uniform_points(len(ss), hz_to_stride(0.2, fps)))), pool="mean"))
        c, a, n = score(pts)
        smooth.append({"smooth_window": win, "avg_hz": round(a, 3), "cider": round(c, 3)})
    R["smoothing"] = smooth
    print("\n== 4. stream smoothing (@~0.2Hz adaptive) ==")
    for r in smooth:
        print(f"  smooth_window={r['smooth_window']} -> CIDEr={r['cider']:.3f}")

    print(f"\ndecode cache: {dec.hits}/{dec.calls} reused")
    json.dump(R, open("results_ablations.json", "w"), indent=2)
    print("wrote results_ablations.json")

    # methods Pareto plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 5))
    sty = {"uniform": dict(marker="s", color="#888", ls="--"),
           "adaptive": dict(marker="o", color="#2c7fb8", ls="-"),
           "online": dict(marker="^", color="#d95f0e", ls=":"),
           "online_seg": dict(marker="v", color="#31a354", ls="-")}
    for name, curve in methods.items():
        xs = [r["avg_hz"] for r in curve]; ys = [r["cider"] for r in curve]
        o = np.argsort(xs)
        ax.plot(np.array(xs)[o], np.array(ys)[o], label=name, **sty.get(name, {}))
    ax.set_xscale("log"); ax.set_xlabel("avg decoding frequency (Hz, log)")
    ax.set_ylabel("time-aligned CIDEr-D")
    ax.set_title(f"LiveJEPA ablation — uniform vs adaptive vs online ({args.dataset} {args.gt_source}, noisy)")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig("results_ablation_methods.png", dpi=130)
    print("wrote results_ablation_methods.png")


if __name__ == "__main__":
    main()
