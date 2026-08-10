"""Offline selective decoding (the headline method).

Partition a stream of predicted embeddings into temporally-contiguous
segments using agglomerative clustering with a temporal-connectivity
constraint and Ward (variance) linkage, then decode once per segment at
the segment midpoint, from the average-pooled segment embedding.

This mirrors VL-JEPA §4.5 / Fig. 4. Sweeping `n_segments` traces the
decoding-frequency axis of the Pareto curve.
"""
from __future__ import annotations
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from scipy.sparse import diags


def temporal_connectivity(n: int):
    """Chain graph: node i connects only to neighbors i-1 and i+1.
    Forces clusters to be temporally contiguous segments."""
    if n <= 1:
        return None
    return diags([np.ones(n - 1), np.ones(n - 1)], [-1, 1], shape=(n, n)).tocsr()


def _l2norm(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-8)


def segment_stream(emb: np.ndarray, n_segments: int, linkage: str = "ward"):
    """emb: (T, d). Returns (labels, midpoints, pooled_embeddings).

    labels: (T,) segment id per step (in time order)
    midpoints: list of segment-midpoint indices (sorted by time)
    pooled: (N, d) average-pooled embedding per segment (decode these)
    """
    raw = np.asarray(emb, dtype=np.float32)
    emb = _l2norm(raw)  # cluster in scale-invariant space ...
    T = len(emb)
    n_segments = max(1, min(n_segments, T))
    if T == 1 or n_segments == 1:
        return (np.zeros(T, dtype=int), [T // 2], raw.mean(0, keepdims=True))

    conn = temporal_connectivity(T)
    labels = AgglomerativeClustering(
        n_clusters=n_segments, linkage=linkage, connectivity=conn
    ).fit_predict(emb)

    # order segments by their first appearance in time
    seen, order = {}, []
    for lab in labels:
        if lab not in seen:
            seen[lab] = len(order)
            order.append(lab)

    midpoints, pooled = [], []
    for lab in order:
        idx = np.where(labels == lab)[0]
        midpoints.append(int(np.median(idx)))
        # ... but pool at NATIVE scale: the SONAR decoder rejects unit-norm
        # vectors (its embeddings live at norm ~0.16)
        pooled.append(raw[idx].mean(0))

    # remap labels to time order for readability
    remap = {lab: i for i, lab in enumerate(order)}
    labels = np.array([remap[l] for l in labels])
    return labels, midpoints, np.stack(pooled)


def decode_points(emb, n_segments, pool="mean", linkage="ward"):
    """Convenience: return (timestep_indices, embeddings_to_decode)."""
    _, mids, pooled = segment_stream(emb, n_segments, linkage)
    if pool == "mean":
        return mids, pooled
    # 'none' => decode the exact embedding at each midpoint instead of pooled
    return mids, np.asarray(emb, dtype=np.float32)[mids]
