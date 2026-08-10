"""Pareto evaluation: adaptive selective decoding vs uniform sampling.

Sweeps the average decoding frequency and, at each point, measures
time-aligned CIDEr for (a) uniform-interval decoding and (b) adaptive
selective decoding. Produces the curve whose shape is the thesis result:
adaptive should Pareto-dominate uniform.

Run on real EgoExo4D once available; runs out-of-the-box on synthetic
streams for development (see `__main__`).
"""
from __future__ import annotations
import numpy as np

from livejepa.selective.offline import decode_points as adaptive_points
from livejepa.selective.online import run_online


def uniform_points(T, stride):
    """Uniform decode indices at a fixed stride."""
    idxs = list(range(stride // 2, T, max(1, stride)))
    return idxs or [T // 2]


def hz_to_stride(hz, fps):
    """Convert a target decode frequency (Hz) to a stride in stream steps."""
    return max(1, int(round(fps / max(hz, 1e-6))))


def sweep(stream, ground_truth, sonar, freqs_hz, fps, method="adaptive"):
    """Returns list of (avg_freq_hz, n_decodes, cider) over the sweep.
    stream: (T, d) predicted embeddings with per-step timestamps implied by fps.
    ground_truth: list[(t_seconds, text)]."""
    from livejepa.data.egoexo import time_aligned_cider
    T = len(stream)
    times = np.arange(T) / fps
    results = []
    for hz in freqs_hz:
        stride = hz_to_stride(hz, fps)
        if method == "uniform":
            idxs = uniform_points(T, stride)
            embs = np.asarray(stream)[idxs]
        elif method == "adaptive":
            n_seg = max(1, T // stride)
            idxs, embs = adaptive_points(stream, n_seg, pool="mean")
        elif method == "online":
            idxs, embs = run_online(stream)  # fixed tau; vary tau externally if needed
        else:
            raise ValueError(method)

        captions = sonar.decode(embs)
        decoded = list(zip([times[i] for i in idxs], captions))
        cider = time_aligned_cider(decoded, ground_truth)
        avg_freq = len(idxs) / (T / fps)
        results.append((avg_freq, len(idxs), cider))
    return results


def pareto_compare(stream, ground_truth, sonar, freqs_hz, fps):
    return {
        "uniform": sweep(stream, ground_truth, sonar, freqs_hz, fps, "uniform"),
        "adaptive": sweep(stream, ground_truth, sonar, freqs_hz, fps, "adaptive"),
    }


if __name__ == "__main__":
    # --- synthetic smoke test (no real data / models needed) ---
    import yaml
    from livejepa.encoders.sonar import SonarSpace

    cfg = yaml.safe_load(open("configs/default.yaml"))
    cfg["project"]["use_stubs"] = True
    sonar = SonarSpace(cfg)

    # build a synthetic stream with 5 distinct "events" of uneven length —
    # the short events are what low-rate uniform sampling misses and
    # adaptive segmentation catches
    rng = np.random.default_rng(0)
    events = ["person opens fridge", "person takes out milk",
              "person pours milk", "person closes fridge", "person washes cup"]
    seg_lens = [70, 6, 80, 8, 36]
    stream, gt = [], []
    t0 = 0
    for txt, L in zip(events, seg_lens):
        center = sonar.encode([txt])[0]
        # noise norm ~0.15 relative to the unit-norm event embedding
        noise = 0.15 / np.sqrt(center.shape[0])
        for _ in range(L):
            stream.append(center + noise * rng.standard_normal(center.shape))
        # annotate the event at its temporal center (atomic-action convention)
        gt.append(((t0 + L / 2) / cfg["eval"]["fps"], txt))
        t0 += L
    stream = np.stack(stream).astype(np.float32)

    res = pareto_compare(stream, gt, sonar, cfg["eval"]["freq_sweep_hz"], cfg["eval"]["fps"])
    print(f"{'method':9} {'freq_hz':>8} {'n_dec':>6} {'CIDEr':>7}")
    for m, rows in res.items():
        for freq, n, c in rows:
            print(f"{m:9} {freq:8.3f} {n:6d} {c:7.3f}")
