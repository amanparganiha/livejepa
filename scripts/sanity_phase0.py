"""Phase 0 sanity checks (the plan's gate for weeks 1-2).

1. SONAR round-trip: text -> 1024-d embedding -> text.
2. V-JEPA 2 feature extraction from a synthetic frame window.

Run from the repo root:  python scripts/sanity_phase0.py [--skip-vision]
Models download from Hugging Face on first run (SONAR ~3 GB, V-JEPA 2 ~1.2 GB).
"""
import argparse
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import yaml


def check_sonar(cfg):
    from livejepa.encoders.sonar import SonarSpace
    print("== SONAR round-trip ==")
    t0 = time.time()
    sonar = SonarSpace(cfg)
    print(f"loaded in {time.time() - t0:.1f}s (backend={sonar.backend})")

    sentences = [
        "a person slices a tomato on a cutting board",
        "the man opens the refrigerator and takes out milk",
        "someone is washing a cup in the sink",
    ]
    emb = sonar.encode(sentences)
    print(f"encoded {len(sentences)} sentences -> {emb.shape} (expect (3, 1024))")
    assert emb.shape == (3, cfg["encoders"]["sonar"]["embed_dim"])

    decoded = sonar.decode(emb)
    ok = 0
    for s, d in zip(sentences, decoded):
        match = "~" if s.split()[2:4] != d.split()[2:4] else "="
        ok += match == "="
        print(f"  in : {s}\n  out: {d}\n")
    print(f"round-trip: {ok}/{len(sentences)} near-exact (paraphrase is OK)\n")
    return sonar


def check_vision(cfg):
    from livejepa.encoders.vision import VisionEncoder
    print("== V-JEPA 2 feature extraction ==")
    t0 = time.time()
    venc = VisionEncoder(cfg)
    print(f"loaded in {time.time() - t0:.1f}s")

    K = cfg["encoders"]["vision"]["frames_per_window"]
    res = cfg["encoders"]["vision"]["resolution"]
    rng = np.random.default_rng(0)
    frames = [rng.integers(0, 255, (res, res, 3), dtype=np.uint8) for _ in range(K)]
    t0 = time.time()
    tokens = venc.encode_window(frames)
    print(f"window of {K} frames -> tokens {tokens.shape} in {time.time() - t0:.1f}s")
    assert tokens.ndim == 2 and tokens.shape[1] == cfg["predictor"]["vis_dim"]
    print("vision OK\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-vision", action="store_true")
    ap.add_argument("--skip-sonar", action="store_true")
    ap.add_argument("--cpu", action="store_true", help="force CPU")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "..", "configs", "default.yaml")))
    cfg["project"]["use_stubs"] = False
    if args.cpu:
        cfg["project"]["device"] = "cpu"

    if not args.skip_sonar:
        check_sonar(cfg)
    if not args.skip_vision:
        check_vision(cfg)
    print("Phase 0 sanity: PASS")
