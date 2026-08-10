"""Smoothing / pooling utilities for the embedding stream.

The paper notes average pooling gives consistent gains before decoding,
because it denoises and stabilizes the predicted embeddings.
"""
from __future__ import annotations
import numpy as np


def moving_average(stream: np.ndarray, window: int = 3) -> np.ndarray:
    """Causal moving average over time. window=1 is a no-op."""
    stream = np.asarray(stream, dtype=np.float32)
    if window <= 1 or len(stream) <= 1:
        return stream
    out = np.empty_like(stream)
    for t in range(len(stream)):
        lo = max(0, t - window + 1)
        out[t] = stream[lo : t + 1].mean(0)
    return out


def l2_normalize(stream: np.ndarray) -> np.ndarray:
    stream = np.asarray(stream, dtype=np.float32)
    return stream / (np.linalg.norm(stream, axis=-1, keepdims=True) + 1e-8)
