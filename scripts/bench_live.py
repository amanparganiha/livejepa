"""Measure the ONE number that decides whether the live webcam demo feels good:
seconds per window through V-JEPA 2 -> predictor, plus a SONAR decode.

Why this matters more than GPU spec sheets: SegmentTrigger clears its detector
buffer after every fire (livejepa/selective/online.py:114) and must re-fill
before it can fire again, so with `selective.window = W` the demo stays silent
for W x (seconds/window) BOTH before the first caption and between captions.
`min_gap` is usually not the binding constraint. This script reports that
latency directly for the current config, and for a couple of shorter windows.

Runs on whatever GPU it finds, so use it to compare a rental against the local
box before committing money. Synthetic frames -- no webcam or dataset needed.

    python scripts/bench_live.py                 # current config
    python scripts/bench_live.py --iters 20 --windows 8,4,3
"""
import argparse
import os
import sys
import time

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--ckpt", default=None, help="predictor ckpt (default: config/env)")
    ap.add_argument("--iters", type=int, default=12, help="timed windows (after warmup)")
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--windows", default="8,4,3",
                    help="detector windows to report latency for")
    ap.add_argument("--no-decode", action="store_true", help="skip the SONAR decode timing")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    cfg["project"]["use_stubs"] = False
    K = cfg["encoders"]["vision"]["frames_per_window"]
    res = cfg["encoders"]["vision"]["resolution"]

    try:
        import torch
        dev = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    except Exception:
        dev = "unknown"
    print(f"device: {dev}\nK={K} frames @ {res}x{res}, dtype={cfg['encoders']['vision']['dtype']}",
          flush=True)

    from livejepa.encoders.vision import VisionEncoder      # same imports the
    from livejepa.predictor.infer import load_predictor     # webapp uses (backend.py:88)
    vision = VisionEncoder(cfg)
    predict = load_predictor(cfg, args.ckpt)

    rng = np.random.default_rng(0)
    frames = [rng.integers(0, 255, (res, res, 3), dtype=np.uint8) for _ in range(K)]

    for _ in range(args.warmup):                       # cuDNN autotune + weight paging
        predict(vision.encode_window(frames))

    ts = []
    for i in range(args.iters):
        t0 = time.perf_counter()
        emb = predict(vision.encode_window(frames))
        ts.append(time.perf_counter() - t0)
        print(f"  window {i + 1}/{args.iters}: {ts[-1] * 1000:7.1f} ms", flush=True)
    ts = np.array(ts)
    per_win = float(np.median(ts))
    print(f"\nseconds/window: median {per_win:.3f}  mean {ts.mean():.3f}  "
          f"min {ts.min():.3f}  max {ts.max():.3f}")

    dec_s = None
    if not args.no_decode:
        from livejepa.encoders.sonar import SonarSpace
        sonar = SonarSpace(cfg)
        sonar.decode(np.asarray(emb)[None])            # warm the decoder
        t0 = time.perf_counter()
        txt = sonar.decode(np.asarray(emb)[None])[0]
        dec_s = time.perf_counter() - t0
        print(f"SONAR decode (1 caption): {dec_s:.3f} s   -> {txt!r}")

    print("\n=== what the demo will feel like ===")
    print("  detector    silence before      silence between")
    print("  window      first caption       captions")
    for w in (int(x) for x in args.windows.split(",") if x.strip()):
        gap = w * per_win + (dec_s or 0.0)
        print(f"  {w:<11d} {w * per_win:6.1f} s{'':12}{gap:6.1f} s")
    print("\nRule of thumb: under ~10 s between captions reads as live to an "
          "audience; over ~30 s reads as broken. Lower `selective.window` (or send "
          '`window` in the /ws_cam config message) to trade detector context for '
          "responsiveness -- demo only, it is not the measurement setting.")


if __name__ == "__main__":
    main()
