"""Phase 1 gate: selective decoding on GROUND-TRUTH caption streams (COIN).

Builds a clean embedding stream per video from the GT step annotations —
each step contributes SONAR(label) (+ small noise) for its duration — then
checks that adaptive selective decoding Pareto-dominates uniform decoding
on time-aligned CIDEr. No predictor involved: this isolates the selective
layer itself, exactly as the master plan prescribes for Phase 1.

Stream construction: step segments are concatenated (inter-step gaps have no
GT caption, so they are skipped); each GT annotation sits at the center of
its segment on the concatenated timeline. We document this choice in the
thesis: it makes the stream fully labeled, the conservative setting for
comparing decode policies.

Run (stub mode works today, real SONAR when downloaded):
    python scripts/validate_selective_gt.py --coin-json eval_data/COIN.json
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import yaml

from livejepa.data.coin import load_annotations
from livejepa.encoders.sonar import SonarSpace
from livejepa.eval_pareto import pareto_compare


def build_gt_stream(steps, sonar, fps=2.0, noise=0.02, seed=0):
    """steps: [(start, end, label)] -> (stream (T,d), gt [(t, label)])."""
    rng = np.random.default_rng(seed)
    labels = [s[2] for s in steps]
    embs = sonar.encode(labels)  # keep NATIVE scale — the decoder needs it
    d = embs.shape[1]
    scale = float(np.linalg.norm(embs, axis=1).mean())
    stream, gt, t = [], [], 0
    for (s, e, label), emb in zip(steps, embs):
        n = max(2, int(round((e - s) * fps)))
        for _ in range(n):
            # noise norm ~= `noise` * signal norm
            stream.append(emb + (noise * scale / np.sqrt(d)) * rng.standard_normal(d))
        gt.append(((t + n / 2) / fps, label))
        t += n
    return np.stack(stream).astype(np.float32), gt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--coin-json", default="eval_data/COIN.json")
    ap.add_argument("--n-videos", type=int, default=20)
    ap.add_argument("--min-steps", type=int, default=8)
    ap.add_argument("--noise", type=float, default=0.02,
                    help="per-step noise norm relative to unit embeddings")
    ap.add_argument("--real", action="store_true",
                    help="use the real SONAR models instead of stubs")
    ap.add_argument("--freqs", default=None,
                    help="comma-separated Hz values overriding the config sweep")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    if args.real:
        cfg["project"]["use_stubs"] = False
    sonar = SonarSpace(cfg)
    fps = cfg["eval"]["fps"]
    freqs = ([float(x) for x in args.freqs.split(",")] if args.freqs
             else cfg["eval"]["freq_sweep_hz"])

    ann = load_annotations(args.coin_json)
    vids = [v for v, m in ann.items()
            if m["subset"] == "training" and len(m["steps"]) >= args.min_steps]
    vids = vids[: args.n_videos]
    print(f"validating on {len(vids)} COIN videos (>= {args.min_steps} steps each)\n")

    sums = {}
    for k, vid in enumerate(vids):
        stream, gt = build_gt_stream(ann[vid]["steps"], sonar, fps, args.noise, seed=k)
        res = pareto_compare(stream, gt, sonar, freqs, fps)
        for method, rows in res.items():
            for i, (freq, n, cider) in enumerate(rows):
                key = (method, i)
                f0, c0, cnt = sums.get(key, (0.0, 0.0, 0))
                sums[key] = (f0 + freq, c0 + cider, cnt + 1)

    print(f"{'method':9} {'avg_freq_hz':>11} {'avg_CIDEr':>10}")
    table = {}
    for (method, i), (f, c, cnt) in sorted(sums.items(), key=lambda x: (x[0][0], x[0][1])):
        f, c = f / cnt, c / cnt
        table.setdefault(method, []).append((f, c))
        print(f"{method:9} {f:11.3f} {c:10.3f}")

    # the gate: adaptive >= uniform at (almost) every frequency
    wins = sum(1 for (fa, ca), (fu, cu) in zip(table["adaptive"], table["uniform"])
               if ca >= cu - 1e-9)
    n = len(table["adaptive"])
    print(f"\nadaptive >= uniform at {wins}/{n} sweep points")
    print("PHASE 1 GATE:", "PASS" if wins >= n - 1 else "CHECK SEGMENTER")


if __name__ == "__main__":
    main()
