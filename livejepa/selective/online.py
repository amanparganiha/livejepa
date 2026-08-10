"""Online (streaming) selective decoding.

The real-time path: maintain a sliding buffer of the most recent predicted
embeddings and fire a decode when the local-window semantic variance exceeds
a threshold (a meaning shift), with a minimum-gap guard to avoid bursts.

This is the faithful low-latency realization of VL-JEPA's stated trigger:
"decoded only when a significant semantic shift is detected, such as when
the local window variance exceeds a threshold."
"""
from __future__ import annotations
import numpy as np
from collections import deque


def _unit(v):
    return v / (np.linalg.norm(v) + 1e-8)


class VarianceTrigger:
    """Feed embeddings one at a time via `step`. Returns the embedding to
    decode (pooled over the window) when a decode should fire, else None."""

    def __init__(self, window=8, tau=0.15, min_gap=4, pool="mean"):
        self.buf = deque(maxlen=window)       # normalized, for shift detection
        self.buf_raw = deque(maxlen=window)   # native scale, for decoding
        self.tau = tau
        self.min_gap = min_gap
        self.pool = pool
        self.since = min_gap  # allow an early first decode once buffer fills

    def reset(self):
        self.buf.clear()
        self.buf_raw.clear()
        self.since = self.min_gap

    def step(self, e: np.ndarray):
        raw = np.asarray(e, dtype=np.float32)
        self.buf_raw.append(raw)
        self.buf.append(_unit(raw))
        self.since += 1
        if len(self.buf) < self.buf.maxlen:
            return None
        window = np.stack(self.buf)
        centroid = _unit(window.mean(0))
        # semantic shift = how far the newest embedding is from the window centroid
        shift = 1.0 - float(np.dot(self.buf[-1], centroid))
        if shift > self.tau and self.since >= self.min_gap:
            self.since = 0
            # return at native scale — the SONAR decoder rejects unit-norm vectors
            return (np.mean(self.buf_raw, axis=0) if self.pool == "mean"
                    else self.buf_raw[-1])
        return None


def run_online(stream, window=8, tau=0.15, min_gap=4, pool="mean"):
    """Run the trigger over a full (offline) stream for evaluation.
    stream: (T, d). Returns (decode_indices, embeddings_to_decode)."""
    trig = VarianceTrigger(window, tau, min_gap, pool)
    idxs, embs = [], []
    for t, e in enumerate(stream):
        out = trig.step(e)
        if out is not None:
            idxs.append(t)
            embs.append(out)
    if not idxs:  # ensure at least one decode
        idxs, embs = [len(stream) // 2], [np.asarray(stream)[len(stream) // 2]]
    return idxs, np.stack(embs)


class SegmentTrigger:
    """Online *segment-emission* trigger — a corrected streaming realization.

    `VarianceTrigger` decodes the mean of the last `window` embeddings at the
    trigger time, so its pooled vector straddles the event boundary (old+new
    mixed) and its timestamp lands on the boundary. This tracks offline Ward
    poorly. `SegmentTrigger` instead accumulates the whole current segment and,
    when a shift fires, emits the **previous segment's mean at its midpoint
    index** (retrospective, one-window latency) — matching offline's
    "decode the pooled segment at its midpoint". Same detector; better emission."""

    def __init__(self, window=8, tau=0.15, min_gap=4):
        self.window, self.tau, self.min_gap = window, tau, min_gap
        self.reset()

    def reset(self):
        self.buf = deque(maxlen=self.window)   # recent unit embeddings (shift detection)
        self.seg_raw = []                      # native-scale embeddings of current segment
        self.seg_start = 0                     # stream index where current segment began
        self.t = -1
        self.since = self.min_gap
        self.last_shift = None                 # most recent shift value (None until buffer fills)

    def step(self, e):
        """Feed one embedding. Returns (midpoint_index, pooled_embedding) when a
        segment closes, else None. Call `flush()` at stream end for the last one."""
        self.t += 1
        self.since += 1
        raw = np.asarray(e, dtype=np.float32)
        self.buf.append(_unit(raw))
        self.seg_raw.append(raw)
        if len(self.buf) < self.buf.maxlen:
            self.last_shift = None
            return None
        centroid = _unit(np.mean(self.buf, axis=0))
        shift = 1.0 - float(np.dot(self.buf[-1], centroid))
        self.last_shift = shift
        if shift > self.tau and self.since >= self.min_gap and len(self.seg_raw) > 1:
            seg = self.seg_raw[:-1]                         # close previous segment
            mid = self.seg_start + (len(seg) - 1) // 2
            pooled = np.mean(seg, axis=0)                   # native-scale segment mean
            self.seg_raw = [self.seg_raw[-1]]              # new segment starts at boundary
            self.seg_start = self.t
            self.buf.clear()                                # re-arm the detector: it must
            self.buf.append(_unit(raw))                     # re-fill on the NEW segment
            self.since = 0                                  # before it can fire again
            return mid, pooled
        return None

    def flush(self):
        if not self.seg_raw:
            return None
        mid = self.seg_start + (len(self.seg_raw) - 1) // 2
        pooled = np.mean(self.seg_raw, axis=0)
        self.seg_raw = []
        return mid, pooled


def run_online_segments(stream, window=8, tau=0.15, min_gap=4):
    """Streaming segment-emission trigger over a full stream (for evaluation).
    Returns (decode_indices at segment midpoints, pooled segment embeddings)."""
    trig = SegmentTrigger(window, tau, min_gap)
    idxs, embs = [], []
    for e in stream:
        out = trig.step(e)
        if out is not None:
            idxs.append(out[0]); embs.append(out[1])
    out = trig.flush()
    if out is not None:
        idxs.append(out[0]); embs.append(out[1])
    if not idxs:
        idxs, embs = [len(stream) // 2], [np.asarray(stream)[len(stream) // 2]]
    return idxs, np.stack(embs)


# ---- optional: change-point detection alternative (cite as a studied variant) ----
def run_ruptures(stream, n_bkps=None, pen=10.0, model="rbf"):
    """Offline change-point detection with `ruptures` as an alternative to
    variance thresholding. Decodes at segment midpoints."""
    import ruptures as rpt
    stream = np.asarray(stream, dtype=np.float32)
    algo = rpt.Pelt(model=model).fit(stream)
    bkps = algo.predict(pen=pen) if n_bkps is None else \
        rpt.Dynp(model=model).fit(stream).predict(n_bkps=n_bkps)
    bounds = [0] + list(bkps)
    idxs, embs = [], []
    for a, b in zip(bounds[:-1], bounds[1:]):
        mid = (a + b) // 2
        idxs.append(mid)
        embs.append(stream[a:b].mean(0))
    return idxs, np.stack(embs)
