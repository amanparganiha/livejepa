"""Pre-extract and cache training features.

Running V-JEPA 2 once over your clips and caching (visual_tokens, target
SONAR embedding) to disk turns predictor training into a cheap regression
with no encoder in the loop — the key to single-GPU feasibility.

Cache format: one .npz per sample with keys 'tokens' (N, vis_dim) and
'target' (out_dim,), plus the caption text in a sidecar .txt.
"""
from __future__ import annotations
import os
import numpy as np


def cache_sample(out_dir, sample_id, tokens, target, caption, max_tokens=0):
    """Cache one sample. `max_tokens > 0` subsamples token rows evenly at cache
    time with the SAME np.linspace rule train.collate() applies at load time —
    training sees identical inputs, but the npz shrinks ~len/max_tokens-fold
    (measured: 3.9 MB/clip at 2048 tokens -> ~0.5 MB at 256)."""
    os.makedirs(out_dir, exist_ok=True)
    if max_tokens and len(tokens) > max_tokens:
        tokens = tokens[np.linspace(0, len(tokens) - 1, max_tokens).astype(int)]
    np.savez_compressed(
        os.path.join(out_dir, f"{sample_id}.npz"),
        tokens=tokens.astype(np.float16), target=target.astype(np.float32),
    )
    with open(os.path.join(out_dir, f"{sample_id}.txt"), "w") as f:
        f.write(caption)


def build_cache(cfg, clips, vision_encoder, sonar):
    """clips: iterable of (sample_id, frames_list, caption).
    Extracts V-JEPA 2 tokens + SONAR target embedding for each and caches them."""
    out_dir = cfg["train"]["data_root"]
    for sample_id, frames, caption in clips:
        tokens = vision_encoder.encode_window(frames)        # (N, vis_dim)
        target = sonar.encode([caption])[0]                  # (out_dim,)
        cache_sample(out_dir, sample_id, tokens, target, caption)
    print(f"Cached features to {out_dir}")


class CachedDataset:
    """Minimal torch-style dataset over the cache. Avoids importing torch at
    module import so the file is usable without torch installed.

    `data_root` may be a single dir, a comma-separated list of dirs, or a list —
    needed on Kaggle where resumed extraction sessions each produce a read-only
    delta dataset. Later roots win on duplicate sample ids."""

    def __init__(self, data_root):
        roots = (data_root if isinstance(data_root, (list, tuple))
                 else [r for r in str(data_root).split(",") if r])
        self.by_id = {}
        for root in roots:
            for f in os.listdir(root):
                if f.endswith(".npz"):
                    self.by_id[f[:-4]] = os.path.join(root, f)
        self.ids = sorted(self.by_id)

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        d = np.load(self.by_id[self.ids[i]])
        return d["tokens"].astype(np.float32), d["target"].astype(np.float32)
